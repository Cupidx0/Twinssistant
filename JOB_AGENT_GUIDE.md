# Twinssistant Job Agent — Build Guide

Turn Ashen into an agent that **finds jobs, scores how well they fit you, tailors your CV and cover letter per job, and applies** — with you as the final click. Written for this codebase: you already have the CV pipeline (`cv_route.py`), embeddings (`Pinecone_vec.py`), Firestore, Tavily, auth, and a scheduler-friendly Flask backend. This is mostly wiring, not new invention.

---

## 0. The honest rules (read first, saves you a banned account)

1. **Do NOT bot LinkedIn or Indeed.** Automating "Easy Apply", scraping their pages, or scripted logins violates their terms of service — LinkedIn actively detects it and bans accounts. Your LinkedIn is a career asset; don't feed it to a bot. Use their *official* aggregator APIs (below) for **discovery only**, and apply on employer sites.
2. **Human-in-the-loop is the default, not a compromise.** The agent does 95% of the work: finds, scores, tailors, fills. You review a queue and press submit. This is both safer (no ToS breach, no captcha wars) and *better* — 10 reviewed, tailored applications beat 100 sprayed ones. Recruiters can smell spray-and-pray.
3. **Never fabricate.** The tailoring prompt must expand and reframe your real experience — never invent employers, dates, or qualifications. One fabricated line discovered in an interview ends the whole process.
4. **Full-auto is allowed only where the platform designs for it** — official application APIs (Greenhouse/Lever below) and email applications. Everything else stays draft-mode.

---

## 1. Architecture (what bolts onto what)

```
┌────────────── discovery (cron, daily) ──────────────┐
│ Adzuna API ─┐                                       │
│ Reed API ───┼─→ normalise → dedupe (hash) → score   │
│ Jooble ─────┤       │            │           │      │
│ Greenhouse/ ┘       ▼            ▼           ▼      │
│ Lever boards    Firestore    embeddings   LLM match │
│                 `jobs`       (Pinecone)   0–100     │
└─────────────────────────────────────────────────────┘
                        │  score ≥ 70
                        ▼
┌────────────── tailoring (on demand) ────────────────┐
│ job description + master profile JSON                │
│   → tailored CV (reuse cv_route rewrite)             │
│   → cover letter (new endpoint)                      │
│   → ATS keyword check                                │
│   → .docx + .pdf saved, linked on the job doc        │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌────────────── application ──────────────────────────┐
│ Tier A: Greenhouse/Lever official apply API → auto   │
│ Tier B: job lists an email → draft email → you send  │
│ Tier C: other ATS → Playwright pre-fills → YOU click │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
      tracker UI (right-rail card + /jobs page)
      statuses: found → shortlisted → tailored →
      applied → interview → offer/rejected
      + follow-up reminders via your calendar tools
```

---

## 2. What you'll need (APIs & keys)

### Job discovery (all free tiers, all UK-friendly)

| API | What it gives you | Auth | Notes |
|---|---|---|---|
| **Adzuna** (`developer.adzuna.com`) | UK-strong aggregator; search by title/location/salary; returns description snippets + apply URL | free app id + key | Best first pick. `GET https://api.adzuna.com/v1/api/jobs/gb/search/1?app_id=..&app_key=..&what=junior%20software&where=surrey&distance=30` |
| **Reed** (`reed.co.uk/developerapi`) | UK-only board, real employer listings, full descriptions | free API key (Basic auth) | Great for junior/apprentice UK roles. `GET https://www.reed.co.uk/api/1.0/search?keywords=junior+developer&locationName=Crawley&distanceFromLocation=20` |
| **Jooble** (`jooble.org/api/about`) | aggregator, simple POST search | free key on request | Backup/extra coverage |
| **Remotive / RemoteOK** | remote-only listings, no key needed (`remotive.com/api/remote-jobs`, `remoteok.com/api`) | none | For remote junior roles |
| **Greenhouse Job Board API** | every company that uses Greenhouse exposes `https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true` | none for reading | Full JD text. Keep a list of target companies |
| **The Muse** (`themuse.com/developers`) | curated companies, levels filter (`Entry Level`) | free key | Nice-to-have |
| **Find an apprenticeship (gov.uk)** | UK apprenticeships — check the Apprenticeships API on `api.gov.uk` | key via registration | You're targeting apprenticeships: worth the signup |

### Applying

| Channel | How | Auto-allowed? |
|---|---|---|
| **Greenhouse** | `POST https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{id}` with form fields + resume — works where the company enables API applications | ✅ designed for it |
| **Lever** | `POST https://api.lever.co/v0/postings/{company}/{postingId}?send_confirmation_email=true` with `name`, `email`, `resume` multipart | ✅ designed for it |
| **Email applications** | Gmail API (you already have Google OAuth wired for Calendar — add the `gmail.compose` scope) → create **drafts**, you press send | ✅ (drafts) |
| **Everything else (Workday, Teamtailor, custom forms)** | Playwright script fills the form from your profile JSON, screenshots it, **pauses for you to review and click submit** | ⚠️ assisted only |

