import re
from datetime import datetime

import dateparser
from flask import request


def get_request_json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def parse_natural_datetime(text, base_time=None):
    """
    Convert natural language datetime (e.g. 'tomorrow 7pm') into ISO 8601.
    If parsing fails, returns None.
    """
    settings = {"RELATIVE_BASE": base_time or datetime.now()}
    dt = dateparser.parse(text, settings=settings)
    return dt.isoformat() if dt else None


def has_word(text, words):
    """Match whole words/phrases, not substrings ('hi' should not match 'this')."""
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)
