# Twinssistant Upgrade Guide: Claude-Level Chat, Memory, Writing and Assessment

This README covers every change needed to bring Twinssistant (Flask + Flask-SocketIO + React + Firestore + Pinecone, multi-provider: Anthropic / OpenAI / Gemini) up to the standard of the Claude app while paying per token through the APIs instead of a subscription.

It is written for the current stack:

- Backend: Flask, Flask-SocketIO (threading async mode), Python
- Frontend: React (Vite)
- Storage: Firebase / Firestore (`conversations/{id}/messages/{id}`)
- Vector store: Pinecone index `twins` (AWS, 512 dims, cosine, OpenAI `text-embedding-3-small`)
- Router: Pinecone vector search, then keyword fallback, then GPT-4o-mini with Tavily at confidence 0.7
- Voice: Whisper STT, Porcupine "Hey Ashen" wake word, ElevenLabs TTS with gTTS and browser fallbacks

> Prices and model IDs below were correct as of November 2026. Check the official pricing pages before relying on them.

---

## Contents

1. [Goals](#1-goals)
2. [Architecture after the upgrade](#2-architecture-after-the-upgrade)
3. [Setup: dependencies and environment](#3-setup-dependencies-and-environment)
4. [Build order checklist](#4-build-order-checklist)
5. [Streaming responses](#5-streaming-responses)
6. [Prompt caching](#6-prompt-caching)
7. [Markdown and code rendering](#7-markdown-and-code-rendering)
8. [Difficulty-based model routing](#8-difficulty-based-model-routing)
9. [Tool use loop](#9-tool-use-loop)
10. [Context management: rolling summaries](#10-context-management-rolling-summaries)
11. [Long-term memory that links related chats](#11-long-term-memory-that-links-related-chats)
12. [File and image uploads](#12-file-and-image-uploads)
13. [Artifacts panel](#13-artifacts-panel)
14. [Extended thinking toggle](#14-extended-thinking-toggle)
15. [Cost logging and dashboard](#15-cost-logging-and-dashboard)
16. [Writing pipeline](#16-writing-pipeline)
17. [Assessment and grading pipeline](#17-assessment-and-grading-pipeline)
18. [Firestore schema](#18-firestore-schema)
19. [Testing and calibration](#19-testing-and-calibration)
20. [Cost expectations](#20-cost-expectations)
21. [Security notes](#21-security-notes)
22. [Final checklist](#22-final-checklist)

---

## 1. Goals

| Goal | How |
|---|---|
| Feel as fast as Claude | Token streaming over Socket.IO |
| Cost less than Claude Pro (£18/month) | Prompt caching, cheap-model routing, cost logging |
| Act like an agent, not a chatbot | Native tool use loop |
| Never lose context in long chats | Rolling summaries instead of a hard sliding window |
| Remember across chats, even when worded differently | Semantic memory: embeddings, query rewriting, hybrid search, reranking, aliases |
| Write at Claude quality | Plan, draft, critique, revise pipeline with house style rules |
| Grade work honestly | Rubric-based structured grading with evidence and extended thinking |

---

## 2. Architecture after the upgrade

```
React (Vite)
  ├─ Chat view (streaming markdown, code blocks, copy buttons)
  ├─ Artifacts panel (sandboxed iframe)
  ├─ Upload button (images, PDFs, docx)
  ├─ Toggles: model override, "think harder"
  └─ Cost dashboard
        │  Socket.IO (stream tokens)  +  REST (uploads, history, costs)
        ▼
Flask + Flask-SocketIO (threading)
  ├─ router.py        → intent (existing 3-tier) + difficulty → model choice
  ├─ context.py       → system prompt + profile + memories + summary + recent turns
  ├─ memory.py        → write path (extract, embed, dedupe) / read path (rewrite, hybrid search, rerank)
  ├─ llm.py           → provider adapters, streaming, caching, thinking, usage capture
  ├─ tools.py         → tool schemas + dispatcher (Tavily, laptop_tools, job agent, memory search)
  ├─ pipelines/
  │    ├─ writing.py  → plan → draft → critique → revise
  │    └─ grading.py  → rubric → structured JSON assessment
  └─ costs.py         → per-request token and £ logging
        │
        ▼
Firestore (conversations, messages, summaries, memories, profile, aliases, usage)
Pinecone index "twins" (namespaces: "routing", "memory", "chunks")
```

---

## 3. Setup: dependencies and environment

### Backend

```bash
pip install --upgrade anthropic openai google-genai flask flask-socketio flask-cors \
  firebase-admin pinecone tavily-python pypdf python-docx rank-bm25 tiktoken
```

### Frontend

```bash
npm install react-markdown remark-gfm rehype-highlight highlight.js socket.io-client
```

### `.env`

```env
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GEMINI_API_KEY=
TAVILY_API_KEY=
PINECONE_API_KEY=
PINECONE_INDEX=twins
ELEVENLABS_API_KEY=
FIREBASE_CREDENTIALS=./serviceAccount.json

# Models
MODEL_CHEAP=claude-haiku-5-5
MODEL_MAIN=claude-sonnet-5-5
MODEL_TOP=claude-opus-5-5
EMBED_MODEL=text-embedding-3-small
EMBED_DIMS=512

# Budgets
MONTHLY_BUDGET_GBP=12
USD_TO_GBP=0.76
RECENT_TURNS=8
SUMMARY_TRIGGER_TOKENS=6000
MEMORY_TOKEN_BUDGET=1200
```

Never commit `.env` or `serviceAccount.json`. Add both to `.gitignore`.

---

## 4. Build order checklist

Build in this order. Each step is usable on its own.

- [ ] 1. Cost logging (so every later change is measured)
- [ ] 2. Streaming
- [ ] 3. Prompt caching
- [ ] 4. Markdown and code rendering
- [ ] 5. Difficulty-based routing
- [ ] 6. Rolling summaries
- [ ] 7. Long-term semantic memory
- [ ] 8. Tool use loop
- [ ] 9. Uploads
- [ ] 10. Extended thinking toggle
- [ ] 11. Writing pipeline
- [ ] 12. Assessment pipeline
- [ ] 13. Artifacts panel
- [ ] 14. Calibration tests

---

## 5. Streaming responses

**Why:** the biggest improvement in perceived speed. Users see the first words in under a second instead of waiting for the whole reply.

### Backend (`llm.py`)

```python
import anthropic
from flask_socketio import emit

client = anthropic.Anthropic()

def stream_claude(sid, model, system, messages, tools=None, thinking=None, max_tokens=4096):
    kwargs = dict(model=model, system=system, messages=messages, max_tokens=max_tokens)
    if tools:
        kwargs["tools"] = tools
    if thinking:
        kwargs["thinking"] = thinking

    with client.messages.stream(**kwargs) as stream:
        for event in stream:
            if event.type == "content_block_delta":
                if event.delta.type == "text_delta":
                    socketio.emit("token", {"text": event.delta.text}, to=sid)
                elif event.delta.type == "thinking_delta":
                    socketio.emit("thinking", {"text": event.delta.thinking}, to=sid)
        final = stream.get_final_message()

    socketio.emit("done", {"stop_reason": final.stop_reason}, to=sid)
    return final  # contains .content and .usage for cost logging
```

OpenAI equivalent: `client.chat.completions.create(..., stream=True, stream_options={"include_usage": True})` and emit `chunk.choices[0].delta.content`.

Gemini equivalent: `client.models.generate_content_stream(...)` and emit `chunk.text`.

### Frontend

```jsx
useEffect(() => {
  socket.on("token", ({ text }) =>
    setMessages(m => {
      const last = m[m.length - 1];
      return [...m.slice(0, -1), { ...last, content: last.content + text }];
    })
  );
  socket.on("done", () => setStreaming(false));
  return () => { socket.off("token"); socket.off("done"); };
}, []);
```

### Voice

Do not wait for the full reply before TTS. Buffer tokens until a sentence ends (`.`, `?`, `!`), then send that sentence to ElevenLabs WebSocket. Keep the gTTS and browser fallbacks.

---

## 6. Prompt caching

**Why:** the system prompt, profile, memories and older history are resent every turn. Cache reads cost about a tenth of normal input (or less on 5.5 models), so long chats get much cheaper.

### Rules

- Put stable content first: system prompt, then profile, then tools, then summary, then recent turns.
- Mark the end of the stable part with `cache_control`.
- Mark the last message too, so the growing history is cached turn by turn.
- Cache lifetime is short (minutes), so it helps most during active conversations.

```python
def build_system(system_prompt, profile_text, summary_text):
    return [
        {"type": "text", "text": system_prompt},
        {"type": "text", "text": f"<user_profile>\n{profile_text}\n</user_profile>",
         "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": f"<conversation_summary>\n{summary_text}\n</conversation_summary>"},
    ]

def mark_last_message_cached(messages):
    last = messages[-1]
    if isinstance(last["content"], str):
        last["content"] = [{"type": "text", "text": last["content"]}]
    last["content"][-1]["cache_control"] = {"type": "ephemeral"}
    return messages
```

Memories retrieved per turn change every turn, so place them after the cached block (in the final user message), not inside it.

OpenAI caches long prompt prefixes automatically. Keep the prefix identical between calls to benefit.

---

## 7. Markdown and code rendering

```jsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";

function CodeBlock({ inline, className, children }) {
  const code = String(children).replace(/\n$/, "");
  if (inline) return <code className={className}>{children}</code>;
  return (
    <div className="code-wrap">
      <button onClick={() => navigator.clipboard.writeText(code)}>Copy</button>
      <pre><code className={className}>{children}</code></pre>
    </div>
  );
}

export function Message({ content }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}
      components={{ code: CodeBlock }}>
      {content}
    </ReactMarkdown>
  );
}
```

---

## 8. Difficulty-based model routing

Keep the existing three-tier intent classifier. Add a second dimension: difficulty.

| Intent / difficulty | Model |
|---|---|
| Small talk, quick facts, laptop commands | Haiku 5.5 (or GPT-4o-mini / Gemini Flash) |
| Normal coding help, explanations, summaries | Sonnet 5.5 |
| Writing, assessment, architecture, long debugging | Sonnet 5.5 with thinking, or Opus 5.5 |
| Memory extraction, query rewriting, reranking | Haiku 5.5 |

```python
HARD_INTENTS = {"writing", "assessment", "cv", "architecture"}

def choose_model(intent, text, user_override=None, think=False):
    if user_override:
        return user_override
    if intent in HARD_INTENTS or think:
        return os.getenv("MODEL_MAIN")  # escalate to MODEL_TOP if the user asks
    long_or_code = len(text) > 1500 or "```" in text or "traceback" in text.lower()
    if long_or_code:
        return os.getenv("MODEL_MAIN")
    return os.getenv("MODEL_CHEAP")
```

Add a model picker in the UI so you can override per message.

**Budget guard:** if this month's spend passes `MONTHLY_BUDGET_GBP`, downgrade everything except writing and assessment to the cheap model and show a banner.

---

## 9. Tool use loop

**Why:** lets the model decide when to search, call laptop tools, query memory or run the job agent, then keep going until it has an answer.

### Tool definitions (`tools.py`)

```python
TOOLS = [
    {"name": "web_search", "description": "Search the web for current information.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}},
                      "required": ["query"]}},
    {"name": "search_memory", "description": "Search past conversations and saved facts about the user, including topics phrased differently.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}},
                      "required": ["query"]}},
    {"name": "laptop_action", "description": "Run an approved laptop action from laptop_tools.py.",
     "input_schema": {"type": "object", "properties": {
         "action": {"type": "string"}, "args": {"type": "object"}}, "required": ["action"]}},
    {"name": "job_search", "description": "Search Job Swipr and job boards for roles.",
     "input_schema": {"type": "object", "properties": {
         "role": {"type": "string"}, "location": {"type": "string"}}, "required": ["role"]}},
]

def run_tool(name, args, user_id):
    if name == "web_search":
        return tavily.search(args["query"], max_results=5)
    if name == "search_memory":
        return memory.retrieve(user_id, args["query"], k=6)
    if name == "laptop_action":
        return laptop_tools.dispatch(args["action"], args.get("args", {}))
    if name == "job_search":
        return job_agent.search(**args)
    return {"error": f"unknown tool {name}"}
```

### The loop

```python
def agent_turn(sid, user_id, model, system, messages, max_steps=6):
    for _ in range(max_steps):
        resp = stream_claude(sid, model, system, messages, tools=TOOLS)
        log_usage(user_id, model, resp.usage)
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            return resp

        results = []
        for block in resp.content:
            if block.type == "tool_use":
                socketio.emit("tool", {"name": block.name, "input": block.input}, to=sid)
                out = run_tool(block.name, block.input, user_id)
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": json.dumps(out)[:20000]})
        messages.append({"role": "user", "content": results})
    return resp
```

Rules:

- Cap steps (6) and truncate tool output so a loop cannot burn money.
- Laptop actions that change things (delete, send, install) need a confirmation event to the UI before running.
- Show tool calls in the UI as small status chips ("Searching the web...").

---

## 10. Context management: rolling summaries

**Problem:** the current sliding window drops old turns completely.

**Fix:** keep the last `RECENT_TURNS` turns verbatim, and fold everything older into a running summary stored on the conversation.

```python
SUMMARY_PROMPT = """Update the running summary of this conversation.
Keep: decisions made, facts about the user, open tasks, code/file names, numbers, preferences.
Drop: greetings, filler, repeated content.
Write in compact bullet points. Max 400 words.

<previous_summary>{old}</previous_summary>
<new_turns>{turns}</new_turns>"""

def maybe_summarise(conv_id):
    msgs = load_messages(conv_id)
    if count_tokens(msgs) < int(os.getenv("SUMMARY_TRIGGER_TOKENS")):
        return
    old_part, recent = msgs[:-RECENT_TURNS], msgs[-RECENT_TURNS:]
    old_summary = get_summary(conv_id)
    new_summary = cheap_complete(SUMMARY_PROMPT.format(
        old=old_summary, turns=format_turns(old_part)))
    save_summary(conv_id, new_summary, covered_until=old_part[-1]["id"])
    index_chunk(conv_id, new_summary)   # feeds long-term memory, see section 11
```

Run `maybe_summarise` in a background thread after each reply so it never slows the user down.

---

## 11. Long-term memory that links related chats

This is the core of "remember data from previous chats, even if the way it is typed is different".

Keyword-tag retrieval fails when wording changes ("my car noise app" vs "the mechanic sound thing"). The fix is **meaning-based** retrieval plus several safety nets.

### 11.1 What gets stored

| Type | What | Where |
|---|---|---|
| **Profile** | Stable facts: name, course, location, career goal, preferences | Firestore `users/{uid}/profile` (always injected, cached) |
| **Facts** | Atomic statements extracted from chats ("Uses Flask-SocketIO threading mode") | Firestore `memories` + Pinecone namespace `memory` |
| **Chunks** | Conversation summaries and important passages | Firestore `chunks` + Pinecone namespace `chunks` |
| **Aliases** | Different names for the same thing ("Hey Ashen" = Twinssistant) | Firestore `aliases` |
| **Raw messages** | Full history | Firestore `conversations/{id}/messages/{id}` (existing) |

Use the existing `twins` index with separate **namespaces** (`routing`, `memory`, `chunks`) so routing vectors and memory vectors never mix. Keep 512 dims:

```python
def embed(texts):
    r = openai_client.embeddings.create(model="text-embedding-3-small",
                                        input=texts, dimensions=512)
    return [d.embedding for d in r.data]
```

### 11.2 Write path (after every reply, in the background)

1. **Extract facts** with a cheap model.
2. **Resolve aliases** so new names attach to existing projects.
3. **Deduplicate**: if a near-identical fact exists, update it instead of adding a new one.
4. **Embed and upsert** to Pinecone with metadata.

```python
EXTRACT_PROMPT = """From this exchange, extract durable facts about the user, their projects,
people, preferences and decisions. Ignore small talk and anything only true today.
Return JSON: {"facts":[{"text":..., "topic":..., "entities":[...], "supersedes":null|"old fact text"}],
"aliases":[{"name":..., "refers_to":...}]}

<exchange>{exchange}</exchange>
<known_entities>{entities}</known_entities>"""

def write_memory(user_id, conv_id, exchange):
    known = list_entities(user_id)
    data = cheap_json(EXTRACT_PROMPT.format(exchange=exchange, entities=known))

    for a in data["aliases"]:
        upsert_alias(user_id, a["name"], a["refers_to"])

    for f in data["facts"]:
        vec = embed([f["text"]])[0]
        hit = index.query(vector=vec, top_k=1, namespace="memory",
                          filter={"user_id": user_id}, include_metadata=True)
        if hit.matches and hit.matches[0].score > 0.90:
            update_fact(hit.matches[0].id, f["text"])   # newer wording wins, keep history
            continue
        fact_id = save_fact(user_id, conv_id, f)
        index.upsert(namespace="memory", vectors=[{
            "id": fact_id, "values": vec,
            "metadata": {"user_id": user_id, "text": f["text"], "topic": f["topic"],
                         "entities": f["entities"], "conv_id": conv_id,
                         "created_at": now_iso()}}])
```

### 11.3 Read path (before every reply)

This is what makes differently worded questions find the right memories.

1. **Expand aliases** in the user's message ("Hey Ashen" also searches "Twinssistant").
2. **Rewrite the query** using recent turns, so "how's that going?" becomes "status of the car sound diagnosis app".
3. **Generate a hypothetical answer** (HyDE): embed what a matching memory would look like, which links paraphrases far better than embedding the question alone.
4. **Hybrid search:** dense vectors (Pinecone, both namespaces) plus keyword BM25 over Firestore facts, merged with Reciprocal Rank Fusion.
5. **Rerank** the top 20 with a cheap model and keep the best that fit in `MEMORY_TOKEN_BUDGET`.
6. **Recency boost** so newer facts beat stale ones on ties.

```python
REWRITE_PROMPT = """Rewrite the user's latest message as a standalone search query about
their past conversations and projects. Resolve pronouns using the recent turns.
Also write one short sentence that a stored memory answering it might contain.
Return JSON: {"query": ..., "hypothetical": ...}

<recent_turns>{recent}</recent_turns>
<message>{message}</message>"""

def retrieve(user_id, message, recent="", k=8):
    message = expand_aliases(user_id, message)
    rw = cheap_json(REWRITE_PROMPT.format(recent=recent, message=message))
    vecs = embed([rw["query"], rw["hypothetical"]])

    dense = []
    for ns in ("memory", "chunks"):
        for v in vecs:
            res = index.query(vector=v, top_k=15, namespace=ns,
                              filter={"user_id": user_id}, include_metadata=True)
            dense.append([m for m in res.matches if m.score > 0.30])

    sparse = bm25_search(user_id, rw["query"], top_k=15)   # rank_bm25 over fact texts

    fused = rrf_merge(dense + [sparse], k=60)[:20]
    ranked = rerank(rw["query"], fused)                     # cheap model scores 0-10
    ranked = apply_recency_boost(ranked)
    return fit_to_budget(ranked, int(os.getenv("MEMORY_TOKEN_BUDGET")))[:k]

def rrf_merge(result_lists, k=60):
    scores = {}
    for results in result_lists:
        for rank, item in enumerate(results):
            key = item.id if hasattr(item, "id") else item["id"]
            scores[key] = scores.get(key, 0) + 1 / (k + rank + 1)
    return [load_memory(i) for i, _ in sorted(scores.items(), key=lambda x: -x[1])]
```

### 11.4 Injecting memories

Put retrieved memories inside the final user message, not the cached system prompt:

```python
user_block = f"""<relevant_memories>
{chr(10).join('- ' + m['text'] for m in memories)}
</relevant_memories>

{user_message}"""
```

System prompt rule: *"Use relevant memories only when they change the answer. Do not mention that you have a memory system. If memories conflict, trust the newest."*

The model also has the `search_memory` tool (section 9), so it can look further when the automatic retrieval missed something.

### 11.5 Linking across chats

- Every fact and chunk stores `conv_id` and `entities`.
- When a retrieved memory matches, also pull the summary of its source conversation if the score is high (> 0.6). This brings in surrounding context, not just one line.
- Maintain an `entities` collection (project, person, topic) with aliases. New chats that mention an entity get linked to it automatically during the write path.

### 11.6 Memory management

- **Corrections:** facts with `supersedes` replace the old fact, keeping history ("PM on infra team (previously search)").
- **Forgetting:** a "forget X" command deletes the fact from Firestore and Pinecone.
- **Never store:** passwords, API keys, bank or card numbers, ID numbers. Filter these with regex before saving.
- **Viewer:** a settings page listing saved facts, with edit and delete buttons.

### 11.7 Backfill existing history

Run once to index the history already migrated from `chat_history.txt` into Firestore:

```python
for conv in all_conversations(user_id):
    msgs = load_messages(conv.id)
    for window in sliding_windows(msgs, size=10, overlap=2):
        summary = cheap_complete(SUMMARY_PROMPT.format(old="", turns=format_turns(window)))
        index_chunk(conv.id, summary)
        write_memory(user_id, conv.id, format_turns(window))
```

---

## 12. File and image uploads

```python
@app.post("/api/upload")
def upload():
    f = request.files["file"]
    name, data = f.filename, f.read()
    if name.lower().endswith(".pdf"):
        block = {"type": "document", "source": {"type": "base64",
                 "media_type": "application/pdf", "data": b64(data)}}
    elif name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        block = {"type": "image", "source": {"type": "base64",
                 "media_type": f.mimetype, "data": b64(data)}}
    elif name.lower().endswith(".docx"):
        text = "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)
        block = {"type": "text", "text": f"<file name='{name}'>\n{text}\n</file>"}
    else:
        block = {"type": "text", "text": f"<file name='{name}'>\n{data.decode(errors='ignore')}\n</file>"}
    upload_id = save_upload(name, block)
    return {"upload_id": upload_id}
```

The frontend sends `upload_ids` with the next message. The backend inserts those blocks before the user's text.

- Set a size limit (for example 20 MB) and reject other types.
- Large PDFs: extract text with `pypdf` and chunk them into memory (`chunks` namespace) instead of resending them every turn.

---

## 13. Artifacts panel

When the model returns a complete HTML page or React component, show it in a side panel.

System prompt rule: *"When producing a full runnable HTML page, wrap it in <artifact type="html" title="..."> ... </artifact>."*

```jsx
function ArtifactPanel({ html }) {
  return (
    <iframe title="artifact" sandbox="allow-scripts" srcDoc={html}
      style={{ width: "100%", height: "100%", border: 0 }} />
  );
}
```

- Use `sandbox="allow-scripts"` only. Never add `allow-same-origin`, so artifact code cannot read your app's cookies or tokens.
- Save artifacts in Firestore with versions so you can go back.

---

## 14. Extended thinking toggle

Add a "Think harder" switch in the UI. Use it for assessment, hard debugging and planning.

```python
thinking = {"type": "enabled", "budget_tokens": 8000} if think else None
resp = stream_claude(sid, model, system, messages, thinking=thinking, max_tokens=16000)
```

- `max_tokens` must be larger than `budget_tokens`.
- Thinking tokens are billed as output, so leave it off by default.
- Stream `thinking_delta` into a collapsible "Thinking" section in the UI.
- Check the current docs for your exact model, as newer models may use adaptive thinking settings.

---

## 15. Cost logging and dashboard

```python
PRICES_USD_PER_MTOK = {   # input, output, cache_read, cache_write
    "claude-haiku-5-5":  (0.10, 0.50, 0.01, 0.125),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-opus-5-5":   (4.00, 20.00, 0.20, 5.00),
}  # verify against the official pricing page

def log_usage(user_id, model, u, feature="chat"):
    p_in, p_out, p_cr, p_cw = PRICES_USD_PER_MTOK[model]
    cr = getattr(u, "cache_read_input_tokens", 0) or 0
    cw = getattr(u, "cache_creation_input_tokens", 0) or 0
    usd = (u.input_tokens * p_in + u.output_tokens * p_out + cr * p_cr + cw * p_cw) / 1e6
    db.collection("usage").add({
        "user_id": user_id, "model": model, "feature": feature,
        "input": u.input_tokens, "output": u.output_tokens,
        "cache_read": cr, "cache_write": cw,
        "usd": usd, "gbp": usd * float(os.getenv("USD_TO_GBP")),
        "ts": firestore.SERVER_TIMESTAMP})
```

Also log non-LLM services: ElevenLabs characters, Whisper minutes, Tavily searches, embeddings.

**Dashboard:** `/api/costs?range=month` returns totals by day, model and feature. Show this month's £ total against £18 (Claude Pro) as a progress bar.

---

## 16. Writing pipeline

Use for essays, reports, coursework drafts, cover letters and CVs.

### House style (inject into every writing call)

```text
- UK English spelling.
- No em dashes anywhere. Use commas, colons or full stops instead.
- Harvard referencing:
  Book: Surname, Initial. (Year) *Title*. Edition. Publisher.
  Website: Author/Organisation (Year) Title. [online] Available at: URL [Accessed: Month Year].
- Cite only sources provided in <sources>. Never invent a reference.
- Clear, direct sentences. No filler openings. No repeated points.
- Match the voice of <writing_samples>.
```

Store 2 or 3 samples of your own past writing in Firestore (`users/{uid}/writing_samples`) and inject them.

### Pipeline (`pipelines/writing.py`)

```python
def write_document(brief, criteria, word_count, user_id):
    sources = gather_sources(brief)                 # Tavily: real URLs, titles, authors, years

    plan = main_complete(f"""Create an outline that maps every section to the assessment criteria.
<brief>{brief}</brief><criteria>{criteria}</criteria><sources>{sources}</sources>
Target length: {word_count} words. Return JSON with sections, criteria_covered, word_budget.""")

    sections = []
    for s in plan["sections"]:
        sections.append(main_complete(f"""{HOUSE_STYLE}
Write the section "{s['title']}" ({s['word_budget']} words), covering {s['criteria_covered']}.
<previous_sections>{summarise(sections)}</previous_sections>
<sources>{sources}</sources>"""))
    draft = "\n\n".join(sections)

    critique = main_complete(f"""Act as a strict examiner. Compare the draft to the brief and criteria.
List: unmet criteria, weak evidence, unsupported claims, style rule breaks (em dashes,
US spelling, referencing format), repetition, word count issues. Be specific with quotes.
<brief>{brief}</brief><criteria>{criteria}</criteria><draft>{draft}</draft>""",
        thinking=True)

    final = main_complete(f"""{HOUSE_STYLE}
Revise the draft to fix every issue in the critique. Keep what already works.
<critique>{critique}</critique><draft>{draft}</draft><sources>{sources}</sources>""")

    final = final.replace("\u2014", ", ").replace("\u2013", "-")   # hard guard against em/en dashes
    return {"plan": plan, "draft": draft, "critique": critique, "final": final}
```

Writing every section separately keeps long documents sharp. The critique and revise passes give the biggest jump in quality.

---

## 17. Assessment and grading pipeline

### Input

- The full assignment brief
- Pearson criteria per learning outcome (Pass, Merit, Distinction)
- The submitted work (text, PDF or docx via uploads)

### Output schema

```json
{
  "overall_grade": "Pass | Merit | Distinction | Not yet achieved",
  "criteria": [
    {
      "id": "P1",
      "description": "...",
      "met": true,
      "evidence": ["exact quote from the work"],
      "missing": "what is absent or weak",
      "fix": "specific action to meet it"
    }
  ],
  "strengths": ["..."],
  "priority_fixes": ["top 3 changes that would raise the grade"],
  "style_issues": ["em dashes", "referencing errors", "..."],
  "confidence": 0.0
}
```

### Prompt

```text
You are a strict Pearson BTEC Higher Nationals assessor and internal verifier.
Grade the submission against each criterion separately.
Rules:
- A criterion is met only if you can quote evidence from the submission. No evidence, not met.
- Merit requires all Pass criteria met. Distinction requires all Merit criteria met.
- Do not reward length, confidence or polish without substance.
- Be honest. A generous grade is worse than a harsh one.
- Check Harvard referencing format and that every in-text citation appears in the reference list.
Return only JSON matching the schema.
```

### Code (`pipelines/grading.py`)

```python
def grade(brief, criteria, submission, user_id):
    resp = client.messages.create(
        model=os.getenv("MODEL_MAIN"),
        max_tokens=16000,
        thinking={"type": "enabled", "budget_tokens": 8000},
        system=GRADER_PROMPT,
        messages=[{"role": "user", "content":
            f"<brief>{brief}</brief>\n<criteria>{criteria}</criteria>\n<submission>{submission}</submission>\n<schema>{SCHEMA}</schema>"}])
    log_usage(user_id, os.getenv("MODEL_MAIN"), resp.usage, feature="grading")
    text = next(b.text for b in resp.content if b.type == "text")
    result = json.loads(strip_code_fences(text))
    validate_grade_rules(result)   # enforce Pass, then Merit, then Distinction in code too
    return result
```

### Consistency

- Run grading twice. If the overall grades differ, run a third time and take the majority.
- Show the evidence quotes in the UI, so you can check each judgement yourself.

---

## 18. Firestore schema

```
users/{uid}
  profile: { name, course, location, goals, preferences[] }
  writing_samples/{id}: { title, text }
conversations/{convId}
  title, created_at, updated_at, summary, summary_covered_until, entities[]
  messages/{msgId}: { role, content, model, tokens, ts, upload_ids[] }
memories/{factId}
  user_id, text, topic, entities[], conv_id, created_at, updated_at, history[]
chunks/{chunkId}
  user_id, conv_id, text, created_at
entities/{entityId}
  user_id, name, type, aliases[], conv_ids[]
aliases/{aliasId}
  user_id, name, refers_to
uploads/{uploadId}
  user_id, name, block, created_at
artifacts/{artifactId}
  conv_id, title, versions[]
usage/{id}
  user_id, model, feature, input, output, cache_read, cache_write, usd, gbp, ts
```

Pinecone `twins` namespaces: `routing` (existing), `memory` (facts), `chunks` (summaries and passages). Every vector has `user_id` in metadata.

---

## 19. Testing and calibration

### Memory recall test

Create `tests/memory_cases.json` with paraphrased questions and the fact they should find:

```json
[
  {"ask": "how's the mechanic noise thing going", "expect": "car sound diagnosis app"},
  {"ask": "what's Hey Ashen built with", "expect": "Flask/React multi-provider"},
  {"ask": "which uni am I aiming for", "expect": "University of Greater Manchester"}
]
```

Measure recall@5 (expected fact appears in the top 5). Target 90% or higher. If it is low, lower the dense threshold, add aliases or improve the rewrite prompt.

### Grading calibration

1. Collect 3 to 5 pieces your tutors have already marked.
2. Run the grader on each.
3. Compare per-criterion results with the tutor's.
4. Adjust the prompt (stricter evidence rules, examples of "not met") until it matches at least 80% of criteria.

### Writing check

- Script that fails if the output contains `\u2014` (em dash).
- Script that checks every in-text citation `(Surname, Year)` has a matching reference entry.
- Word count within ±10% of the target.

### Cost check

After one week, compare total £ in the dashboard against £18. Tune routing if needed.

---

## 20. Cost expectations

Rough estimates (around 3k input and 700 output tokens per message, about £0.76 per $1):

| Usage | All Sonnet | 70% Haiku / 30% Sonnet | Saving vs Pro (£18) |
|---|---|---|---|
| Light (10 msgs/day) | ~£3 | ~£1 | £15 to £17 |
| Normal (30 msgs/day) | ~£9 | ~£3 | £9 to £15 |
| Heavy (100/day, long chats) | £25 to £100+ | £10 to £30 | May cost more |

| Task | Approximate cost |
|---|---|
| 3,000-word document through all 4 passes (Sonnet) | 10p to 20p |
| One grading run with thinking | a few pence |
| Memory extraction and rewrite per message (Haiku) | well under 0.1p |
| Embeddings | negligible |

Other services billed separately: ElevenLabs, Whisper, Tavily, Pinecone. Heavy voice use can cancel most of the saving.

---

## 21. Security notes

- Keep all API keys server-side. The React app never sees them.
- Add login (Firebase Auth) before deploying publicly, and scope every query by `user_id`.
- Rate-limit `/api/chat` and Socket.IO events.
- Laptop tools: allow-list of actions, confirmation required for anything destructive.
- Artifacts: sandboxed iframe without `allow-same-origin`.
- Do not store secrets or financial/ID numbers in memory (regex filter on the write path).
- Academic use: use the writing and grading tools for planning, feedback and checking your own work. Follow your college's AI policy for anything you submit.

---

## 22. Final checklist

**Chat quality**
- [ ] Streaming text and thinking over Socket.IO
- [ ] Sentence-by-sentence TTS from the stream
- [ ] Markdown, tables, syntax highlighting, copy buttons
- [ ] Model picker and "Think harder" toggle

**Cost**
- [ ] Prompt caching on system, profile and history
- [ ] Difficulty-based routing
- [ ] Usage logging for every LLM and non-LLM call
- [ ] Monthly budget guard and dashboard

**Agent**
- [ ] Tool loop with step cap
- [ ] Tools: web search, memory search, laptop actions, job search
- [ ] Confirmation for destructive actions

**Memory**
- [ ] Rolling summaries per conversation
- [ ] Fact extraction, dedupe and corrections
- [ ] Pinecone namespaces `memory` and `chunks`
- [ ] Alias and entity linking
- [ ] Query rewriting and HyDE
- [ ] Hybrid dense + BM25 search with RRF
- [ ] Reranking and recency boost
- [ ] Memory viewer with edit and forget
- [ ] Backfill of existing history
- [ ] Recall test at 90% or higher

**Files and output**
- [ ] PDF, image, docx and text uploads
- [ ] Artifacts panel with versions

**Writing and assessment**
- [ ] House style rules and writing samples
- [ ] Plan, draft, critique, revise pipeline with real sources
- [ ] Em dash guard and citation checker
- [ ] Rubric grader with JSON output and evidence quotes
- [ ] Double-run consistency check
- [ ] Calibration against tutor-marked work
