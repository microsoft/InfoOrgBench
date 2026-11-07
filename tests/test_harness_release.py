# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_release
sys.path.insert(0, str(ROOT / "harness"))
from infoorgbench_harness.cli import PAPER_PROFILE


class HarnessReleaseTests(unittest.TestCase):
    def test_table3_configuration_has_all_45_systems(self):
        value = json.loads((ROOT / "harness" / "configs" / "table3-systems.json").read_text(encoding="utf-8"))
        self.assertEqual(len(value["systems"]), 45)
        self.assertEqual({row["harness"] for row in value["systems"]},
                         {"react-fc", "codex", "pi", "dsh", "deepagents"})

    def test_harness_has_no_release_gate_leaks(self):
        problems = []
        for path in (ROOT / "harness").rglob("*"):
            if path.is_file():
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                problems.extend(check_release.scan_text(path.relative_to(ROOT).as_posix(), text, []))
        self.assertEqual(problems, [])

    def test_new_python_sources_have_mit_header(self):
        expected = "# Copyright (c) Microsoft Corporation.\n# Licensed under the MIT License.\n"
        for path in [*(ROOT / "harness").rglob("*.py"), *(ROOT / "tests").glob("test_harness_*.py")]:
            with self.subTest(path=path.name):
                self.assertTrue(path.read_text(encoding="utf-8").startswith(expected))

    def test_runtime_defaults_match_released_configuration(self):
        value = json.loads((ROOT / "harness" / "configs" / "defaults.json").read_text(encoding="utf-8"))
        self.assertEqual(value["paper_profile"], PAPER_PROFILE)
        self.assertIsNone(value["model_overrides"]["claude-haiku-4.5"]["reasoning_effort"])


if __name__ == "__main__":
    unittest.main()
