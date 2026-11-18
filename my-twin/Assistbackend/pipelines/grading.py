"""Rubric-based grading with evidence quotes, structured JSON and a consistency vote
(section 17 of README1).

Grade rules are enforced in code as well as in the prompt:
- a criterion needs a quote that really appears in the submission;
- Merit needs every Pass criterion, Distinction needs every Merit criterion.
"""
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from llm import complete, parse_json
from services import MODEL_MAIN

GRADES = ["Not yet achieved", "Pass", "Merit", "Distinction"]

GRADER_PROMPT = """You are a strict Pearson BTEC Higher Nationals assessor and internal verifier.
Grade the submission against each criterion separately.
Rules:
- A criterion is met only if you can quote evidence from the submission, copied exactly. No evidence, not met.
- Merit requires all Pass criteria met. Distinction requires all Merit criteria met.
- Do not reward length, confidence or polish without substance.
- Be honest. A generous grade is worse than a harsh one.
- Check Harvard referencing format and that every in-text citation appears in the reference list.
- confidence is your confidence in the overall grade, from 0 to 1.
Return only JSON matching the schema."""

_STRINGS = {"type": "array", "items": {"type": "string"}}
SCHEMA = {
    "type": "object",
    "properties": {
        "overall_grade": {"type": "string", "enum": GRADES},
        "criteria": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"}, "description": {"type": "string"}, "met": {"type": "boolean"},
                "evidence": _STRINGS, "missing": {"type": "string"}, "fix": {"type": "string"},
            },
            "required": ["id", "description", "met", "evidence", "missing", "fix"],
            "additionalProperties": False,
        }},
        "strengths": _STRINGS, "priority_fixes": _STRINGS, "style_issues": _STRINGS,
        "confidence": {"type": "number"},
    },
    "required": ["overall_grade", "criteria", "strengths", "priority_fixes", "style_issues", "confidence"],
    "additionalProperties": False,
}


def _normalise(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def evidence_found(quote, submission_norm):
    q = _normalise(quote)
    if len(q) < 8:
        return False
    # Allow small edits at the ends of long quotes: check the first 80 normalised characters.
    return q[:80] in submission_norm


def criterion_level(cid):
    m = re.search(r"\b([PMD])\s*\d", cid or "", re.IGNORECASE)
    return m.group(1).upper() if m else None


def computed_grade(criteria):
    levels = {"P": [], "M": [], "D": []}
    for c in criteria:
        level = criterion_level(c.get("id"))
        if level:
            levels[level].append(bool(c.get("met")))
    if not levels["P"] or not all(levels["P"]):
        return "Not yet achieved"
    if not levels["M"] or not all(levels["M"]):
        return "Pass"
    if not levels["D"] or not all(levels["D"]):
        return "Merit"
    return "Distinction"


def validate_grade_rules(result, submission):
    """Enforce evidence and Pass -> Merit -> Distinction in code. Mutates and returns result."""
    notes = []
    sub_norm = _normalise(submission)
    for c in result.get("criteria", []):
        if not c.get("met"):
            continue
        verified = [q for q in c.get("evidence", []) if evidence_found(q, sub_norm)]
        if not verified:
            c["met"] = False
            c["missing"] = ("No quoted evidence could be found in the submission. " + (c.get("missing") or "")).strip()
            notes.append(f"{c.get('id')}: marked not met because its evidence quote was not found in the submission")
        c["evidence"] = verified or c.get("evidence", [])
    has_levels = any(criterion_level(c.get("id")) for c in result.get("criteria", []))
    grade = computed_grade(result.get("criteria", [])) if has_levels else result.get("overall_grade")
    if result.get("overall_grade") != grade:
        notes.append(f"Overall grade changed from {result.get('overall_grade')} to {grade} by the grading rules")
        result["overall_grade"] = grade
    result["rule_notes"] = notes
    return result


def _grade_once(brief, criteria, submission, user_id):
    content = (f"<brief>{brief}</brief>\n<criteria>{criteria}</criteria>\n"
               f"<submission>{submission}</submission>\n<schema>{json.dumps(SCHEMA)}</schema>")
    text = complete(content, model=MODEL_MAIN, system=GRADER_PROMPT, user_id=user_id, feature="grading",
                    max_tokens=16000, think=True, effort="high",
                    output_format={"type": "json_schema", "schema": SCHEMA})
    result = parse_json(text)
    if not isinstance(result, dict) or "criteria" not in result:
        raise ValueError("The grader did not return valid JSON")
    return validate_grade_rules(result, submission)


def grade(brief, criteria, submission, user_id, progress=None):
    """Run twice; if the overall grades differ, run a third time and take the majority."""
    if progress:
        progress("Grading (two independent runs)")
    with ThreadPoolExecutor(max_workers=2) as pool:
        runs = list(pool.map(lambda _: _grade_once(brief, criteria, submission, user_id), range(2)))
    if runs[0]["overall_grade"] != runs[1]["overall_grade"]:
        if progress:
            progress("Runs disagreed, running a tie-break")
        runs.append(_grade_once(brief, criteria, submission, user_id))

    votes = Counter(r["overall_grade"] for r in runs)
    top, count = votes.most_common(1)[0]
    if count == 1:  # three different grades: take the median (never the most generous)
        top = sorted((r["overall_grade"] for r in runs), key=GRADES.index)[1]
    chosen = next(r for r in runs if r["overall_grade"] == top)
    chosen["consistency"] = {"runs": [r["overall_grade"] for r in runs], "agreed": len(set(votes)) == 1}
    return chosen
