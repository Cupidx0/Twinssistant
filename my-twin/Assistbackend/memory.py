"""Long-term semantic memory that links related chats (section 11 of README1).

Write path (background, after each reply):
    extract facts -> resolve aliases -> dedupe / supersede -> embed -> upsert
Read path (before each reply):
    expand aliases -> rewrite query + HyDE -> dense (Pinecone memory + chunks)
    + BM25 over facts -> RRF merge -> rerank -> recency boost -> token budget

Storage: Firestore `memories`, `chunks`, `aliases`, `entities`;
Pinecone index "twins" namespaces "memory" and "chunks" (routing vectors stay in
the default namespace, so they never mix). Every vector carries user_id.
"""
import hashlib
import math
import re
import threading
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from costs import log_usage
from llm import cheap_complete, cheap_json
from services import db, env_int, openai_client, pinecone_index

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIMS = env_int("EMBED_DIMS", 512)
MEMORY_TOKEN_BUDGET = env_int("MEMORY_TOKEN_BUDGET", 1200)
NS_MEMORY, NS_CHUNKS = "memory", "chunks"
DUPLICATE_SCORE = 0.90
SUPERSEDE_SCORE = 0.80
DENSE_MIN_SCORE = 0.30
LINK_SUMMARY_SCORE = 6.0  # rerank score (0-10) above which the source chat's summary is pulled in
MIN_RERANK_SCORE = 3.0
CACHE_TTL = 120

# ── Never store secrets ─────────────────────────────────────────────────────

SECRET_PATTERNS = [
    r"\bsk-[A-Za-z0-9_\-]{16,}",                       # OpenAI / Anthropic style keys
    r"\bAKIA[0-9A-Z]{16}\b",                           # AWS access key
    r"\bgh[pousr]_[A-Za-z0-9]{20,}",                   # GitHub tokens
    r"\bAIza[0-9A-Za-z_\-]{30,}",                      # Google API keys
    r"\bxox[abprs]-[A-Za-z0-9-]{10,}",                 # Slack tokens
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\b(?:\d[ -]?){13,19}\b",                         # card numbers
    r"\b[A-CEGHJ-PR-TW-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b",  # UK NI number
    r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b",               # IBAN
    r"\bsort code\b",
    r"\b(?:password|passcode|pin|api key|secret key|private key|access token)\b\s*(?:is|was|:|=)",
    r"\b(?:passport|driving licen[cs]e|account|card) (?:number|no\.?)\b",
]
_SECRET_RE = re.compile("|".join(SECRET_PATTERNS), re.IGNORECASE)


def contains_secret(text):
    return bool(_SECRET_RE.search(text or ""))


# ── Small helpers ───────────────────────────────────────────────────────────

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:80] or "x"


def _m(match, key, default=None):
    """Pinecone matches support both attribute and dict access depending on version."""
    if isinstance(match, dict):
        return match.get(key, default)
    return getattr(match, key, default)


def _matches(res):
    return (res.get("matches") if isinstance(res, dict) else getattr(res, "matches", None)) or []


_cache = {}
_cache_lock = threading.Lock()


def _cached(key, loader):
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
    value = loader()
    with _cache_lock:
        _cache[key] = (time.time(), value)
    return value


def _invalidate(user_id):
    with _cache_lock:
        for key in [k for k in _cache if k[1] == user_id]:
            _cache.pop(key, None)


# ── Embeddings and vector store ─────────────────────────────────────────────

def embed(texts, user_id=None):
    texts = [t if t.strip() else "." for t in texts]
    r = openai_client().embeddings.create(model=EMBED_MODEL, input=texts, dimensions=EMBED_DIMS)
    total = getattr(getattr(r, "usage", None), "total_tokens", 0) or 0
    log_usage(user_id, EMBED_MODEL, {"input_tokens": total}, feature="embeddings")
    return [d.embedding for d in r.data]


