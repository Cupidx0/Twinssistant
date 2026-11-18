"""Plan -> draft (section by section) -> critique -> revise (section 16 of README1)."""
from costs import log_service
from llm import cheap_complete, main_complete, parse_json
from pipelines.checks import remove_dashes, run_checks
from services import db, tavily_client

HOUSE_STYLE = """House style:
- UK English spelling.
- No em dashes or en dashes anywhere. Use commas, colons or full stops instead.
- Harvard referencing:
  Book: Surname, Initial. (Year) *Title*. Edition. Publisher.
  Website: Author/Organisation (Year) Title. [online] Available at: URL [Accessed: Month Year].
  In-text: (Surname, Year) or Surname (Year).
- Cite only sources provided in <sources>. Never invent a reference, author, year or URL.
- Clear, direct sentences. No filler openings. No repeated points.
- Match the voice of <writing_samples> when samples are given."""


def load_writing_samples(user_id, limit=3):
    try:
        docs = db().collection("users").document(user_id).collection("writing_samples").limit(limit).stream()
        samples = [d.to_dict() for d in docs]
    except Exception as e:
        print(f"Writing samples load failed: {e}")
        return ""
    return "\n\n".join(f"<sample title=\"{s.get('title', '')}\">\n{s.get('text', '')[:6000]}\n</sample>"
                       for s in samples)


def gather_sources(brief, user_id, max_results=8):
    """Real sources from Tavily: titles, URLs, dates and snippets."""
    try:
        res = tavily_client().search(query=brief[:380], search_depth="advanced", max_results=max_results)
        log_service(user_id, "tavily_search", 2, feature="writing")  # advanced search costs 2 credits
    except Exception as e:
        print(f"Source search failed: {e}")
        return []
    out = []
    for r in (res.get("results", []) if isinstance(res, dict) else []):
        out.append({"title": r.get("title"), "url": r.get("url"),
                    "published": r.get("published_date"), "snippet": (r.get("content") or "")[:1200]})
    return out


def format_sources(sources):
    if not sources:
        return "No sources were provided. Do not cite anything; write from reasoning and the brief only."
    lines = []
    for i, s in enumerate(sources, 1):
        lines.append(f"[{i}] {s.get('title')}\nURL: {s.get('url')}\nPublished: {s.get('published') or 'unknown'}\n"
                     f"Author/Organisation: {s.get('author') or 'derive from the site, or use the organisation name'}\n"
                     f"Notes: {s.get('snippet') or ''}")
    return "\n\n".join(lines)


PLAN_PROMPT = """Create an outline that maps every section to the assessment criteria.
<brief>{brief}</brief>
<criteria>{criteria}</criteria>
<sources>{sources}</sources>
Target length: {word_count} words in total (excluding references).
Return JSON only: {{"title": "...", "sections": [{{"title": "...", "purpose": "...", "criteria_covered": ["P1"], "word_budget": 400}}]}}
Include a final "References" section with word_budget 0 when sources are cited."""

SECTION_PROMPT = """{house_style}

<writing_samples>{samples}</writing_samples>
<brief>{brief}</brief>
<outline>{outline}</outline>
<previous_sections>{previous}</previous_sections>
<sources>{sources}</sources>

Write only the section "{title}" (about {words} words). Purpose: {purpose}.
It must cover these criteria: {criteria}.
Start with the section heading as a markdown "## " heading. Do not repeat earlier sections."""

REFERENCES_PROMPT = """{house_style}
Write the Harvard reference list for every source cited in this draft, alphabetical by surname/organisation.
Use only these sources. Accessed date: {accessed}.
Start with "## References".
<sources>{sources}</sources>
<draft>{draft}</draft>"""

CRITIQUE_PROMPT = """Act as a strict examiner. Compare the draft to the brief and criteria.
List: unmet criteria, weak evidence, unsupported claims, invented or unlisted sources, style rule breaks
(em dashes, US spelling, Harvard format, in-text citations missing from the reference list), repetition,
and word count issues (target {word_count}, current about {current} words). Be specific and quote the draft.
<brief>{brief}</brief>
<criteria>{criteria}</criteria>
<sources>{sources}</sources>
<draft>{draft}</draft>"""

REVISE_PROMPT = """{house_style}

Revise the draft to fix every issue in the critique. Keep what already works.
Return the full revised document in markdown, including the reference list. Target {word_count} words excluding references.
<writing_samples>{samples}</writing_samples>
<critique>{critique}</critique>
<sources>{sources}</sources>
<draft>{draft}</draft>"""


def _previous_context(sections, user_id):
    joined = "\n\n".join(sections)
    if len(joined) < 24000:
        return joined or "None yet."
    return cheap_complete("Summarise these sections in bullet points so the next section can follow on "
                          f"without repeating them:\n\n{joined}", user_id=user_id, feature="writing")


def write_document(brief, criteria, word_count, user_id, sources=None, progress=None):
    from datetime import datetime
    from pipelines.checks import word_count as count_words

    def step(msg):
        if progress:
            progress(msg)

    word_count = int(word_count or 1000)
    step("Finding sources")
    sources = sources if sources else gather_sources(brief, user_id)
    src = format_sources(sources)
    samples = load_writing_samples(user_id) or "None provided."

    step("Planning the outline")
    plan = parse_json(main_complete(PLAN_PROMPT.format(brief=brief, criteria=criteria or "None given",
                                                       sources=src, word_count=word_count),
                                    user_id=user_id, feature="writing", max_tokens=4000), default={})
    sections_plan = [s for s in (plan.get("sections") or []) if isinstance(s, dict) and s.get("title")]
    if not sections_plan:
        sections_plan = [{"title": "Main body", "purpose": "Answer the brief", "criteria_covered": [],
                          "word_budget": word_count}]
    body_plan = [s for s in sections_plan if "reference" not in s["title"].lower()]
    outline = "\n".join(f"- {s['title']}: {s.get('purpose', '')}" for s in body_plan)

    sections = []
    for i, s in enumerate(body_plan, 1):
        step(f"Drafting section {i} of {len(body_plan)}: {s['title']}")
        sections.append(main_complete(SECTION_PROMPT.format(
            house_style=HOUSE_STYLE, samples=samples, brief=brief, outline=outline,
            previous=_previous_context(sections, user_id), sources=src, title=s["title"],
            words=s.get("word_budget") or word_count // max(len(body_plan), 1),
            purpose=s.get("purpose", ""), criteria=", ".join(s.get("criteria_covered") or []) or "the brief"),
            user_id=user_id, feature="writing", max_tokens=8000))
    draft = "\n\n".join(sections)
    if sources:
        step("Writing the reference list")
        draft += "\n\n" + main_complete(REFERENCES_PROMPT.format(
            house_style=HOUSE_STYLE, sources=src, draft=draft,
            accessed=datetime.now().strftime("%B %Y")), user_id=user_id, feature="writing", max_tokens=4000)

    step("Critiquing the draft")
    critique = main_complete(CRITIQUE_PROMPT.format(
        brief=brief, criteria=criteria or "None given", sources=src, draft=draft,
        word_count=word_count, current=count_words(draft)), user_id=user_id, feature="writing", think=True)

    step("Revising")
    final = main_complete(REVISE_PROMPT.format(
        house_style=HOUSE_STYLE, samples=samples, critique=critique, sources=src, draft=draft,
        word_count=word_count), user_id=user_id, feature="writing")
    final = remove_dashes(final)

    step("Checking style rules")
    return {"title": plan.get("title"), "plan": sections_plan, "sources": sources, "draft": draft,
            "critique": critique, "final": final, "checks": run_checks(final, word_count)}
