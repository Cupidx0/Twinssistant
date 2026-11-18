"""Compare the grader with tutor-marked work (README1 section 19). Uses live services and costs money.

Put cases in tests/grading_cases/*.json:
    {"brief": "...", "criteria": "...", "submission": "...",
     "tutor": {"overall_grade": "Merit", "criteria": {"P1": true, "P2": true, "M1": true, "D1": false}}}

Usage (from Assistbackend/):
    venv312/bin/python tests/calibrate_grading.py <firebase_uid>

Target: at least 80% per-criterion agreement.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipelines.grading import grade  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    user_id = sys.argv[1]
    files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "grading_cases", "*.json")))
    if not files:
        print("No cases in tests/grading_cases/. See the docstring for the format.")
        sys.exit(1)
    agree = total = 0
    for path in files:
        with open(path) as f:
            case = json.load(f)
        result = grade(case["brief"], case["criteria"], case["submission"], user_id)
        ours = {c["id"]: c["met"] for c in result["criteria"]}
        print(f"\n{os.path.basename(path)}: grader {result['overall_grade']} vs tutor {case['tutor']['overall_grade']}"
              f" (runs {result['consistency']['runs']})")
        for cid, met in case["tutor"]["criteria"].items():
            total += 1
            same = ours.get(cid) == met
            agree += same
            print(f"  {cid}: tutor {'met' if met else 'not met'}, grader "
                  f"{'met' if ours.get(cid) else 'not met' if cid in ours else 'missing'} {'' if same else '<-- differs'}")
    rate = agree / total if total else 0
    print(f"\nPer-criterion agreement: {rate:.0%} ({agree}/{total}); target 80%")
    sys.exit(0 if rate >= 0.8 else 1)


if __name__ == "__main__":
    main()
