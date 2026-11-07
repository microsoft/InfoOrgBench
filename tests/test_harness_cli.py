# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

from infoorgbench_harness.cli import load_tasks, score_run


class HarnessCLITests(unittest.TestCase):
    def test_loads_selected_recap_task(self):
        rows = load_tasks(ROOT, "Recap", ["mini-001"])
        self.assertEqual([(name, packet["task_id"]) for name, packet in rows], [("mini-001", "ami/mini-001")])

    def test_thread_explains_local_materialization(self):
        public = ROOT / "benchmark" / "inputs" / "public" / "Thread"
        if public.is_dir():
            self.skipTest("Thread packets are already materialized")
        with self.assertRaisesRegex(FileNotFoundError, "benchmark.build_thread"):
            load_tasks(ROOT, "Thread", ["mini-001"])

    def test_scores_release_format_prediction_with_benchmark_engine(self):
        reference = json.loads((ROOT / "benchmark" / "inputs" / "reference" / "Recap" / "mini-001.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            target = run / "Recap" / "mini-001.json"
            target.parent.mkdir()
            target.write_text(json.dumps({"assignments": [{"id": row["id"], "path": row["path"]}
                                                            for row in reference["records"]]}), encoding="utf-8")
            report = score_run(ROOT, run)
        self.assertEqual(report["tasks_scored"], 1)
        self.assertEqual(report["families"]["Recap"]["structure_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
