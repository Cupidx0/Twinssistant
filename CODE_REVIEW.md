# Twinssistant — Full Code Review

**Goal:** push this toward maximum Jarvis / Perplexity AI vibes.
**Date:** 2026-07-02 · **Scope:** whole repo (backend `my-twin/Assistbackend/`, frontend `my-twin/src/`, repo hygiene)

> **Status update (2026-07-02):** Phases 1–3 have been applied on this branch — repo hygiene (venv/personal docs untracked, `requirements.txt` + README added), all P0 bugs (items 1–10), and the P1 security/correctness fixes (Firebase token auth on data routes, `calendarId="primary"`, word-boundary intent matching, cache-poisoning guard, path fixes, dead code removal). Phase 4 (streaming, citations, status lines, unified thread) remains the roadmap.

---

## TL;DR

The bones are genuinely good: multi-provider LLM routing, voice in/out, semantic intent caching with Pinecone, calendar + CV tooling. That's a real Jarvis feature set. But right now the intent router is silently broken (a tuple-vs-string bug means it never routes), several endpoints crash inside their own error handlers, and **94% of the tracked files in this repo are the `venv/` folder plus personal documents that should never be in git**. Fix the routing bug, clean the repo, add streaming + citations, and this jumps two tiers in polish.

---

## ✅ What's fine (keep, this is the good stuff)

| What | Where | Why it's good |
|---|---|---|
| Multi-provider abstraction (`create_chat_completion`, `create_anthropic_completion`, `create_gemini_completion` + extractors) | `Routing.py` | Exactly the right architecture for a Jarvis-style assistant — swap models per task. The OpenAI↔Gemini message/config remapping is well done. |
| ElevenLabs websocket TTS with gTTS fallback | `eleven.py`, `Assist.py` chat route | Streaming TTS with a graceful degrade path is proper assistant engineering. |
| Semantic intent cache concept | `Pinecone_vec.py` | Caching classified intents by embedding similarity is a smart latency/cost play (implementation needs fixes, see below). |
| The voice UI | `ai_speech.jsx` | Best file in the repo: pause-detection auto-send, socket-with-HTTP-fallback, speaking/listening state machine, mic error handling, voice/rate settings. This *is* the Jarvis vibe — make it the main surface. |
| Central axios client with interceptors + env base URL | `Utils/Assistant.js` | Correct pattern (the rest of the app just needs to actually use it). |
| Auth context | `AuthContext.jsx` | Clean, minimal, correct Firebase listener + cleanup. |
| Settings persistence with defaults-merge | `Settings.jsx` | Defensive localStorage read with nested-default merging — nice. |
| CV pipeline concept (upload → extract → review JSON → rewrite → .docx download) | `cv_route.py`, `Weather_cv.jsx` | End-to-end feature that actually ships a file back. The markdown→docx formatting logic is decent. |
| UK holidays fallback (Easter computus, nth-weekday, substitute-day logic) | `Assist.py` | Correct algorithms, sensible `holidays` lib fallback. |
| Secrets hygiene for keys | `.gitignore` | `tw.json`, `token.json`, `.env`, `credentials.json` are all ignored and **verified not tracked**. Good. |

---

## 🔧 What needs improvement

### P0 — Actually broken (fix these first)

1. **The intent router never routes.** `Assist.py:712` — `intent = intent_classifier(message)` returns a **tuple** `(intent, confidence)`, then `if intent == "calendar"` compares a tuple to a string → always false. Unpack it: `intent, confidence = intent_classifier(message)`. (All branches are `pass` anyway right now — wire them to `calendar_manage()`, the CV blueprint, etc.)

2. **Classifier crashes on API failure.** `Assist.py:634-646` — if the Gemini call raises, the `except` only prints, then the next line reads `response` → `NameError`. Return the keyword result inside the `except`, or initialize `response = None` and guard.

