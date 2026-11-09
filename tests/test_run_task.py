# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"
sys.path.insert(0, str(BENCH))

import run_task  # noqa: E402


def quiet(*argv):
    with contextlib.redirect_stdout(io.StringIO()):
        return run_task.main(list(argv))


class RunTaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.run = self.tmp / "run"
        quiet("prepare", "Recap/mini-001", str(self.run))
        self.workspace = self.run / "workspace"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def arrange(self, assignments):
        for row in assignments:
            folder = self.workspace.joinpath(*row["path"])
            folder.mkdir(parents=True, exist_ok=True)
            (self.workspace / "inbox" / f"{row['id']}.txt").rename(folder / f"{row['id']}.txt")
        (self.workspace / "inbox").rmdir()

    def test_prepare_writes_inbox_instruction_and_checker(self):
        packet = json.loads((BENCH / "inputs" / "public" / "Recap" / "mini-001.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(p.stem for p in (self.workspace / "inbox").iterdir()), sorted(r["id"] for r in packet["records"]))
        task = (self.run / "TASK.md").read_text(encoding="utf-8")
        self.assertIn(f"All {len(packet['records'])} records start in inbox", task)
        self.assertNotRegex(task.lower(), r"benchmark|score|reference|ami\b")
        self.assertNotIn('"path"', (self.run / "check_inventory.py").read_text(encoding="utf-8").split("EXPECTED")[1].split("def capture")[0])

    def test_score_reproduces_saved_model_output(self):
        prediction = json.loads((BENCH / "predictions" / "Recap" / "mini-001" / "archived_C36.json").read_text(encoding="utf-8"))
        self.arrange(prediction["assignments"])
        quiet("score", str(self.run))
        result = json.loads((self.run / "result.json").read_text(encoding="utf-8"))
        saved = next(row for row in json.loads((BENCH / "saved-results.json").read_text(encoding="utf-8"))
                     if row["prediction"] == ["predictions", "Recap", "mini-001", "archived_C36.json"])
        self.assertTrue(result["valid_output"])
        self.assertAlmostEqual(result["structure_score"], saved["expected"]["primary"]["structure_score"], delta=1e-12)

    def test_checker_flags_changed_and_unplaced_records(self):
        checker = [sys.executable, "-B", str(self.run / "check_inventory.py")]
        self.assertEqual(subprocess.run(checker, capture_output=True).returncode, 1)
        record = next((self.workspace / "inbox").iterdir())
        record.write_text(record.read_text(encoding="utf-8") + " edited", encoding="utf-8")
        output = subprocess.run(checker, capture_output=True, text=True).stdout
        self.assertIn("changed record", output)
        quiet("score", str(self.run))
        result = json.loads((self.run / "result.json").read_text(encoding="utf-8"))
        self.assertFalse(result["valid_output"])
        self.assertEqual(result["structure_score"], 0.0)

    def test_prepare_refuses_non_empty_folder(self):
        with self.assertRaises(SystemExit):
            quiet("prepare", "Recap/mini-001", str(self.run))

    def test_patterns_prepare_score_and_summarize_many_runs(self):
        parent = self.tmp / "design"
        quiet("prepare", "Design/mini-00[12]", str(parent))
        self.assertEqual(sorted(p.name for p in parent.iterdir()), ["mini-001", "mini-002"])
        quiet("score", str(parent / "*"))
        self.assertTrue(all((parent / name / "result.json").is_file() for name in ("mini-001", "mini-002")))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            run_task.main(["summary", str(parent / "*")])
        self.assertRegex(out.getvalue(), r"Design\s+2 task\(s\)")


if __name__ == "__main__":
    unittest.main()
