# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import hashlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

from infoorgbench_harness import deepagents_worker
from infoorgbench_harness.adapters import run_third_party
from infoorgbench_harness.cli import parser, run_command
from infoorgbench_harness.receipts import make_receipt
from infoorgbench_harness.skills import (
    fetch_skills, install_codex_skills, load_skills, receipt_block, skill_name, worker_config,
)

SKILL = "---\nname: file-organizer\ndescription: Organize files.\n---\n\n# File Organizer\nGroup related files.\n"


def _skill_directory(root, directory="file-organizer", text=SKILL):
    path = Path(root) / directory
    path.mkdir(parents=True)
    (path / "SKILL.md").write_bytes(text.encode("utf-8"))
    return path


class SkillLoadingTests(unittest.TestCase):
    def test_skill_name_reads_frontmatter_names(self):
        self.assertEqual(skill_name(SKILL), "file-organizer")
        self.assertEqual(skill_name('---\nname: "File Organizer"\ndescription: x\n---\nbody'), "File Organizer")
        with self.assertRaises(ValueError):
            skill_name("# no frontmatter")

    def test_worker_config_seeds_skill_files_under_the_skills_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = load_skills([_skill_directory(temporary)], "pinned")
        config = worker_config(bundle)
        self.assertEqual(config["mode"], "pinned")
        self.assertEqual(config["names"], ["file-organizer"])
        self.assertEqual(config["files"], {"/skills/file-organizer/SKILL.md": SKILL})
        self.assertEqual(deepagents_worker.SKILLS_SOURCE, "/skills/")

    def test_receipt_block_is_content_free(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = load_skills([_skill_directory(temporary)], "available")
        block = receipt_block(bundle)
        self.assertNotIn("Group related files", json.dumps(block))
        self.assertEqual(block["skills"][0]["sha256"], hashlib.sha256(SKILL.encode()).hexdigest())

    def test_rejects_missing_skill_unknown_mode_and_duplicate_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileNotFoundError):
                load_skills([Path(temporary)], "pinned")
            first = _skill_directory(Path(temporary) / "a")
            second = _skill_directory(Path(temporary) / "b")
            with self.assertRaises(ValueError):
                load_skills([first], "always")
            with self.assertRaisesRegex(ValueError, "distinct"):
                load_skills([first, second], "pinned")


class SkillFetchTests(unittest.TestCase):
    @staticmethod
    def _manifest(directory, data, commit="a" * 40):
        manifest = {"skills": [{"id": "example", "repository": "owner/repo", "commit": commit,
                                "path": "file-organizer/SKILL.md", "directory": "file-organizer",
                                "sha256": hashlib.sha256(data).hexdigest()}]}
        path = Path(directory) / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def test_fetch_verifies_hash_and_uses_pinned_commit(self):
        data = SKILL.encode()
        urls = []

        def opener(request, timeout):
            urls.append(request.full_url)
            return io.BytesIO(data)
        with tempfile.TemporaryDirectory() as temporary:
            written = fetch_skills(self._manifest(temporary, data), Path(temporary) / "out", opener=opener)
            self.assertEqual((Path(written[0]) / "SKILL.md").read_bytes(), data)
        self.assertEqual(urls, ["https://raw.githubusercontent.com/owner/repo/" + "a" * 40 + "/file-organizer/SKILL.md"])

    def test_fetch_rejects_changed_text_and_branch_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                fetch_skills(self._manifest(temporary, b"original"), Path(temporary) / "out",
                             opener=lambda request, timeout: io.BytesIO(b"changed"))
            with self.assertRaisesRegex(ValueError, "full SHA-1"):
                fetch_skills(self._manifest(temporary, b"x", commit="main"), Path(temporary) / "out",
                             opener=lambda request, timeout: io.BytesIO(b"x"))

    def test_community_manifest_pins_distinct_skills(self):
        manifest = json.loads((ROOT / "harness" / "configs" / "community-skills.json").read_text(encoding="utf-8"))
        rows = manifest["skills"]
        self.assertGreaterEqual(len(rows), 3)
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        for row in rows:
            self.assertRegex(row["commit"], r"^[0-9a-f]{40}$")
            self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual([row["installs"] for row in rows], sorted((row["installs"] for row in rows), reverse=True))
        for row in manifest["controls"]:
            self.assertRegex(row["commit"], r"^[0-9a-f]{40}$")
            self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")


