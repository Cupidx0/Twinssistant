"""Builds the request: cached system prompt + profile + summary, recent turns,
and a volatile final user block (date, memories, uploads, message).

Also owns the rolling conversation summary (section 10 of README1).
"""
import threading
from datetime import datetime

from llm import build_system, cheap_complete, mark_cached
from services import OWNER_UIDS, db, env_int

RECENT_TURNS = env_int("RECENT_TURNS", 8)
SUMMARY_TRIGGER_TOKENS = env_int("SUMMARY_TRIGGER_TOKENS", 6000)

# Byte-stable: no dates, names or per-request values here, or the cache misses.
SYSTEM_PROMPT = """You are Ashen, a personal AI assistant inside the Twinssistant app. You are sharp, intelligent and adaptive, not just a coding assistant. Most conversations are personal, practical or conversational.

How to behave:
- Respond directly to the current message first. Use context only when it strengthens the answer.
- Casual: respond like a smart friend, no unnecessary structure.
- Technical: be precise and concise. Format code in fenced blocks with the language name, with a brief explanation.
- Emotional or personal: be empathetic and grounded.
- Be direct. Do not over-explain or pad. Use plain conversational language unless code or structure is needed.
- Prefer tool results and web results over your training knowledge for anything current. Cite web sources by title when you use them.
- Use UK English spelling.

Tools:
- web_search for anything current, news, prices, lyrics, people or facts you are unsure of.
- search_memory when the user refers to something from a past chat that the provided memories do not cover.
- Calendar tools to read or add events; confirm what you added.
- laptop_action only when the user explicitly asks you to do something on their Mac.
- job_search for job listings.

Memory:
- <relevant_memories> in the user's message are facts recalled from past chats. Use them only when they change the answer.
- Do not mention that you have a memory system. If memories conflict, trust the newest.
- For outfit or fashion advice, check the profile and memories for sex, age, height, weight and skin tone; ask for anything missing.

Artifacts:
- When producing a complete runnable HTML page (or a single-file React demo using CDN scripts), wrap it in <artifact type="html" title="Short title"> ... </artifact> so the app can show it in a preview panel. Do not wrap ordinary code snippets.

Voice:
- When the message says voice mode is on, reply in natural spoken sentences with no markdown, lists or code.

You were built by the user and are still evolving."""

OWNER_DEFAULT_PROFILE = """Name: Godwin Alamu
- Developer learning Python, React and DSA
- Targeting apprenticeships and junior roles
- Built this assistant, so he knows how it works"""


def conversation_id_for(user_id, data):
    conv = (data or {}).get("conversation_id")
    if isinstance(conv, str) and conv.strip() and "/" not in conv:
        return conv.strip()
    return f"user_{user_id}"


# ── Profile ─────────────────────────────────────────────────────────────────

def load_profile(user_id):
    try:
        snap = db().collection("users").document(user_id).get()
        profile = (snap.to_dict() or {}).get("profile") if snap.exists else None
    except Exception as e:
        print(f"Profile load failed: {e}")
        profile = None
    return profile or {}


def profile_text(user_id):
    profile = load_profile(user_id)
    if not profile:
        return OWNER_DEFAULT_PROFILE if user_id in OWNER_UIDS else "No profile saved yet."
    lines = []
    for key in sorted(profile):
        value = profile[key]
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        if value:
            lines.append(f"{key.replace('_', ' ').title()}: {value}")
    return "\n".join(lines) or "No profile saved yet."


def save_profile(user_id, profile):
    db().collection("users").document(user_id).set({"profile": profile}, merge=True)


# ── Conversation history ────────────────────────────────────────────────────

def _conv_ref(conv_id):
    return db().collection("conversations").document(conv_id)


def get_summary(conv_id):
    try:
        snap = _conv_ref(conv_id).get()
        data = (snap.to_dict() or {}) if snap.exists else {}
    except Exception as e:
        print(f"Summary load failed: {e}")
        data = {}
    return data.get("summary", ""), data.get("summary_covered_until")


def load_recent_turns(conv_id, n=RECENT_TURNS):
    """Last n exchanges, oldest first. Each doc holds one user/assistant pair."""
    from firebase_admin import firestore
    try:
        q = (_conv_ref(conv_id).collection("messages")
             .order_by("clienttimestamp", direction=firestore.Query.DESCENDING).limit(n))
        docs = [d.to_dict() | {"id": d.id} for d in q.stream()]
    except Exception as e:
        print(f"History load failed: {e}")
        return []
    return list(reversed(docs))