def _query(vec, user_id, namespace, top_k):
    res = pinecone_index().query(vector=vec, top_k=top_k, namespace=namespace,
                                 filter={"user_id": {"$eq": user_id}}, include_metadata=True)
    return _matches(res)


def _nearest(user_id, vec, namespace=NS_MEMORY):
    matches = _query(vec, user_id, namespace, 1)
    return matches[0] if matches else None


def _upsert(namespace, vid, vec, metadata):
    meta = {k: v for k, v in metadata.items() if v is not None}
    meta["text"] = (meta.get("text") or "")[:3000]
    pinecone_index().upsert(namespace=namespace, vectors=[{"id": vid, "values": vec, "metadata": meta}])


# ── Aliases and entities ────────────────────────────────────────────────────

def list_aliases(user_id):
    def load():
        try:
            docs = db().collection("aliases").where("user_id", "==", user_id).stream()
            return [d.to_dict() for d in docs]
        except Exception as e:
            print(f"Alias load failed: {e}")
            return []
    return _cached(("aliases", user_id), load)


def upsert_alias(user_id, name, refers_to):
    if not name or not refers_to or slug(name) == slug(refers_to):
        return
    db().collection("aliases").document(f"{user_id}_{slug(name)}").set(
        {"user_id": user_id, "name": name, "refers_to": refers_to, "updated_at": now_iso()}, merge=True)
    _invalidate(user_id)


def expand_aliases(user_id, message):
    """Append canonical names for any alias mentioned, so both spellings are searched."""
    extra = []
    lowered = (message or "").lower()
    for a in list_aliases(user_id):
        name, target = (a.get("name") or ""), (a.get("refers_to") or "")
        if name and re.search(rf"\b{re.escape(name.lower())}\b", lowered) and target.lower() not in lowered:
            extra.append(f"{name} = {target}")
        elif target and re.search(rf"\b{re.escape(target.lower())}\b", lowered) and name.lower() not in lowered:
            extra.append(f"{target} (also called {name})")
    return message + (f" [{'; '.join(extra)}]" if extra else "")


def list_entities(user_id):
    def load():
        try:
            docs = db().collection("entities").where("user_id", "==", user_id).stream()
            return [d.to_dict() for d in docs]
        except Exception as e:
            print(f"Entity load failed: {e}")
            return []
    return _cached(("entities", user_id), load)


def link_entities(user_id, names, conv_id):
    from firebase_admin import firestore
    for name in names or []:
        if not isinstance(name, str) or not name.strip():
            continue
        record = {"user_id": user_id, "name": name.strip(), "updated_at": now_iso()}
        if conv_id:
            record["conv_ids"] = firestore.ArrayUnion([conv_id])
        db().collection("entities").document(f"{user_id}_{slug(name)}").set(record, merge=True)
    _invalidate(user_id)


def _known_entities_text(user_id):
    names = []
    aliases = {}
    for a in list_aliases(user_id):
        aliases.setdefault(a.get("refers_to"), []).append(a.get("name"))
    for e in list_entities(user_id)[:150]:
        n = e.get("name")
        if n:
            names.append(n + (f" (aka {', '.join(aliases[n])})" if n in aliases else ""))
    return ", ".join(names) or "none yet"


# ── Facts ───────────────────────────────────────────────────────────────────

def list_facts(user_id):
    def load():
        try:
            docs = db().collection("memories").where("user_id", "==", user_id).limit(3000).stream()
            return [d.to_dict() | {"id": d.id} for d in docs]
        except Exception as e:
            print(f"Fact load failed: {e}")
            return []
    return _cached(("facts", user_id), load)


def _owned_fact(user_id, fact_id):
    ref = db().collection("memories").document(fact_id)
    snap = ref.get()
    if not snap.exists or (snap.to_dict() or {}).get("user_id") != user_id:
        return None, None
    return ref, snap.to_dict()


