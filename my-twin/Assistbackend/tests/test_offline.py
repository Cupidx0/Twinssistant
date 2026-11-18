"""Offline unit tests (no network, no credentials).

Run from Assistbackend/:  venv312/bin/python -m unittest discover -s tests -p "test_*.py"
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from artifacts import extract_artifacts  # noqa: E402
from costs import usage_cost_usd  # noqa: E402
from llm import build_system, mark_cached, parse_json, request_kwargs  # noqa: E402
from memory import (apply_recency_boost, bm25_rank, contains_secret, fit_to_budget,  # noqa: E402
                    forget_request, rrf_merge, sliding_windows)
from model_router import choose_model, detect_difficulty_intent  # noqa: E402
from pipelines.checks import check_citations, find_dashes, remove_dashes, run_checks, word_count  # noqa: E402
from pipelines.grading import computed_grade, validate_grade_rules  # noqa: E402
from services import MODEL_CHEAP, MODEL_MAIN, MODEL_TOP  # noqa: E402


class WritingChecks(unittest.TestCase):
    def test_dashes_removed(self):
        text = "It works — mostly. Pages 10–12 cover it – briefly."
        cleaned = remove_dashes(text)
        self.assertEqual(find_dashes(cleaned), {"em_dashes": 0, "en_dashes": 0})
        self.assertIn("10-12", cleaned)

    def test_citations_match_reference_list(self):
        text = ("Cloud use is rising (Smith, 2021). Jones and Patel (2019) disagree (BBC, 2023; Lee et al., 2020).\n\n"
                "## References\n"
                "Smith, J. (2021) *Cloud Futures*. 2nd edn. Penguin.\n"
                "Jones, A. and Patel, R. (2019) *Systems*. Wiley.\n"
                "BBC (2023) Cloud news. [online] Available at: https://bbc.co.uk [Accessed: November 2026].\n")
        result = check_citations(text)
        self.assertEqual(result["missing_from_references"], ["Lee (2020)"])
        self.assertEqual(result["citations"], 4)

    def test_word_count_excludes_references(self):
        text = "one two three four five\n\nReferences\nSmith, J. (2020) Book. Publisher."
        self.assertEqual(word_count(text), 5)

    def test_run_checks(self):
        report = run_checks("word " * 100, target_words=105)
        self.assertTrue(report["passed"])
        self.assertFalse(run_checks("word — " * 100, 100)["passed"])


class MemoryHelpers(unittest.TestCase):
    def test_rrf_merge_prefers_items_in_many_lists(self):
        a = [{"id": "x", "text": "x"}, {"id": "y", "text": "y"}]
        b = [{"id": "y", "text": "y"}, {"id": "z", "text": "z"}]
        merged = rrf_merge([a, b])
        self.assertEqual(merged[0]["id"], "y")
        self.assertEqual({m["id"] for m in merged}, {"x", "y", "z"})

    def test_bm25_finds_keyword_matches(self):
        docs = [{"id": "1", "text": "Uses Flask-SocketIO threading mode"},
                {"id": "2", "text": "Favourite colour is green"},
                {"id": "3", "text": "Building a car sound diagnosis app"}]
        ranked = bm25_rank("car sound app", docs)
        self.assertEqual(ranked[0]["id"], "3")
        self.assertEqual(len(ranked), 1)

    def test_recency_boost_breaks_ties(self):
        now = datetime.now(timezone.utc)
        items = [{"id": "old", "score": 5, "created_at": (now - timedelta(days=400)).isoformat()},
                 {"id": "new", "score": 5, "created_at": now.isoformat()}]
        self.assertEqual(apply_recency_boost(items)[0]["id"], "new")

    def test_fit_to_budget(self):
        items = [{"text": "a" * 400}, {"text": "b" * 400}, {"text": "c" * 40}]
        self.assertEqual(len(fit_to_budget(items, 120)), 2)

    def test_secret_filter(self):
        for secret in ["my api key is abc", "sk-ant-api03-abcdefghijklmnopqrstu", "card 4111 1111 1111 1111",
                       "NI number AB123456C", "password: hunter2"]:
            self.assertTrue(contains_secret(secret), secret)
        for fine in ["Exam on 18-11-26", "Uses Flask on port 5050", "Studies at UGM", "Phone is 07700 900123"]:
            self.assertFalse(contains_secret(fine), fine)

    def test_forget_request(self):
        self.assertEqual(forget_request("Forget that I live in Horley."), "I live in Horley")
        self.assertIsNone(forget_request("don't forget my keys"))

    def test_sliding_windows_overlap(self):
        windows = list(sliding_windows(list(range(20)), size=10, overlap=2))
        self.assertEqual(windows[0][-2:], windows[1][:2])
        self.assertEqual(windows[-1][-1], 19)


class Routing(unittest.TestCase):
    def test_choose_model(self):
        self.assertEqual(choose_model("greeting", "hi")[0], MODEL_CHEAP)
        self.assertEqual(choose_model("code", "fix this")[0], MODEL_MAIN)
        self.assertEqual(choose_model("casual", "x" * 2000)[0], MODEL_MAIN)
        self.assertEqual(choose_model("casual", "hi", user_override=MODEL_TOP)[0], MODEL_TOP)
        self.assertEqual(choose_model("casual", "hi", user_override="gpt-9")[0], MODEL_CHEAP)
        self.assertEqual(choose_model("code", "fix", over_budget=True)[0], MODEL_CHEAP)
        self.assertEqual(choose_model("writing", "essay", over_budget=True)[0], MODEL_MAIN)

    def test_difficulty_intent(self):
        self.assertEqual(detect_difficulty_intent("Write me an essay on cloud computing", "casual"), "writing")
        self.assertEqual(detect_difficulty_intent("grade this against the rubric", "casual"), "assessment")
        self.assertEqual(detect_difficulty_intent("hello", "greeting"), "greeting")


class LlmHelpers(unittest.TestCase):
    def test_request_kwargs_think_uses_adaptive_and_effort(self):
        kw = request_kwargs("claude-sonnet-5-5", [{"role": "user", "content": "x"}], think=True, effort="low")
        self.assertEqual(kw["thinking"], {"type": "adaptive", "display": "summarized"})
        self.assertEqual(kw["output_config"]["effort"], "high")
        self.assertNotIn("temperature", kw)
        self.assertEqual(kw["extra_body"], {"fallbacks": "default"})

    def test_haiku_has_no_fallback(self):
        kw = request_kwargs("claude-haiku-5-5", [{"role": "user", "content": "x"}], effort="low")
        self.assertNotIn("extra_body", kw)
        self.assertNotIn("thinking", kw)

    def test_cache_breakpoints(self):
        system = build_system("prompt", "profile", "summary")
        self.assertEqual(sum("cache_control" in b for b in system), 2)
        msg = mark_cached({"role": "assistant", "content": "hi"})
        self.assertEqual(msg["content"][-1]["cache_control"], {"type": "ephemeral"})

    def test_parse_json(self):
        self.assertEqual(parse_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(parse_json('Sure: {"a": 2} done'), {"a": 2})
        self.assertEqual(parse_json("nope", {}), {})


class Costs(unittest.TestCase):
    def test_usage_cost(self):
        usd, tokens = usage_cost_usd("claude-sonnet-5-5", {
            "input_tokens": 1_000_000, "output_tokens": 100_000,
            "cache_read_input_tokens": 1_000_000, "cache_creation_input_tokens": 0})
        self.assertAlmostEqual(usd, 2.0 + 1.0 + 0.10)
        self.assertEqual(tokens["cache_read"], 1_000_000)


class Grading(unittest.TestCase):
    def test_computed_grade(self):
        crit = [{"id": "P1", "met": True}, {"id": "P2", "met": True}, {"id": "M1", "met": False}, {"id": "D1", "met": True}]
        self.assertEqual(computed_grade(crit), "Pass")
        crit[2]["met"] = True
        self.assertEqual(computed_grade(crit), "Distinction")
        crit[0]["met"] = False
        self.assertEqual(computed_grade(crit), "Not yet achieved")

    def test_evidence_must_exist(self):
        submission = "The network uses a star topology because it isolates faults on each link."
        result = {"overall_grade": "Merit", "criteria": [
            {"id": "P1", "met": True, "evidence": ["uses a star topology because it isolates faults"], "missing": "", "fix": ""},
            {"id": "M1", "met": True, "evidence": ["a quote the student never wrote at all"], "missing": "", "fix": ""}]}
        validate_grade_rules(result, submission)
        self.assertTrue(result["criteria"][0]["met"])
        self.assertFalse(result["criteria"][1]["met"])
        self.assertEqual(result["overall_grade"], "Pass")
        self.assertTrue(result["rule_notes"])


class Artifacts(unittest.TestCase):
    def test_extract(self):
        arts = extract_artifacts('Here:\n<artifact type="html" title="Clock"><html><body>hi</body></html></artifact>')
        self.assertEqual(arts, [{"type": "html", "title": "Clock", "html": "<html><body>hi</body></html>"}])


if __name__ == "__main__":
    unittest.main()
