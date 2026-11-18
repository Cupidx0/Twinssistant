"""Deterministic checks for written work: dashes, citations, word count, US spelling.

Pure functions (no network) so they run in tests and after every writing job.
"""
import re

EM_DASH, EN_DASH = "—", "–"

REFERENCE_HEADING_RE = re.compile(r"^\s*#*\s*\**(references?|reference list|bibliography)\**\s*:?\s*$",
                                  re.IGNORECASE | re.MULTILINE)
_SURNAME = r"[A-Z][A-Za-z'\-]+"
# (Smith, 2020) (Smith and Jones, 2020) (Smith et al., 2020: 14) (BBC, 2021; Smith, 2019)
PAREN_CITATION_RE = re.compile(r"\(([^()]*?\b(?:19|20)\d{2}[a-z]?\b[^()]*?)\)")
NARRATIVE_CITATION_RE = re.compile(rf"\b({_SURNAME})(?:\s+et al\.)?(?:\s+(?:and|&)\s+{_SURNAME})?\s+\(((?:19|20)\d{{2}}[a-z]?)\)")
ONE_CITATION_RE = re.compile(rf"({_SURNAME}(?:[\s&]+[A-Z][A-Za-z'\-]+)*?)(?:\s+et al\.)?(?:\s+(?:and|&)\s+{_SURNAME})?,?\s+((?:19|20)\d{{2}}[a-z]?|n\.d\.)")

US_SPELLINGS = {
    "color": "colour", "behavior": "behaviour", "organize": "organise", "organization": "organisation",
    "analyze": "analyse", "center": "centre", "favorite": "favourite", "realize": "realise",
    "recognize": "recognise", "optimize": "optimise", "prioritize": "prioritise", "license": "licence (noun)",
    "defense": "defence", "catalog": "catalogue", "modeling": "modelling", "traveled": "travelled",
    "labor": "labour", "honor": "honour", "utilize": "utilise", "summarize": "summarise",
}


def remove_dashes(text):
    """Hard guard: no em or en dashes. Number ranges keep a hyphen."""
    text = re.sub(rf"(\d)\s*{EN_DASH}\s*(\d)", r"\1-\2", text or "")
    text = re.sub(rf"\s*[{EM_DASH}{EN_DASH}]\s*", ", ", text)
    return re.sub(r",\s*,", ",", text)


def find_dashes(text):
    return {"em_dashes": (text or "").count(EM_DASH), "en_dashes": (text or "").count(EN_DASH)}


def split_references(text):
    """Return (body, reference_lines)."""
    m = None
    for m in REFERENCE_HEADING_RE.finditer(text or ""):
        pass  # the last heading wins
    if not m:
        return text or "", []
    body, refs = text[:m.start()], text[m.end():]
    lines = [ln.strip(" -*\t") for ln in refs.splitlines() if ln.strip()]
    return body, lines


def find_citations(body):
    """[(surname, year)] for in-text citations."""
    found = []
    for m in PAREN_CITATION_RE.finditer(body):
        for part in m.group(1).split(";"):
            c = ONE_CITATION_RE.search(part.strip())
            if c:
                found.append((c.group(1).split()[0].strip(","), c.group(2)))
    for m in NARRATIVE_CITATION_RE.finditer(body):
        found.append((m.group(1), m.group(2)))
    # De-duplicate, keep order
    seen, out = set(), []
    for item in found:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def check_citations(text):
    body, refs = split_references(text)
    citations = find_citations(body)
    missing = []
    for surname, year in citations:
        if not any(surname.lower() in r.lower() and year in r for r in refs):
            missing.append(f"{surname} ({year})")
    uncited = [r for r in refs
               if not any(s.lower() in r.lower() and y in r for s, y in citations)]
    return {"citations": len(citations), "references": len(refs),
            "missing_from_references": missing, "references_not_cited": uncited}


def word_count(text):
    body, _ = split_references(text)
    body = re.sub(r"[#*_`>]", " ", body)
    return len(re.findall(r"\b[\w'’-]+\b", body))


def check_word_count(text, target, tolerance=0.10):
    count = word_count(text)
    ok = target is None or abs(count - target) <= target * tolerance
    return {"words": count, "target": target, "within_tolerance": ok}


def find_us_spellings(text):
    hits = {}
    for us, uk in US_SPELLINGS.items():
        n = len(re.findall(rf"\b{us}\w*\b", text or "", re.IGNORECASE))
        if n:
            hits[us] = {"count": n, "use": uk}
    return hits


def run_checks(text, target_words=None):
    dashes = find_dashes(text)
    citations = check_citations(text)
    words = check_word_count(text, target_words)
    spelling = find_us_spellings(text)
    passed = (dashes["em_dashes"] == 0 and not citations["missing_from_references"]
              and words["within_tolerance"])
    return {"passed": passed, "dashes": dashes, "citations": citations,
            "word_count": words, "us_spellings": spelling}