def save_fact(user_id, conv_id, fact, vec, source="chat"):
    fact_id = uuid.uuid4().hex
    created = now_iso()
    record = {
        "user_id": user_id, "text": fact["text"], "topic": fact.get("topic") or "",
        "entities": [e for e in (fact.get("entities") or []) if isinstance(e, str)],
        "conv_id": conv_id, "source": source, "created_at": created, "updated_at": created, "history": [],
    }
    db().collection("memories").document(fact_id).set(record)
    _upsert(NS_MEMORY, fact_id, vec, {
        "user_id": user_id, "text": record["text"], "topic": record["topic"],
        "entities": record["entities"], "conv_id": conv_id or "", "created_at": created, "kind": "fact"})
    _invalidate(user_id)
    return fact_id


def update_fact(user_id, fact_id, new_text, vec=None):
    """Newer wording wins; the old text is kept in history ("X (previously Y)")."""
    ref, current = _owned_fact(user_id, fact_id)
    if not ref or current.get("text") == new_text:
        return False
    from firebase_admin import firestore
    updated = now_iso()
    ref.update({
        "text": new_text, "updated_at": updated,
        "history": firestore.ArrayUnion([{"text": current.get("text"), "until": updated}]),
    })
    vec = vec or embed([new_text], user_id)[0]
    _upsert(NS_MEMORY, fact_id, vec, {
        "user_id": user_id, "text": new_text, "topic": current.get("topic") or "",
        "entities": current.get("entities") or [], "conv_id": current.get("conv_id") or "",
        "created_at": updated, "kind": "fact"})
    _invalidate(user_id)
    return True


def delete_fact(user_id, fact_id):
    ref, _ = _owned_fact(user_id, fact_id)
    if not ref:
        return False
    ref.delete()
    try:
        pinecone_index().delete(ids=[fact_id], namespace=NS_MEMORY)
    except Exception as e:
        print(f"Pinecone delete failed: {e}")
    _invalidate(user_id)
    return True


# ── Chunks (summaries, uploaded documents, passages) ───────────────────────

def split_text(text, size=1500, overlap=200):
    text = (text or "").strip()
    if len(text) <= size:
        return [text] if text else []
    out, start = [], 0
    while start < len(text):
        out.append(text[start:start + size])
        start += size - overlap
    return out


def index_chunk(user_id, conv_id, text, kind="passage", title=None):
    pieces = [p for p in split_text(text) if not contains_secret(p)]
    if not pieces:
        return []
    vecs = embed(pieces, user_id)
    ids = []
    for piece, vec in zip(pieces, vecs):
        cid = hashlib.sha256(f"{user_id}:{conv_id}:{kind}:{piece}".encode()).hexdigest()[:32]
        created = now_iso()
        db().collection("chunks").document(cid).set({
            "user_id": user_id, "conv_id": conv_id, "text": piece, "kind": kind,
            "title": title, "created_at": created})
        _upsert(NS_CHUNKS, cid, vec, {"user_id": user_id, "conv_id": conv_id or "", "text": piece,
                                      "kind": kind, "title": title, "created_at": created})
        ids.append(cid)
    return ids


# ── Write path ──────────────────────────────────────────────────────────────

EXTRACT_PROMPT = """From this exchange, extract durable facts about the user, their projects,
people, preferences and decisions. Ignore small talk, anything only true today, and the
assistant's general knowledge. Never include passwords, keys, card, bank or ID numbers.
Write each fact as one standalone sentence about the user ("Godwin's car sound app uses Flask").
Use the known entity names when the exchange refers to one of them in other words, and add an
alias when a new name refers to a known entity.
Return JSON: {{"facts":[{{"text":"...", "topic":"...", "entities":["..."], "supersedes":null}}],
"aliases":[{{"name":"...", "refers_to":"..."}}]}}
Set "supersedes" to the old fact's wording when the user corrects or changes something.
Return {{"facts":[],"aliases":[]}} when there is nothing worth keeping.

<exchange>{exchange}</exchange>
<known_entities>{entities}</known_entities>"""


