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

import check_release  # noqa: E402


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for name in check_release.REQUIRED_FILES + ("tools/check_release.py",):
            dest = self.tmp / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / name, dest)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, text):
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def manifest(self):
        return json.loads((self.tmp / "release" / "manifest.json").read_text(encoding="utf-8"))

    def save(self, manifest):
        (self.tmp / "release" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def approve_all(self, channel=None, reference="REVIEW-1", decide_licences=True):
        m = self.manifest()
        if decide_licences:
            for comp in m["components"]:
                if comp["license"] == "PENDING-CELA":
                    comp["license"] = comp.get("proposed_license", "MIT")
        for info in m["approvals"].values():
            info["status"], info["reference"] = "approved", reference
        if channel:
            m["channels"][channel]["approved"] = True
        self.save(m)

    def test_repository_passes_staging_gate(self):
        self.assertEqual(check_release.check(ROOT), [])

    def test_repository_is_not_yet_releasable(self):
        for channel in ("public_github", "anonymous_review"):
            problems = check_release.check(ROOT, channel=channel)
            self.assertIn(f"channel {channel} is not approved", problems)

    def test_first_matching_component_owns_file(self):
        comps = check_release.components_from(self.manifest())
        owner = lambda p: check_release.owner_of(p, comps).id
        self.assertEqual(owner("benchmark/predictions/Recap/mini-001/archived_C01.json"), "model-outputs")
        self.assertEqual(owner("benchmark/predictions/Recap/mini-001/filed_flat.json"), "baseline-outputs-and-scores")
        self.assertEqual(owner("benchmark/inputs/public/Design/mini-001.json"), "design-data")
        self.assertEqual(owner("benchmark/engine/infoorgbench.py"), "benchmark-code")

    def test_pending_data_is_allowed_in_staging_but_blocks_channel(self):
        self.write("benchmark/inputs/public/Recap/mini-001.json", "{}")
        self.assertEqual(check_release.check(self.tmp), [])
        m = self.manifest()
        m["channels"]["anonymous_review"]["approved"] = True
        self.save(m)
        problems = check_release.check(self.tmp, channel="anonymous_review")
        self.assertTrue(any(p.startswith("component recap-data: approval dataset_review is ") for p in problems))

    def test_fully_approved_channel_passes(self):
        self.write("benchmark/inputs/public/Recap/mini-001.json", "{}")
        self.approve_all("public_github")
        self.assertEqual(check_release.check(self.tmp, channel="public_github"), [])

    def test_pending_licence_blocks_channel(self):
        self.write("benchmark/predictions/Recap/mini-001/filed_flat.json", "{}")
        self.approve_all("public_github", decide_licences=False)
        problems = check_release.check(self.tmp, channel="public_github")
        self.assertIn("component baseline-outputs-and-scores: licence not yet decided in the dataset review", problems)

    def test_approval_without_reference_is_rejected(self):
        self.write("benchmark/inputs/public/Recap/mini-001.json", "{}")
        self.approve_all("public_github", reference=None)
        problems = check_release.check(self.tmp, channel="public_github")
        self.assertIn("component recap-data: approval dataset_review has no reference", problems)

    def test_thread_text_cannot_be_committed(self):
        self.write("benchmark/inputs/public/Thread/mini-001.json", "{}")
        problems = check_release.check(self.tmp)
        self.assertTrue(any(p.startswith("benchmark/inputs/public/Thread/mini-001.json: must not be committed") for p in problems))

    def test_uncovered_path_is_rejected(self):
        self.write("scratch/notes.txt", "hello")
        self.assertIn("scratch/notes.txt: not covered by any manifest component", check_release.check(self.tmp))

    def test_archive_is_rejected(self):
        (self.tmp / "benchmark").mkdir()
        (self.tmp / "benchmark" / "raw.zip").write_bytes(b"PK\x03\x04")
        self.assertIn("benchmark/raw.zip: archives are not allowed", check_release.check(self.tmp))

    def test_internal_text_is_rejected(self):
        home = "C:" + "\\Users\\someone\\file.txt"
        email = "alias" + "@microsoft.com"
        token = "ghp_" + "a" * 30
        self.write("docs/leak.md", f"{home}\n{email}\n{token}\n")
        labels = " ".join(check_release.check(self.tmp))
        for label in ("Windows user path", "Microsoft email address", "GitHub token"):
            self.assertIn(label, labels)

    def test_upstream_text_is_checked_for_secrets_only(self):
        self.write("benchmark/inputs/public/Recap/x.json", "log at /" + "Users/dev/tmp by dev" + "@example.org\n")
        self.assertEqual(check_release.check(self.tmp), [])
        self.write("benchmark/inputs/public/Recap/y.json", "token ghp_" + "b" * 30 + "\n")
        self.assertTrue(any("GitHub token" in p for p in check_release.check(self.tmp)))

    def test_code_of_conduct_contact_is_allowed(self):
        self.write("docs/contact.md", "opencode" + "@microsoft.com\n")
        self.assertEqual(check_release.check(self.tmp), [])

    def test_local_denylist_with_bom_is_applied(self):
        (self.tmp / ".release-denylist").write_text("\ufeffsecretalias\n", encoding="utf-8")
        self.write("docs/notes.md", "Owner: SecretAlias\n")
        self.assertIn("docs/notes.md:1: denylisted term", check_release.check(self.tmp))

    def test_unknown_licence_is_rejected(self):
        m = self.manifest()
        m["components"][0]["license"] = "GPL-3.0"
        self.save(m)
        self.assertTrue(any("unknown licence" in p for p in check_release.check(self.tmp)))


if __name__ == "__main__":
    unittest.main()