# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import contextlib
import csv
import importlib.util
import io
import json
import unittest
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[1] / "results"


def load_checker():
    spec = importlib.util.spec_from_file_location("check_table3", RESULTS / "check_table3.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ResultsLedgerTest(unittest.TestCase):
    def test_checker_reproduces_published_table(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = load_checker().main()
        self.assertEqual(status, 0, out.getvalue())
        self.assertIn("562/562 matched", out.getvalue())

    def test_ledger_covers_45_systems_and_6750_task_rows(self):
        systems = json.loads((RESULTS / "systems.json").read_text(encoding="utf-8"))
        self.assertEqual(len(systems["systems"]), 45)
        self.assertTrue(all(not entry["in_table3"] for entry in systems["excluded"]))
        with (RESULTS / "per-task.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 45 * 150)
        self.assertEqual(len({(r["system"], r["family"], r["task"]) for r in rows}), len(rows))


if __name__ == "__main__":
    unittest.main()
