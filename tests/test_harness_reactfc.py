# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import importlib
import json
import os
import sys
import tempfile
import threading
import unittest
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "benchmark" / "engine"))

from infoorgbench_harness.models.http import ProviderBackend
from infoorgbench_harness.models.protocols import ANTHROPIC, CHAT, RESPONSES, encode_response
from infoorgbench_harness.reactfc import run_episode


class _EpisodeServer(BaseHTTPRequestHandler):
    protocol = RESPONSES
    groups = []
    assignments = []
    calls = 0

    def log_message(self, _format, *_args):
        return

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        cls = self.__class__
        cls.calls += 1
        if cls.calls == 1:
            output = [{"type": "function_call", "call_id": f"move-{index}", "name": "move_files",
                       "arguments": json.dumps({"file_ids": ids, "folder_path": list(path)}, separators=(",", ":"))}
                      for index, (path, ids) in enumerate(cls.groups)]
        elif cls.calls == 2:
            output = [{"type": "function_call", "call_id": "check-1", "name": "check_inventory", "arguments": "{}"}]
        else:
            output = [{"type": "message", "role": "assistant", "content": [{"type": "output_text",
                       "text": json.dumps({"assignments": cls.assignments}, separators=(",", ":"))}]}]
        response = {"id": f"r-{cls.calls}", "object": "response", "model": body["model"], "status": "completed",
                    "output": output, "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}}
        raw, content_type = encode_response(response, cls.protocol, stream=True)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class FullReactFCEpisodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads((ROOT / "benchmark" / "inputs" / "public" / "Recap" / "mini-001.json").read_text(encoding="utf-8"))
        cls.reference = json.loads((ROOT / "benchmark" / "inputs" / "reference" / "Recap" / "mini-001.json").read_text(encoding="utf-8"))
        cls.assignments = [{"id": row["id"], "path": ["Organized"]} for row in cls.reference["records"]]
        cls.groups = [(('Organized',), [row["id"] for row in cls.assignments])]

    def test_three_streaming_wire_protocols_complete_and_score(self):
        old = dict(os.environ)
        try:
            for protocol, backend_name, key_env in ((RESPONSES, "openai", "TEST_OPENAI_KEY"),
                                                     (CHAT, "openai-chat", "TEST_CHAT_KEY"),
                                                     (ANTHROPIC, "anthropic", "TEST_ANTHROPIC_KEY")):
                with self.subTest(protocol=protocol), tempfile.TemporaryDirectory() as work:
                    _EpisodeServer.protocol = protocol
                    _EpisodeServer.groups = self.groups
                    _EpisodeServer.assignments = self.assignments
                    _EpisodeServer.calls = 0
                    server = ThreadingHTTPServer(("127.0.0.1", 0), _EpisodeServer)
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    os.environ[key_env] = "test-only-key"
                    try:
                        backend = ProviderBackend(backend_name, base_url=f"http://127.0.0.1:{server.server_port}/v1",
                                                  key_env=key_env)
                        result = run_episode(self.packet, family="Recap", model="test-model", backend=backend,
                                             settings={"max_output_tokens": 128000, "reasoning_effort": "medium",
                                                       "request_seconds": 10, "decision_turns": None,
                                                       "episode_seconds": None, "episode_observed_token_stop": None},
                                             workspace_root=Path(work) / "workspace")
                    finally:
                        server.shutdown(); server.server_close(); thread.join(timeout=5)
                    self.assertTrue(result["inventory_preserved"])
                    self.assertTrue(result["checker_matches_final_state"])
                    self.assertEqual(result["assignments"], self.assignments)
                    self.assertEqual(result["usage"]["total_tokens"], 45)
                    benchmark = importlib.import_module("infoorgbench")
                    score, _ = benchmark.scorer("native")
                    metrics = score(self.packet, self.reference, {"assignments": result["assignments"]})
                    self.assertTrue(metrics["valid_output"])
                    self.assertIsNotNone(metrics["main"]["structure_score"])
        finally:
            os.environ.clear(); os.environ.update(old)

    def test_transport_failure_still_captures_authoritative_state(self):
        class FailingBackend:
            protocol = RESPONSES
            calls = 0

            def request(self, _protocol, body):
                self.calls += 1
                if self.calls > 1:
                    raise RuntimeError("test transport failure")
                response = {"id": "r", "object": "response", "model": body["model"], "status": "completed",
                            "output": [{"type": "function_call", "call_id": "move", "name": "move_files",
                                        "arguments": json.dumps({"file_ids": ["F001"], "folder_path": ["Filed"]})}],
                            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}
                return encode_response(response, RESPONSES, stream=True)

        packet = {"task_id": "synthetic", "records": [{"id": "F001", "format": "text", "text": "one"}]}
        with tempfile.TemporaryDirectory() as work:
            result = run_episode(packet, family="Recap", model="test-model", backend=FailingBackend(),
                                 settings={"max_output_tokens": 100, "reasoning_effort": None,
                                           "request_seconds": 10, "decision_turns": None,
                                           "episode_seconds": None, "episode_observed_token_stop": None},
                                 workspace_root=Path(work) / "workspace")
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["assignments"], [{"id": "F001", "path": ["Filed"]}])
        self.assertTrue(result["inventory_preserved"])


if __name__ == "__main__":
    unittest.main()