### Already in your stack (reuse, don't rebuild)

- **OpenAI/Gemini/Anthropic** via `Routing.py` — scoring, tailoring, cover letters
- **`text-embedding-3-small` + Pinecone** — job↔profile similarity (add a `jobs` namespace, or a second index)
- **Firestore** — the tracker database
- **`cv_route.py`** — extract/review/rewrite already works; you're adding a JD parameter
- **`python-docx` + docx2pdf or LibreOffice headless** — document output (most ATS want PDF: `soffice --headless --convert-to pdf file.docx`)
- **Google Calendar tools** — follow-up reminders ("chase X after 7 days")

New env vars:

```
ADZUNA_APP_ID=...
ADZUNA_APP_KEY=...
REED_API_KEY=...
JOOBLE_API_KEY=...        # optional
THEMUSE_API_KEY=...       # optional
```

---

## 3. Phase 0 — Master profile (do this before any code)

Everything downstream reads from **one structured file**: `Assistbackend/profile/master_profile.json` (gitignored — it's personal data).

```json
{
  "name": "Godwin Alamu",
  "email": "...", "phone": "...", "location": "Horley, Surrey",
  "links": { "github": "...", "linkedin": "...", "portfolio": "..." },
  "right_to_work_uk": true,
  "targets": {
    "titles": ["junior software developer", "graduate developer", "software apprentice", "AI integration"],
    "locations": ["Crawley", "Gatwick", "London", "remote"],
    "min_salary": 0, "max_commute_miles": 30
  },
  "education": [ { "course": "HNC/HND Computing", "provider": "...", "dates": "..." } ],
  "experience": [ { "role": "...", "org": "...", "dates": "...", "bullets": ["..."] } ],
  "projects": [ { "name": "Twinssistant", "stack": ["Python","Flask","React","Firebase","Pinecone"], "bullets": ["multi-provider AI assistant with voice, calendar tools, and CV pipeline"] } ],
  "skills": ["Python","React","Flask","Firebase","REST APIs","WebSockets","OpenAI/Anthropic/Gemini APIs","Pinecone"],
  "answers": {
    "why_this_role_seed": "one honest paragraph you write once",
    "notice_period": "immediate",
    "requires_sponsorship": false
  }
}
```

Why: the CV, the cover letter, and every form-fill all pull from here. Update it once, everything downstream updates. The `answers` block is what the Playwright filler uses for the standard ATS questions.

---

## 4. Phase 1 — Discovery (`job_agent/discover.py`)

1. **Fetch** from each source with your target titles × locations. Each API returns different shapes — normalise immediately:
   ```python
   def normalise(raw, source):
       return {
           "id": hashlib.sha256(f"{title}|{company}|{location}".lower().encode()).hexdigest(),
           "source": source, "title": ..., "company": ..., "location": ...,
           "salary": ..., "url": ..., "description": ...,   # full text where available
           "posted_at": ..., "found_at": datetime.utcnow().isoformat(),
           "status": "found", "score": None,
       }
   ```
2. **Dedupe** on that content hash (same trick as your Pinecone IDs) — Adzuna and Reed will both return the same job.
3. **Store** to Firestore collection `jobs` with `set(..., merge=True)` so re-runs don't clobber statuses.
4. **Schedule it**: a `/jobs/refresh` Flask endpoint (auth-required) + run daily. Simplest: cron on your Mac (`crontab -e` → `0 8 * * * curl -X POST ...`) or a `while True: time.sleep(86400)` thread. Later: APScheduler.

Gotcha: Adzuna truncates descriptions — when a job scores well, fetch the full posting (the `redirect_url` page, or the Greenhouse/Lever API if that's where it lives) before tailoring.

## 5. Phase 2 — Scoring (`job_agent/score.py`)

Two-stage, same cost-ladder you already use for intent:

1. **Cheap filter — embeddings.** Embed each new job (`title + description`) and compare to your embedded profile (cosine similarity via Pinecone `jobs` namespace). Drop anything under ~0.35; it's noise.
2. **Real score — one flash-lite call** for survivors:
   ```
   Score 0-100 how well this candidate fits this job. Consider: required
   skills vs candidate skills, experience level (candidate is junior —
   punish jobs needing 3+ years), location/remote, UK right-to-work.
   Return JSON only: {"score": int, "reasons": ["..."], "missing": ["..."],
   "keywords": ["exact terms from the JD an ATS would scan for"]}
   ```
   Save all four fields to the job doc. `keywords` feeds Phase 3; `missing` is your interview-prep list.
3. **Threshold:** ≥70 → `status: "shortlisted"` and it appears in your review queue. Everything else stays `found` (visible, but quiet).

## 6. Phase 3 — Tailoring (extend `cv_route.py`)

You already have `/cv/rewrite`. Add `/cv/tailor` that takes a `job_id`:

1. Pull the job doc + master profile JSON (stop feeding the model raw CV text — structured JSON tailors better).
2. Prompt essentials (keep your existing no-fabrication block, add):
   - "Mirror the job's own vocabulary for skills the candidate genuinely has — the JD calls it 'REST API development', the CV says 'REST APIs' → use their phrasing." (this is legitimate ATS optimisation)
   - "Weave in these exact keywords where truthful: {keywords from Phase 2}"
   - "Reorder bullets so the most relevant experience for THIS job comes first"
3. **Cover letter** — new generator, same call, different prompt: ≤ 250 words, structure = *why this company specifically* (1 para, use the JD + one fact from a quick Tavily search of the company) → *proof you can do the job* (2–3 concrete links from profile to their requirements) → *close*. Ban: "I am writing to express my interest", "esteemed organisation", any sentence that could open every cover letter ever written.
4. **ATS check** — cheap and useful: string-match the Phase-2 keywords against the generated CV text; report coverage ("14/17 JD keywords present"). Below ~70%? Regenerate with the misses called out.
5. Output `.docx` (your existing formatter) **and** `.pdf`, save to `refined/{job_id}/`, store paths on the job doc, `status: "tailored"`.

## 7. Phase 4 — Applying (three tiers, `job_agent/apply.py`)

- **Tier A — official APIs (full auto, opt-in per job).** If the job's apply URL contains `greenhouse.io` or `lever.co`, extract company + posting id and POST the application (name/email/phone from profile, tailored PDF as `resume`, cover letter text). Store the response as your receipt, `status: "applied"`. Rate-limit yourself: max ~10/day, jittered — be a polite client.
- **Tier B — email (draft-auto).** Job lists an application email → Gmail API `drafts.create` with subject `Application: {title} — {your name}`, cover letter as body, CV attached. It lands in your Drafts; you skim and hit send. (Add the Gmail scope to your existing `login_assist.py` flow and re-consent.)
- **Tier C — assisted browser (everything else).** Playwright (headed, not headless) opens the apply URL, fills every field it can match from `profile.answers`, uploads the PDF, screenshots the completed form, then **stops**. You review, answer anything weird, click submit, and hit "mark applied" in your UI. Do not build auto-submit here: captchas and bot-detection make it an arms race you don't want, and this tier is where the sketchy ToS territory begins.

## 8. Phase 5 — Tracker (the part that actually gets you hired)

- **Backend:** `GET /jobs?status=shortlisted`, `POST /jobs/{id}/status`, `POST /jobs/{id}/tailor`, `POST /jobs/{id}/apply`. All `@require_auth`.
- **Frontend:** a "Job hunt" card in the home right rail (top 3 shortlisted, score badges, one-tap *Tailor* → *Review* → *Applied*) + a full `/jobs` page (columns by status — found / shortlisted / tailored / applied / interview / done).
- **Chat integration:** add a `jobs` intent to `keyword_classify` ("find me jobs", "any new roles today", "apply to the Softwire one") → routes to these endpoints. Now Ashen answers "found 4 new roles above 70, want the CVs tailored?" — that's the Jarvis moment.
- **Follow-ups:** on `applied`, use your existing calendar tools to drop a "chase {company}" event 7 days out. On `interview`, generate a prep doc: JD + `missing` list + company Tavily digest.

---

## 9. Build order (each step ships something usable)

| # | Step | Effort | You have after it |
|---|---|---|---|
| 1 | `master_profile.json` + gitignore it | 1 evening | single source of truth |
| 2 | Adzuna + Reed fetch → normalise → dedupe → Firestore | 1 day | fresh UK jobs daily in your DB |
| 3 | Embedding filter + LLM score + shortlist | 1 day | ranked queue of real fits |
| 4 | `/cv/tailor` + cover letter + ATS check | 1–2 days | per-job CV+letter on demand |
| 5 | Tracker card + `/jobs` page + chat intent | 1 day | Ashen manages your search |
| 6 | Tier B email drafts | ½ day | one-keystroke applications |
| 7 | Tier A Greenhouse/Lever auto-apply | 1 day | true auto-apply where legal |
| 8 | Tier C Playwright assist | 2 days, do last | everything else pre-filled |

Steps 1–5 are the real product. 6–8 are acceleration.

## 10. Pitfalls learned by everyone who builds this

- **Volume is a trap.** The agent makes applying cheap; don't let it make your applications cheap. Keep the ≥70 threshold honest.
- **Same-day-post applications win.** That's why discovery is a daily cron and the digest pings you in the morning.
- **Junior-role filters:** score prompt must punish "3+ years required" hard, or your queue fills with fake-junior roles.
- **Keep receipts.** Store the exact CV/letter version + timestamp per application — when they call you three weeks later, you need to know what they read.
- **Costs:** at ~50 jobs/day scored with flash-lite + a few tailors, you're at pennies per day. The expensive call is tailoring — that's why it's on-demand per shortlisted job, not automatic for everything.
- **Data protection:** your profile JSON and generated letters are personal data — gitignored, like `Cv_docs/`. (You already learned this one the hard way. 😄)