3. **Calendar-flavored chats always error.** `Assist.py:831-839` — `create_anthropic_completion` is sent a `{"role": "system"}` message (the Anthropic API rejects system-role messages; pass `system=` instead, like `cv_route.py` correctly does) **and** the model `claude-2` is retired. Use a current model (e.g. `claude-sonnet-4-6`, which you already use in `cv_route.py`).

4. **Error handlers crash.** `jsonify({"error": str(e)}, debug=True)` in `Assist.py:895` and `cv_route.py:165,168` — `jsonify` treats the second positional arg as more response data and `debug=` isn't a thing; the handler itself throws, masking the real error. Remove `debug=True`.

5. **`calendar_manage` returns a Response inside a Response.** `Assist.py:466-467` calls the *view function* `fetch_calendar_events()` and then wraps the Flask `Response` in `jsonify()` → serialization error. Call `get_calendar_events(...)` (the plain function) instead.

6. **`smart_chat_history` mangles history.** `load_chat_history()` returns a **string**, but `smart_chat_history` treats it as a list of message dicts: `len(history)` counts characters, `history[:-6]` chops 6 characters, then joins single characters with `" | "`. Store history as a JSON list (see roadmap) or split the string into turns before slicing.

7. **`/audio` endpoint is non-functional.** `Assist.py:551-573` — writes `request.data` to a file named after a JSON field, calls `create_chat_completion` and then uses the *response* as if it were an OpenAI *client* (`client.audio.transcriptions.create`), and `gpt-4o-transcribe` isn't a chat model. Rewrite it to accept a file upload and call the transcription API directly — or delete it (the browser SpeechRecognition path already covers STT).

8. **Frontend/backend contract mismatch on add-event.** `Assistant.js:105` sends `{ summary, dueDate, userId }` but the backend reads `data.get("end")` → every `CalendarAPI.addEvent` call is a 400. Also `home.jsx:160` sends `UserId` (wrong casing) and `fetchEvents` posts no body at all, so `userId` is always `None`.

9. **`Login.jsx` uses `toast` without importing it** → `ReferenceError` the moment login succeeds or fails.

10. **Rules-of-Hooks violation in `home.jsx`.** Early `return` at line 283-285 (`browserSupportsSpeechRecognition`) sits *before* several `useEffect` hooks (line 289+). React will throw "rendered fewer hooks than expected" if that branch ever flips. Move all hooks above any conditional return.

### P1 — Wrong behavior / security

11. **No auth on any backend endpoint.** Every route trusts a `userId` from the request body, and the Google Calendar is hardcoded to `alamugodwin@gmail.com` in three places — every user of the app reads/writes *your* calendar. Verify the Firebase ID token server-side (`firebase_admin.auth.verify_id_token`) and derive `userId` + calendar from it. Use `"primary"` as the calendarId for the authorized token.

12. **Keyword classifier uses substring matching.** `keyword_classify` checks `"hi" in text` — matches "t**hi**s", "w**hi**ch"; `"open"` matches "hap**pen**ing"... wait, and `"play"` matches "dis**play**". Match on word boundaries (`re.search(r'\bhi\b', text)`) or token sets. Also the greeting check runs *after* code/mac checks, so "hey, fix this bug" and "hi" behave unpredictably.

13. **The intent cache poisons itself.** `save_pattern` runs on **every** message, including 0.5-confidence "casual" fallbacks — so wrong guesses get cached at 0.85+ similarity and returned forever. Only save above a confidence threshold. Also: ID `user_text[:100]` means two long messages with the same first 100 chars overwrite each other — hash the text instead.

14. **Embedding + Pinecone round-trip on every single message** (`find_pattern` then `save_pattern`) adds two network calls of latency before the chat even starts, and `Pinecone_vec.py` uses the **legacy** `openai.Embedding.create` API (removed in openai ≥ 1.0) while `Routing.py` carefully handles both SDK generations — inconsistent; one of the two will be broken in any given env.

15. **Module-level side effects.** `Pinecone_vec.py:41` runs `print(index.describe_index_stats())` at import (network call + noise on every boot); `Assist.py:390` has stray `print(get_calendar_events)`. `Routing.py` builds a *second* Flask app + CORS + Tavily client that are never used — it should be a pure helper module.