def write_memory(user_id, conv_id, exchange, source="chat"):
    if not (exchange or "").strip():
        return []
    data = cheap_json(EXTRACT_PROMPT.format(exchange=exchange[:12000], entities=_known_entities_text(user_id)),
                      default={"facts": [], "aliases": []}, user_id=user_id, feature="memory_write")
    if not isinstance(data, dict):
        return []

    for a in data.get("aliases") or []:
        if isinstance(a, dict) and not contains_secret(f"{a.get('name')} {a.get('refers_to')}"):
            upsert_alias(user_id, a.get("name"), a.get("refers_to"))

    facts = [f for f in data.get("facts") or []
             if isinstance(f, dict) and isinstance(f.get("text"), str) and f["text"].strip()
             and not contains_secret(f["text"])]
    if not facts:
        return []

    vecs = embed([f["text"] for f in facts], user_id)
    written = []
    for fact, vec in zip(facts, vecs):
        link_entities(user_id, fact.get("entities"), conv_id)
        if fact.get("supersedes"):
            old = _nearest(user_id, embed([fact["supersedes"]], user_id)[0])
            if old and _m(old, "score", 0) > SUPERSEDE_SCORE:
                update_fact(user_id, _m(old, "id"), fact["text"], vec)
                written.append(_m(old, "id"))
                continue
        hit = _nearest(user_id, vec)
        if hit and _m(hit, "score", 0) > DUPLICATE_SCORE:
            update_fact(user_id, _m(hit, "id"), fact["text"], vec)
            written.append(_m(hit, "id"))
            continue
        written.append(save_fact(user_id, conv_id, fact, vec, source=source))
    return written


def write_memory_in_background(user_id, conv_id, user_text, reply):
    def run():
        try:
            write_memory(user_id, conv_id, f"User: {user_text}\nAssistant: {reply}")
        except Exception as e:
            print(f"Memory write failed: {e}")
    threading.Thread(target=run, daemon=True).start()


# ── Read path ───────────────────────────────────────────────────────────────

REWRITE_PROMPT = """Rewrite the user's latest message as a standalone search query about
their past conversations and projects. Resolve pronouns using the recent turns.
Also write one short sentence that a stored memory answering it might contain.
Return JSON: {{"query": "...", "hypothetical": "..."}}

<recent_turns>{recent}</recent_turns>
<message>{message}</message>"""

RERANK_PROMPT = """Score how useful each memory is for answering the user's query, 0 (irrelevant) to 10 (directly answers it).
Return JSON: {{"scores": [{{"i": 0, "score": 7}}, ...]}} with one entry per memory.

<query>{query}</query>
<memories>
{items}
</memories>"""

_TOKEN_RE = re.compile(r"[a-z0-9']+")
_STOP = {"the", "a", "an", "is", "it", "to", "of", "in", "on", "for", "and", "or", "what", "who",
         "how", "do", "you", "your", "me", "my", "i", "his", "her", "that", "this", "was", "with", "are"}


def tokenize(text):
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP and len(t) > 1]


def bm25_rank(query, docs, top_k=15, k1=1.5, b=0.75):
    """Okapi BM25 over [{"id","text",...}]. Returns the top docs that share at least one term."""
    q_terms = tokenize(query)
    if not q_terms or not docs:
        return []
    tokenised = [tokenize(d.get("text")) for d in docs]
    n = len(docs)
    avgdl = sum(len(t) for t in tokenised) / n or 1
    df = Counter()
    for toks in tokenised:
        df.update(set(toks))
    scored = []
    for doc, toks in zip(docs, tokenised):
        tf = Counter(toks)
        score = 0.0
        for term in q_terms:
            if term not in tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * len(toks) / avgdl))
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:top_k]]


