import json
import shutil
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

import build_thread  # noqa: E402

ISSUE = {"key": "HADOOP-1", "fields": {
    "summary": "Fix the reader", "description": "It fails on large files.", "status": {"name": "Resolved"},
    "comment": {"comments": [{"id": "10", "body": "Patch attached."}]}}}


class BuildThreadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.pkg = self.tmp / "pkg"
        texts = {"F001": "Patch attached.", "F002": "Fix the reader\n\nIt fails on large files.\n\nStatus: Resolved"}
        (self.pkg / "sources" / "hadoop-jira").mkdir(parents=True)
        (self.pkg / "sources" / "hadoop-jira" / "issues.json").write_text(json.dumps({"issues": [
            {"key": "HADOOP-1", "rest_url": "https://example.invalid/HADOOP-1", "save_as": "HADOOP-1.json"}]}), encoding="utf-8")
        (self.pkg / "inputs" / "reference" / "Thread").mkdir(parents=True)
        reference = {"task_id": "hadoop-jira/mini-001",
                     "records": [{"id": k, "path": ["HADOOP-1"], "content_sha256": sha256(v.encode()).hexdigest()} for k, v in texts.items()],
                     "provenance": [{"id": "F001", "native_id": "HADOOP-1/comment/10", "role": "comment"},
                                    {"id": "F002", "native_id": "HADOOP-1", "role": "subtask"}]}
        (self.pkg / "inputs" / "reference" / "Thread" / "mini-001.json").write_text(json.dumps(reference), encoding="utf-8")
        packet = build_thread.serialize({"task_id": "hadoop-jira/mini-001",
                                         "records": [{"id": k, "format": "text", "text": v} for k, v in texts.items()]})
        (self.pkg / "manifest.json").write_text(json.dumps({"files": [
            {"parts": ["inputs", "public", "Thread", "mini-001.json"], "sha256": sha256(packet).hexdigest(), "build": "build_thread.py"}]}), encoding="utf-8")
        self.expected = packet
        self.responses = self.tmp / "responses"
        self.responses.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def save(self, issue):
        (self.responses / "HADOOP-1.json").write_text(json.dumps(issue), encoding="utf-8")

    def test_rebuilds_packet_byte_for_byte(self):
        self.save(ISSUE)
        result = build_thread.build(self.pkg, self.responses)
        self.assertEqual((result["built"], result["total"], result["failed"]), (1, 1, []))
        self.assertEqual((self.pkg / "inputs/public/Thread/mini-001.json").read_bytes(), self.expected)

    def test_reports_missing_responses(self):
        result = build_thread.build(self.pkg, self.responses)
        self.assertEqual([m["key"] for m in result["missing_issues"]], ["HADOOP-1"])

    def test_changed_upstream_text_is_not_written(self):
        changed = json.loads(json.dumps(ISSUE))
        changed["fields"]["status"]["name"] = "Reopened"
        self.save(changed)
        result = build_thread.build(self.pkg, self.responses)
        self.assertEqual(result["built"], 0)
        self.assertIn("F002", result["failed"][0]["problems"][0])
        self.assertFalse((self.pkg / "inputs/public/Thread/mini-001.json").exists())

    def test_check_only_writes_nothing(self):
        self.save(ISSUE)
        result = build_thread.build(self.pkg, self.responses, check_only=True)
        self.assertEqual(result["built"], 1)
        self.assertFalse((self.pkg / "inputs/public/Thread").exists())


if __name__ == "__main__":
    unittest.main()
