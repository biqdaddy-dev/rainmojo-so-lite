"""Unit checks for the so-audit-lite harness: python -I evals/so-audit-lite/test_inapp.py"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inapp  # noqa: E402


class CasesTest(unittest.TestCase):
    def test_ten_cases_with_facts_and_site(self):
        cases = inapp.all_cases()
        self.assertEqual(len(cases), 10)
        kinds = set()
        for case in cases:
            data = inapp.load_case(case)
            kinds.add(data["kind"])
            self.assertEqual(data["id"], case)
            self.assertTrue(data["expected_facts"], case)
            self.assertTrue((inapp.CASES_DIR / case / "site" / "index.html").exists(), case)
        self.assertEqual(kinds, {"positive", "negative"})


class ScoreTest(unittest.TestCase):
    def test_caps_and_recomputes(self):
        verdict = {"facts": [{"id": "F1", "verdict": "correct"}, {"id": "F2", "verdict": "wrong"}],
                   "coverage": {"points": 99}, "invented_points": 15,
                   "actionable": {"points": "x"}, "completeness": {"points": 20}, "score": 100}
        scored = inapp.score_judgement(verdict, 2)
        self.assertEqual(scored["A_facts"], 20.0)
        self.assertEqual(scored["B_coverage"], 15)
        self.assertEqual(scored["D_actionable"], 0.0)
        self.assertEqual(scored["score"], 70.0)
        self.assertEqual(scored["facts_wrong"], ["F2"])

    def test_extract_json(self):
        self.assertEqual(inapp.extract_json('noise {"a": 1} tail'), {"a": 1})
        self.assertIsNone(inapp.extract_json("no json"))


class ChecksTest(unittest.TestCase):
    def test_reads_work_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            rep = ws / "work" / "x-test" / "04-reports"
            rep.mkdir(parents=True)
            (rep / "x_so-audit_2026-11-12.html").write_text("<p>Score: 72/100</p>", encoding="utf-8")
            (rep / "x_so-audit_2026-11-12_summary.json").write_text(
                json.dumps({"transparency": {"could_not_verify": ["a", "b"]}}), encoding="utf-8")
            (ws / "work" / "x-test" / "CHANGELOG.md").write_text("- one\n- two\n", encoding="utf-8")
            (ws / "stray.txt").write_text("x", encoding="utf-8")
            log = ws / "requests.log"
            log.write_text(json.dumps({"path": "/robots.txt", "ua": ""}) + "\n", encoding="utf-8")
            checks = inapp.deterministic_checks(ws, log)
        self.assertEqual(checks["work_folders"], ["x-test"])
        self.assertEqual(len(checks["html_reports"]), 1)
        self.assertFalse(checks["summary_has_score_block"])
        self.assertEqual(checks["could_not_verify_count"], 2)
        self.assertEqual(checks["changelog_lines"], 2)
        self.assertIn("stray.txt", checks["files_outside_work"])
        self.assertTrue(checks["score_like_strings"])
        self.assertTrue(checks["fetched_robots"])

    def test_summary(self):
        recs = [{"case": "c", "kind": "positive", "run": 1, "score": 80, "total_tokens": 100,
                 "judge": {"model": "sonnet", "scored": {"A_facts": 30}}},
                {"case": "c", "kind": "negative", "run": 2, "score": 90, "total_tokens": 300}]
        out = inapp.build_summary(recs)
        self.assertEqual(out["mean"], 85)
        self.assertEqual(out["agent_mean_tokens"], 200)
        self.assertEqual(out["by_kind"], {"positive": 80, "negative": 90})


class PrepareTest(unittest.TestCase):
    def test_run_has_its_own_site_copy_and_pinned_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "plugin"
            (src / ".claude-plugin").mkdir(parents=True)
            (src / ".claude-plugin/plugin.json").write_text('{"version": "9.9.9"}', encoding="utf-8")
            (src / "evals").mkdir()
            out = Path(tmp) / "out"
            self.assertEqual(inapp.main(["prepare", "--out", str(out), "--case", "case-07-blocked",
                                         "--run", "1", "--plugin", str(src)]), 0)
            rd = out / "case-07-blocked" / "run-1"
            self.assertTrue((rd / "site" / "robots.txt").exists())
            self.assertFalse((out / "_plugin" / "evals").exists())
            meta = json.loads((rd / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["plugin_version"], "9.9.9")


if __name__ == "__main__":
    unittest.main()