def load_unsummarised(conv_id, covered_until):
    try:
        q = _conv_ref(conv_id).collection("messages").order_by("clienttimestamp")
        if covered_until:
            q = q.where("clienttimestamp", ">", covered_until)
        return [d.to_dict() | {"id": d.id} for d in q.stream()]
    except Exception as e:
        print(f"History load failed: {e}")
        return []


def turns_to_messages(turns):
    """Firestore exchanges -> alternating user/assistant messages (text only, byte-stable)."""
    messages = []
    for t in turns:
        user, assistant = (t.get("user") or "").strip(), (t.get("assistant") or "").strip()
        if not user or not assistant:
            continue
        messages.append({"role": "user", "content": user})
        messages.append({"role": "assistant", "content": assistant})
    return messages


def format_turns(turns):
    return "\n\n".join(f"User: {t.get('user', '')}\nAssistant: {t.get('assistant', '')}" for t in turns)


def estimate_tokens(text):
    return len(text or "") // 4


# ── Rolling summaries ───────────────────────────────────────────────────────

SUMMARY_PROMPT = """Update the running summary of this conversation.
Keep: decisions made, facts about the user, open tasks, code/file names, numbers, preferences.
Drop: greetings, filler, repeated content.
Write in compact bullet points. Max 400 words.

<previous_summary>{old}</previous_summary>
<new_turns>{turns}</new_turns>"""


def maybe_summarise(user_id, conv_id):
    summary, covered_until = get_summary(conv_id)
    turns = load_unsummarised(conv_id, covered_until)
    if len(turns) <= RECENT_TURNS:
        return
    if estimate_tokens(format_turns(turns)) < SUMMARY_TRIGGER_TOKENS:
        return
    old_part = turns[:-RECENT_TURNS]
    new_summary = cheap_complete(
        SUMMARY_PROMPT.format(old=summary or "", turns=format_turns(old_part)),
        user_id=user_id, feature="summary", max_tokens=1500)
    if not new_summary:
        return
    from firebase_admin import firestore
    _conv_ref(conv_id).set({
        "summary": new_summary,
        "summary_covered_until": old_part[-1].get("clienttimestamp"),
        "updated_at": firestore.SERVER_TIMESTAMP,
    }, merge=True)
    try:
        import memory
        memory.index_chunk(user_id, conv_id, new_summary, kind="summary")
    except Exception as e:
        print(f"Summary indexing failed: {e}")


def summarise_in_background(user_id, conv_id):
    def run():
        try:
            maybe_summarise(user_id, conv_id)
        except Exception as e:
            print(f"Summarisation failed: {e}")
    threading.Thread(target=run, daemon=True).start()


# ── Request assembly ────────────────────────────────────────────────────────

def build_user_block(message, memories=None, extra_context=None, voice=False):
    now = datetime.now()
    parts = [f"<context>\nNow: {now.strftime('%A %d %B %Y, %H:%M')}"]
    if voice:
        parts.append("Voice mode is on.")
    if memories:
        parts.append("<relevant_memories>\n" + "\n".join(f"- {m['text']}" for m in memories)
                     + "\n</relevant_memories>")
    for name, value in (extra_context or {}).items():
        if value:
            parts.append(f"<{name}>\n{value}\n</{name}>")
    parts.append("</context>")
    return "\n".join(parts) + "\n\n" + message


def build_request(user_id, conv_id, message, memories=None, upload_blocks=None,
                  extra_context=None, voice=False, turns=None):
    """Returns (system_blocks, messages). `turns` are preloaded recent exchanges."""
    summary, _ = get_summary(conv_id)
    system = build_system(SYSTEM_PROMPT, profile_text(user_id), summary)

    history = turns_to_messages(turns if turns is not None else load_recent_turns(conv_id))
    if history:
        # End of the shared, unchanging portion: next turn reads up to here from cache.
        mark_cached(history[-1])

    content = list(upload_blocks or [])
    content.append({"type": "text", "text": build_user_block(message, memories, extra_context, voice)})
    return system, history + [{"role": "user", "content": content}]
