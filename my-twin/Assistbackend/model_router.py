"""Second routing dimension: difficulty -> model, plus the monthly budget guard.

The existing intent classifier (Pinecone cache -> keywords -> LLM) still picks
the intent; this module picks which Claude model answers.
"""
import re

from services import MODEL_CHEAP, MODEL_MAIN, MODEL_TOP

HARD_INTENTS = {"writing", "assessment", "cv", "architecture"}
# Writing and assessment keep their model even when over budget.
BUDGET_EXEMPT = {"writing", "assessment"}
ALLOWED_OVERRIDES = {MODEL_CHEAP, MODEL_MAIN, MODEL_TOP}
CHEAP_INTENTS = {"greeting", "identity", "mac_tool", "casual"}

_DIFFICULTY_PATTERNS = {
    "writing": r"\b(essay|report|coursework|assignment|dissertation|cover letter|personal statement|write (?:me )?an?|draft (?:me )?an?)\b",
    "assessment": r"\b(grade|mark|assess|assessment|rubric|criteria|feedback on my (?:essay|work|assignment))\b",
    "architecture": r"\b(architecture|system design|design a system|scalab\w+|refactor the (?:whole|entire))\b",
}


def detect_difficulty_intent(text, intent):
    """Upgrade the intent when the message is a writing/assessment/architecture task."""
    lowered = (text or "").lower()
    for name, pattern in _DIFFICULTY_PATTERNS.items():
        if re.search(pattern, lowered):
            return name
    return intent


def is_long_or_code(text):
    lowered = (text or "").lower()
    return len(text or "") > 1500 or "```" in (text or "") or "traceback" in lowered


def choose_model(intent, text, user_override=None, think=False, over_budget=False):
    """Return (model, reason)."""
    if user_override in ALLOWED_OVERRIDES:
        return user_override, "picked by you"

    if over_budget and intent not in BUDGET_EXEMPT:
        return MODEL_CHEAP, "monthly budget reached"

    if intent in HARD_INTENTS or think:
        return MODEL_MAIN, "hard task" if intent in HARD_INTENTS else "think harder"
    if intent == "code" or is_long_or_code(text):
        return MODEL_MAIN, "code or long message"
    if intent in CHEAP_INTENTS or intent in {"calendar", "jobs", "web_search"}:
        return MODEL_CHEAP, "quick task"
    return MODEL_CHEAP, "default"
