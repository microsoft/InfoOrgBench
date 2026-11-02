# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_anonymous  # noqa: E402

CONFIG = json.loads((ROOT / "release" / "anonymization.json").read_text(encoding="utf-8"))


class AnonymizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tree(self, files):
        out = {}
        for rel, text in files.items():
            path = self.tmp / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            out[rel] = path
        return out

    def test_repository_copy_is_anonymous(self):
        tree = build_anonymous.plan(ROOT, CONFIG)
        self.assertEqual(build_anonymous.verify(tree, CONFIG), [])
        self.assertNotIn("CODE_OF_CONDUCT.md", tree)
        self.assertEqual(tree["README.md"], ROOT / "release" / "anonymous" / "README.md")

    def test_upstream_text_may_mention_microsoft(self):
        tree = self.tree({"benchmark/inputs/public/Design/x.json": "Microsoft Windows containers"})
        self.assertEqual(build_anonymous.verify(tree, CONFIG), [])

    def test_copyright_header_is_neutralized(self):
        tree = self.tree({"benchmark/engine/x.py": "# Copyright (c) Microsoft Corporation.\n# Licensed under the MIT License.\n"})
        self.assertEqual(build_anonymous.verify(tree, CONFIG), [])
        out = self.tmp / "out"
        build_anonymous.materialize(tree, out)
        self.assertIn("The InfoOrgBench authors", (out / "benchmark/engine/x.py").read_text(encoding="utf-8"))

    def test_identity_outside_upstream_text_is_rejected(self):
        tree = self.tree({"benchmark/engine/x.py": "# Maintained by Microsoft Research."})
        self.assertTrue(any("identity marker" in p for p in build_anonymous.verify(tree, CONFIG)))

    def test_private_term_is_rejected(self):
        tree = self.tree({"benchmark/engine/x.py": "# owner: SomeAlias"})
        config = dict(CONFIG, private_terms=["somealias"])
        self.assertTrue(any("private term" in p for p in build_anonymous.verify(tree, config)))

    def test_term_in_data_is_rejected(self):
        tree = self.tree({"benchmark/inputs/public/Recap/x.json": "owner jou2024"})
        self.assertTrue(any("anonymization term" in p for p in build_anonymous.verify(tree, CONFIG)))


if __name__ == "__main__":
    unittest.main()