def rrf_merge(result_lists, k=60):
    """Reciprocal Rank Fusion. Items are dicts with an "id"; first occurrence keeps its data."""
    scores, items = {}, {}
    for results in result_lists:
        for rank, item in enumerate(results):
            key = item["id"]
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            items.setdefault(key, item)
    ordered = sorted(scores.items(), key=lambda x: -x[1])
    return [items[i] | {"rrf": s} for i, s in ordered]


def apply_recency_boost(items, half_life_days=120, weight=0.75):
    """Newer facts win ties: add up to `weight` points, decaying with age."""
    now = datetime.now(timezone.utc)
    for item in items:
        boost = 0.0
        try:
            created = datetime.fromisoformat(str(item.get("created_at")).replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_days = max((now - created).total_seconds() / 86400, 0)
            boost = weight * 0.5 ** (age_days / half_life_days)
        except (TypeError, ValueError):
            pass
        item["score"] = float(item.get("score", 0)) + boost
    return sorted(items, key=lambda x: -x["score"])


def fit_to_budget(items, budget_tokens):
    out, used = [], 0
    for item in items:
        cost = len(item.get("text", "")) // 4 + 4
        if used + cost > budget_tokens:
            continue
        out.append(item)
        used += cost
    return out


def _candidate(match, ns):
    meta = _m(match, "metadata", {}) or {}
    return {"id": _m(match, "id"), "ns": ns, "text": meta.get("text", ""),
            "conv_id": meta.get("conv_id") or None, "created_at": meta.get("created_at"),
            "kind": meta.get("kind", "fact" if ns == NS_MEMORY else "passage"),
            "dense": _m(match, "score", 0)}


def rerank(query, candidates, user_id=None):
    if not candidates:
        return []
    items = "\n".join(f"[{i}] {c['text'][:500]}" for i, c in enumerate(candidates))
    data = cheap_json(RERANK_PROMPT.format(query=query, items=items), default={},
                      user_id=user_id, feature="memory_rerank")
    scores = {}
    for row in (data.get("scores") if isinstance(data, dict) else None) or []:
        try:
            scores[int(row["i"])] = float(row["score"])
        except (KeyError, TypeError, ValueError):
            continue
    if not scores:  # reranker failed: keep fused order with a neutral score
        return [c | {"score": 5.0 - i * 0.01} for i, c in enumerate(candidates)]
    ranked = [c | {"score": scores.get(i, 0.0)} for i, c in enumerate(candidates)]
    return sorted(ranked, key=lambda x: -x["score"])


def retrieve(user_id, message, recent="", k=8, current_conv_id=None):
    """Return up to k memory dicts ({"text", "score", ...}) relevant to `message`."""
    expanded = expand_aliases(user_id, message)
    rw = cheap_json(REWRITE_PROMPT.format(recent=recent[-3000:], message=expanded), default={},
                    user_id=user_id, feature="memory_rewrite")
    query = (rw.get("query") if isinstance(rw, dict) else None) or expanded
    hypothetical = (rw.get("hypothetical") if isinstance(rw, dict) else None) or query
    vecs = embed([query, hypothetical], user_id)

    jobs = [(vec, ns) for ns in (NS_MEMORY, NS_CHUNKS) for vec in vecs]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        results = list(pool.map(lambda j: _query(j[0], user_id, j[1], 15), jobs))
    dense = [[_candidate(m, ns) for m in matches if _m(m, "score", 0) > DENSE_MIN_SCORE]
             for (_, ns), matches in zip(jobs, results)]

    facts = [{"id": f["id"], "ns": NS_MEMORY, "text": f.get("text", ""), "conv_id": f.get("conv_id"),
              "created_at": f.get("updated_at") or f.get("created_at"), "kind": "fact"}
             for f in list_facts(user_id)]
    sparse = bm25_rank(f"{query} {expanded}", facts, top_k=15)

    fused = rrf_merge(dense + [sparse])[:20]
    ranked = apply_recency_boost(rerank(query, fused, user_id))
    ranked = [r for r in ranked if r["score"] >= MIN_RERANK_SCORE]

    # Link across chats: pull the summary of a strongly matching memory's source chat.
    linked, seen_convs = [], set()
    for r in ranked:
        conv = r.get("conv_id")
        if r["score"] >= LINK_SUMMARY_SCORE and conv and conv != current_conv_id and conv not in seen_convs:
            seen_convs.add(conv)
            summary = _conversation_summary(conv)
            if summary:
                linked.append({"id": f"summary:{conv}", "text": f"Summary of a related past chat: {summary}",
                               "score": r["score"] - 0.5, "kind": "linked_summary"})
        if len(seen_convs) >= 2:
            break

    selected = fit_to_budget(ranked[:k], MEMORY_TOKEN_BUDGET)
    used = sum(len(s["text"]) // 4 for s in selected)
    selected += fit_to_budget(linked, max(MEMORY_TOKEN_BUDGET - used, 0))
    return selected


def _conversation_summary(conv_id):
    try:
        snap = db().collection("conversations").document(conv_id).get()
        return ((snap.to_dict() or {}).get("summary") or "")[:1500] if snap.exists else ""
    except Exception:
        return ""


# ── Forgetting ──────────────────────────────────────────────────────────────

FORGET_RE = re.compile(r"^\s*(?:please\s+)?forget\s+(?:that\s+|about\s+)?(.+)$", re.IGNORECASE)
FORGET_PROMPT = """The user asked: "forget {request}".
Which of these stored facts should be deleted? Only pick facts that clearly match the request.
Return JSON: {{"delete": [indexes]}}

{items}"""


def forget_request(message):
    m = FORGET_RE.match(message or "")
    return m.group(1).strip(" .!?") if m else None


def forget_matching(user_id, request_text):
    vec = embed([request_text], user_id)[0]
    matches = [m for m in _query(vec, user_id, NS_MEMORY, 8) if _m(m, "score", 0) > DENSE_MIN_SCORE]
    candidates = [_candidate(m, NS_MEMORY) for m in matches]
    if not candidates:
        return []
    items = "\n".join(f"[{i}] {c['text']}" for i, c in enumerate(candidates))
    data = cheap_json(FORGET_PROMPT.format(request=request_text, items=items), default={},
                      user_id=user_id, feature="memory_forget")
    removed = []
    for i in (data.get("delete") if isinstance(data, dict) else None) or []:
        try:
            c = candidates[int(i)]
        except (IndexError, TypeError, ValueError):
            continue
        if delete_fact(user_id, c["id"]):
            removed.append(c["text"])
    return removed


# ── Backfill existing history ───────────────────────────────────────────────

SUMMARY_PROMPT = """Summarise this part of a conversation in compact bullet points (max 300 words).
Keep decisions, facts about the user, projects, file names, numbers and preferences. Drop filler.

<turns>{turns}</turns>"""


def sliding_windows(items, size=10, overlap=2):
    step = max(size - overlap, 1)
    for start in range(0, max(len(items) - overlap, 1), step):
        window = items[start:start + size]
        if window:
            yield window


def backfill(user_id, conv_id, size=10, overlap=2, log=print):
    from context import format_turns, load_unsummarised
    turns = load_unsummarised(conv_id, None)
    log(f"Backfilling {len(turns)} exchanges from {conv_id}")
    for n, window in enumerate(sliding_windows(turns, size, overlap), 1):
        text = format_turns(window)
        summary = cheap_complete(SUMMARY_PROMPT.format(turns=text[:20000]), user_id=user_id,
                                 feature="backfill", max_tokens=1000)
        if summary:
            index_chunk(user_id, conv_id, summary, kind="summary")
        write_memory(user_id, conv_id, text[:12000])
        log(f"  window {n} done")