16. **One giant prompt, rebuilt every message.** The chat route stuffs the full CV review JSON, calendar events, fit-check rules, and web results into every prompt regardless of topic — token waste, and it dilutes answers (the prompt even ends mid-sentence: *"Do not get distracted by context unless it"*). Load context conditionally based on the (fixed) intent. Also note the assistant has three different names: "Tavily" (`get_ai_response`), "Ashen" (chat route default), and whatever the frontend sends.

17. **Untrusted content is interleaved with instructions** (web search results, chat history, CV text pasted straight into the system prompt) — classic prompt-injection surface. Separate: instructions in `system`, data in clearly delimited user content.

18. **`Login.jsx` writes every login email to a `logins` Firestore collection from the client.** Any authenticated client can read/write it (depending on rules). Use Firebase Auth's built-in metadata or server-side logging.

19. **Hardcoded `http://127.0.0.1:5000` in six fetches in `home.jsx`** while `Assistant.js` already exists with an env-based client — deploys will silently break. Route everything through the axios client. Same for the weather city being hardcoded (`horley` backend, `London` frontend) and the OpenWeather call using `http://` instead of `https://`.

20. **DOM manipulation inside React.** `home.jsx:196-211` grabs `#task-input` with `document.getElementById` and attaches a native `change` listener in a `useEffect` keyed on `AiTasks` (re-attaching every keystroke). The input is already controlled — just use `onChange`/`onBlur`. Also `alert(data.reply)` at line 163 next to a toast system, and `localStorage.getItem` called directly in JSX render (lines 465, 553-557).

21. **`get_relevant_history(history, keywords=[...])`** — mutable default arg, the `history` parameter is immediately overwritten by a file read, and it crashes with `FileNotFoundError` if `chat/chat_history.txt` doesn't exist (fresh install). Same fragility in the chat route: `open(cv_info_json)` throws if no CV was ever reviewed, killing *all* chat, not just CV chat.

22. **Duplicate code:** `extract_anthropic_text` is defined twice in `cv_route.py` (module level *and* inside `review()`); `get_cv()` sorts the file list twice (first sort is dead); the web-search keyword list exists twice (`keyword_classify` and inline in `chat()`); `Assist.py` re-declares `CV_DIR` etc. that `cv_route.py` also declares — but with different casing (`Cv_docs` vs `cv_docs`), so upload and chat read **different directories** depending on OS case-sensitivity.

---

## 🗑️ What's unnecessary (delete from the repo)

This is the highest-impact cleanup — the repo is 1,177 tracked files and ~1,100 of them shouldn't be here:

