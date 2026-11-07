# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
ASSIGNMENTS = RESULTS / "assignments"


def load_rescore():
    spec = importlib.util.spec_from_file_location("rescore", RESULTS / "rescore.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AssignmentReleaseTests(unittest.TestCase):
    def test_assignment_files_match_system_ledger(self):
        systems = json.loads((RESULTS / "systems.json").read_text(encoding="utf-8"))["systems"]
        expected = {entry["key"] for entry in systems}
        actual = {path.stem for path in ASSIGNMENTS.glob("*.json") if path.name != "MANIFEST-COMPONENTS.json"}
        self.assertEqual(actual, expected)

    def test_assignment_shape_contains_only_ids_and_paths(self):
        systems = json.loads((RESULTS / "systems.json").read_text(encoding="utf-8"))["systems"]
        for entry in systems:
            path = ASSIGNMENTS / f"{entry['key']}.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(set(data), {"system", "model", "harness", "tasks"}, path)
            self.assertEqual(data["system"], entry["key"], path)
            self.assertEqual(data["model"], entry["model"]["display_name"], path)
            self.assertEqual(data["harness"], entry["harness"]["display_name"], path)
            self.assertIsInstance(data["tasks"], dict, path)
            self.assertLessEqual(len(data["tasks"]), 150, path)
            for task, result in data["tasks"].items():
                self.assertRegex(task, r"^(Recap|Thread|Design)/mini-\d{3}$")
                self.assertEqual(set(result), {"run", "assignments"}, (path, task))
                self.assertIsInstance(result["run"], str, (path, task))
                self.assertTrue(result["run"], (path, task))
                self.assertIsInstance(result["assignments"], list, (path, task))
                seen = set()
                for assignment in result["assignments"]:
                    self.assertEqual(set(assignment), {"id", "path"}, (path, task))
                    self.assertRegex(assignment["id"], r"^F\d{3}$")
                    self.assertNotIn(assignment["id"], seen, (path, task))
                    seen.add(assignment["id"])
                    self.assertIsInstance(assignment["path"], list, (path, task))
                    self.assertGreaterEqual(len(assignment["path"]), 1, (path, task))
                    self.assertLessEqual(len(assignment["path"]), 4, (path, task))
                    self.assertTrue(all(isinstance(label, str) and label for label in assignment["path"]),
                                    (path, task))
                family, task_id = task.split("/", 1)
                reference = json.loads((ROOT / "benchmark" / "inputs" / "reference" / family
                                        / f"{task_id}.json").read_text(encoding="utf-8"))
                self.assertEqual(seen, {row["id"] for row in reference["records"]}, (path, task))

    def test_rescore_passes_non_thread_families(self):
        result = load_rescore().rescore(ROOT, families=("Recap", "Design"))
        self.assertTrue(result["passed"], result)
        self.assertGreater(result["outputs_checked"], 0)
        self.assertEqual(result["metric_mismatches"], [])


if __name__ == "__main__":
    unittest.main()
