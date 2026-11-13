# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("skill_study", ROOT / "tools" / "skill_study.py")
skill_study = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(skill_study)

MODEL = "claude-sonnet-5.5"


def _episode(out, condition, family, task, usage, seconds=60.0, turns=6):
    attempt = Path(out) / "runs" / condition / MODEL / family / task / "attempt-1"
    (attempt / "out").mkdir(parents=True)
    (attempt / "attempt.json").write_text(json.dumps(
        {"attempt": 1, "status": "completed", "infrastructure_failure": False, "seconds": seconds}), encoding="utf-8")
    receipt = {"tasks": [{"provider_reported_usage": dict(zip(skill_study.USAGE_KEYS, usage)),
                          "agent_stats": {"model_turns": turns}}]}
    (attempt / "out" / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")


class CostTests(unittest.TestCase):
    def test_cost_pairs_each_skill_with_its_no_skill_run(self):
        with tempfile.TemporaryDirectory() as out:
            for task in ("mini-001", "mini-002"):
                _episode(out, "control", "Recap", task, (0, 10_000, 90_000, 8_000))
                _episode(out, "pinned-composio-file-organizer", "Recap", task, (0, 13_000, 117_000, 8_000))
            skill_study.command_cost(SimpleNamespace(out=out))
            summary = json.loads((Path(out) / "cost.json").read_text(encoding="utf-8"))
            with open(Path(out) / "per-task-usage.csv", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        input_price, write_price, read_price, output_price = skill_study.PRICES[MODEL]
        control_usd = (10_000 * write_price + 90_000 * read_price + 8_000 * output_price) / 1e6
        skill_usd = (13_000 * write_price + 117_000 * read_price + 8_000 * output_price) / 1e6
        control = summary["conditions"]["control|" + MODEL]
        skill = summary["conditions"]["pinned-composio-file-organizer|" + MODEL]
        self.assertEqual(control["tasks"], 2)
        self.assertNotIn("relative", control)
        self.assertAlmostEqual(control["per_task"]["usd"], control_usd)
        self.assertEqual(skill["reference"], "control")
        self.assertEqual(skill["extra_per_task"]["tokens_read"], 30_000)
        self.assertAlmostEqual(skill["relative"]["tokens_read"]["change"], 0.3)
        self.assertAlmostEqual(skill["relative"]["usd"]["change"], skill_usd / control_usd - 1)
        self.assertEqual(skill["relative"]["usd"]["ci95"][0], skill["relative"]["usd"]["ci95"][1])
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["cache_read_input_tokens"], "90000")

    def test_round_two_skills_use_the_round_two_control(self):
        with tempfile.TemporaryDirectory() as out:
            _episode(out, "control", "Thread", "mini-001", (0, 10_000, 50_000, 5_000))
            _episode(out, "control-r2", "Thread", "mini-001", (0, 20_000, 50_000, 5_000))
            _episode(out, "pinned-office-email-classifier", "Thread", "mini-001", (0, 20_000, 50_000, 5_000))
            skill_study.command_cost(SimpleNamespace(out=out))
            summary = json.loads((Path(out) / "cost.json").read_text(encoding="utf-8"))
        skill = summary["conditions"]["pinned-office-email-classifier|" + MODEL]
        self.assertEqual(skill["reference"], "control-r2")
        self.assertAlmostEqual(skill["relative"]["usd"]["change"], 0.0)


if __name__ == "__main__":
    unittest.main()