| Delete | Why |
|---|---|
| `my-twin/Assistbackend/venv/` (**1,100 files**) | Never commit a virtualenv. Add `venv/` to `.gitignore`, `git rm -r --cached`, and ship a `requirements.txt` instead (there isn't one — that's the real gap). |
| `my-twin/Assistbackend/Cv_docs/*` | **Personal data in git**: your actual CV, university assignments, observation records. Anyone who clones the repo gets them, and they live in history forever. Remove and gitignore the folder (it's user-upload storage at runtime). |
| `my-twin/Assistbackend/chat/chat_history.txt` | Personal chat logs, same problem. Runtime data, not source. |
| `my-twin/Assistbackend/refined/*`, `output.mp3`, `.~written_Software_Engineer.doc` | Generated artifacts and an Office lock file. |
| `__pycache__/`, `.DS_Store` | Standard ignores. |
| `main_shut.py` | A script whose only job is `shutdown -h now`. Unused, and genuinely dangerous if ever imported/wired to a route on an unauthenticated backend. |
| Dead imports in `Assist.py`/`Routing.py` | `from pickle import GET`, `from yaml import emit` (shadowed by the flask_socketio `emit` import anyway), `cv2`, `pdfplumber`, `session`, `InstalledAppFlow`, `secure_filename`... run `ruff` once and let it flag all of them. |
| Unused Flask app + Tavily client + `get_tavily_results` in `Routing.py` | `Routing.py` should export the provider helpers only. |
| ~350 lines of commented-out JSX in `home.jsx` (lines 80-139, 182-214, 571-671) | Git already remembers it. It's more than half the file. |
| `Closet.jsx`, `Music.jsx` | Both are 0 bytes; the sidebar links to them anyway. Either build or remove the nav entries. |
| Unused frontend deps | `openai` (an LLM SDK in the *browser* bundle — if it were ever used it'd expose the key), `@elevenlabs/elevenlabs-js` (TTS happens server-side), `dotenv` (Vite has `import.meta.env`), likely `recharts`, `browser-image-compression`, `react-linkify` (only used in a comment). |
| Duplicate `.gitignore` blocks | The root `.gitignore` repeats the same 10 lines twice. |
| Root `README.md` (9 bytes) | Not "delete" — replace. No setup steps, no env-var list, no architecture note. For a portfolio project (which this is — it's on your CV), the README *is* the landing page. |

---

## 🚀 The Jarvis / Perplexity roadmap

In priority order — each step is visible polish:

1. **Stream the reply.** Nothing says "Perplexity" like tokens appearing live. You already have Socket.IO on both ends and `ai_speech.jsx` even has a `replacePendingAssistantMessage(text, "streaming")` handler waiting for it — the backend just never streams. Emit chunks from the provider's streaming API over the socket; fall back to the current one-shot HTTP.

2. **Citations.** When Tavily results are used, return `sources: [{title, url}]` alongside `reply`, render them as numbered chips under the answer. `react-markdown` + `remark-gfm` are *already installed and unused* — render replies as markdown with clickable sources instead of stripping `*` characters with `.replace("*","")`.

3. **Agent status lines.** Emit intermediate events — "Searching the web…", "Checking your calendar…", "Reading your CV…" — over the socket while tools run. This is the single cheapest Jarvis-vibe upgrade, and your intent router (once fixed) already knows which tool it's about to call.

4. **One real function-calling router.** Replace the keyword lists + Gemini-JSON-regex hybrid with a single model call using tool definitions (you already wrote `calendar_functions` and the tool-conversion code in all three providers). Keep the Pinecone cache in front of it — that design is right.

5. **Structured, per-user memory.** Store history as JSON turns (per Firebase UID, in Firestore — you already have it) instead of a shared flat text file. Then `smart_chat_history` becomes real summarization: summarize turns older than N with a cheap model and pin the summary.

6. **Make voice the front door.** `ai_speech.jsx` is your best UX — promote it to the home screen. Add barge-in (you already stop the mic while speaking; also stop *speaking* when the user starts talking) and pipe the ElevenLabs audio you already generate through the socket instead of falling back to robotic `speechSynthesis`.

7. **Unify the chat surface.** `home.jsx` currently shows one question/one answer from localStorage. Reuse the conversation-thread component from `ai_speech.jsx` so text and voice share one message list.

8. **Lock it down.** Firebase ID-token verification middleware on Flask, per-user Google OAuth for calendar (`calendarId="primary"`), rate limiting, and `.env.example` documenting the 7 required keys (`OPENAI`, `CLAUDE`, `GEMINI`, `TAVILY`, `OPENWEATHER`, `PINECONE`, `ELEVENLABS`).

---

## Suggested order of attack

| Phase | Work | Effort |
|---|---|---|
| 1. Repo hygiene | Remove venv/personal docs/artifacts, add `requirements.txt` + README + `.env.example` | ~1 hr |
| 2. P0 bug fixes | Items 1–10 above | ~1 day |
| 3. Auth + contracts | Items 11, 18, 19; align frontend/backend payloads | ~1 day |
| 4. Vibes | Streaming → citations → status lines → unified thread | iterative |

The project's ambition is right and the hard parts (multi-provider routing, voice loop, tool concepts) already exist. Most of what stands between this and a demo that feels like Jarvis is deleting what shouldn't be here and letting the good 20% breathe.