class SkillRunTests(unittest.TestCase):
    def test_skill_options_parse_and_default_to_available(self):
        args = parser().parse_args(["run", "--harness", "deepagents", "--model", "m", "--backend", "copilot",
                                    "--family", "Recap", "--out", "run", "--skill", "one", "--skill", "two"])
        self.assertEqual(args.skill, [Path("one"), Path("two")])
        self.assertEqual(args.skill_mode, "available")

    def test_skills_are_rejected_for_other_harnesses(self):
        with tempfile.TemporaryDirectory() as temporary:
            skill = _skill_directory(temporary)
            out = Path(temporary) / "run"
            args = parser().parse_args(["run", "--harness", "react-fc", "--model", "m", "--backend", "copilot",
                                        "--family", "Recap", "--out", str(out), "--skill", str(skill)])
            with self.assertRaisesRegex(ValueError, "deepagents"):
                run_command(args)
            self.assertFalse(out.exists())
            with self.assertRaisesRegex(ValueError, "Deep Agents and Codex"):
                run_third_party({"records": []}, harness="pi", family="Recap", model="m", backend=None,
                                settings={}, run_root=Path(temporary) / "pi", skills={"mode": "pinned"})

    def test_codex_skills_install_under_codex_home_and_pin_body_without_frontmatter(self):
        with tempfile.TemporaryDirectory() as temporary:
            pinned = load_skills([_skill_directory(Path(temporary) / "a")], "pinned")
            text = install_codex_skills(pinned, Path(temporary) / "codex-home")
            installed = Path(temporary) / "codex-home" / "skills" / "file-organizer" / "SKILL.md"
            self.assertEqual(installed.read_bytes(), SKILL.encode())
            self.assertTrue(text.startswith('<skill name="file-organizer" path="'))
            self.assertIn("Group related files.", text)
            self.assertNotIn("description: Organize files.", text)
            available = load_skills([_skill_directory(Path(temporary) / "b")], "available")
            self.assertEqual(install_codex_skills(available, Path(temporary) / "codex-home-2"), "")
            self.assertTrue((Path(temporary) / "codex-home-2" / "skills" / "file-organizer" / "SKILL.md").is_file())

    def test_receipt_keeps_skill_identity_and_only_numeric_episode_counts(self):
        receipt = make_receipt(harness="deepagents", model="m", backend="copilot", family="Recap",
                               task_id="mini-001", status="completed", settings={}, hashes={}, usage={},
                               versions={}, skills={"mode": "pinned", "skills": []},
                               agent_stats={"model_turns": 3, "tool_calls": {"record_move": 2, "bad": "text"},
                                            "note": "free text", "negative": -1})
        self.assertEqual(receipt["skills"]["mode"], "pinned")
        self.assertEqual(receipt["agent_stats"], {"model_turns": 3, "tool_calls": {"record_move": 2}})
        plain = make_receipt(harness="pi", model="m", backend="copilot", family="Recap", task_id="mini-001",
                             status="completed", settings={}, hashes={}, usage={}, versions={})
        self.assertNotIn("skills", plain)
        self.assertNotIn("agent_stats", plain)

    def test_episode_stats_count_tool_calls_and_skill_reads(self):
        def ai(*calls):
            return SimpleNamespace(type="ai", tool_calls=list(calls), additional_kwargs={})
        messages = [
            SimpleNamespace(type="human", tool_calls=None, additional_kwargs={}),
            SimpleNamespace(type="human", tool_calls=None, additional_kwargs={"lc_source": "pinned_skill"}),
            ai({"name": "read_file", "id": "1", "args": {"file_path": "/skills/file-organizer/SKILL.md"}},
               {"name": "record_list", "id": "2", "args": {}}),
            SimpleNamespace(type="tool", tool_call_id="1", status="success", additional_kwargs={}),
            SimpleNamespace(type="tool", tool_call_id="2", status="success", additional_kwargs={}),
            ai(),
        ]
        stats = deepagents_worker.episode_stats(messages)
        self.assertEqual(stats, {"model_turns": 2, "tool_calls": {"read_file": 1, "record_list": 1},
                                 "skill_file_reads": 1, "skill_file_reads_ok": 1, "skill_md_reads": 1,
                                 "pinned_skill_messages": 1})

    def test_control_worker_keeps_the_paper_tool_exclusions(self):
        self.assertIn("read_file", deepagents_worker.EXCLUDED_TOOLS)
        source = (ROOT / "harness" / "infoorgbench_harness" / "deepagents_worker.py").read_text(encoding="utf-8")
        self.assertRegex(source, re.escape('skills=[SKILLS_SOURCE] if skills else None'))


if __name__ == "__main__":
    unittest.main()
