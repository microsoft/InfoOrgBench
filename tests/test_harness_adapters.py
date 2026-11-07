# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

from infoorgbench_harness.adapters import PINS, build_codex_invocation, build_dsh_patch, run_third_party
from infoorgbench_harness.models.protocols import RESPONSES


class AdapterConfigurationTests(unittest.TestCase):
    def test_paper_harness_versions_are_frozen(self):
        self.assertEqual(PINS, {"codex": "0.162.1", "pi": "1.1.0",
                                "dsh": "0.2.1-alpha.1", "deepagents": "0.7.23"})

    def test_codex_invocation_disables_unrecorded_capabilities(self):
        invocation = build_codex_invocation("codex", Path("workspace"), Path("run"),
                                            "http://127.0.0.1:1234/v1", "gpt-6.1-sol", "medium")
        rendered = " ".join(invocation)
        for value in ('approval_policy="never"', 'web_search="disabled"',
                      "features.multi_agent=false", "features.memories=false",
                      'wire_api="responses"', "request_max_retries=0", "stream_max_retries=0"):
            self.assertIn(value, rendered)

    def test_dsh_patch_disables_memory_telemetry_and_subagents(self):
        patch = build_dsh_patch(Path("workspace").resolve(), "http://127.0.0.1:1234/v1",
                                "gpt-6.1-sol", 128000, "medium")
        self.assertIn("agents: []", patch)
        self.assertIn("mode: workspace-write", patch)
        self.assertIn("telemetry", patch)
        self.assertIn("memory", patch)
        self.assertIn("maxRetries: 0", patch)

    def test_native_failure_still_returns_independent_capture(self):
        class UnusedBackend:
            protocol = RESPONSES

        packet = {"task_id": "synthetic", "records": [{"id": "F001", "format": "text", "text": "one"}]}
        settings = {"max_output_tokens": 100, "reasoning_effort": None}
        with tempfile.TemporaryDirectory() as temporary, patch(
                "infoorgbench_harness.adapters._run_codex", side_effect=RuntimeError("failed")):
            result = run_third_party(packet, harness="codex", family="Recap", model="m",
                                     backend=UnusedBackend(), settings=settings,
                                     run_root=Path(temporary) / "run")
        self.assertEqual(result["status"], "failed:RuntimeError")
        self.assertTrue(result["inventory_preserved"])
        self.assertEqual(result["assignments"], [{"id": "F001", "path": ["inbox"]}])


if __name__ == "__main__":
    unittest.main()
