# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

from infoorgbench_harness.cli import _settings, load_tasks, score_run
from infoorgbench_harness.models.protocols import ANTHROPIC, CHAT, from_responses_request


class HarnessSettingsTests(unittest.TestCase):
    @staticmethod
    def _args(model, max_output_tokens=None):
        class Args:
            request_seconds = 2400
        args = Args()
        args.model, args.max_output_tokens = model, max_output_tokens
        return args

    def test_output_cap_respects_known_model_limit(self):
        self.assertEqual(_settings(self._args("claude-haiku-4.5"))["max_output_tokens"], 64000)
        self.assertIsNone(_settings(self._args("claude-haiku-4.5"))["reasoning_effort"])
        self.assertEqual(_settings(self._args("gpt-6.1-sol"))["max_output_tokens"], 128000)
        self.assertEqual(_settings(self._args("gpt-6.1-sol", 8192))["max_output_tokens"], 8192)

    def test_untyped_input_messages_are_translated(self):
        body = {"model": "m", "input": [{"role": "user", "content": "Reply with OK."}], "max_output_tokens": 16}
        for protocol in (ANTHROPIC, CHAT):
            translated = from_responses_request(body, protocol)
            self.assertEqual(len(translated["messages"]), 1, protocol)


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
