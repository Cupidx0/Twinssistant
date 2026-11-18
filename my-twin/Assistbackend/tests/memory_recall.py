"""Memory recall@5 against tests/memory_cases.json (README1 section 19). Uses live services.

Usage (from Assistbackend/):
    venv312/bin/python tests/memory_recall.py <firebase_uid>

A case passes when any of the top 5 memories shares most of the expected
phrase's words. Target: 90% or higher.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import memory  # noqa: E402


def matches(expect, text):
    want = set(re.findall(r"[a-z0-9]+", expect.lower()))
    have = set(re.findall(r"[a-z0-9]+", text.lower()))
    return bool(want) and len(want & have) / len(want) >= 0.6


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    user_id = sys.argv[1]
    with open(os.path.join(os.path.dirname(__file__), "memory_cases.json")) as f:
        cases = json.load(f)
    hits = 0
    for case in cases:
        found = memory.retrieve(user_id, case["ask"], k=5)
        ok = any(matches(case["expect"], m["text"]) for m in found[:5])
        hits += ok
        print(f"{'PASS' if ok else 'FAIL'}  {case['ask']!r} -> expected {case['expect']!r}")
        if not ok:
            for m in found[:5]:
                print(f"        got: {m['text'][:110]}")
    recall = hits / len(cases) if cases else 0
    print(f"\nrecall@5 = {recall:.0%} ({hits}/{len(cases)}); target 90%")
    sys.exit(0 if recall >= 0.9 else 1)


if __name__ == "__main__":
    main()
