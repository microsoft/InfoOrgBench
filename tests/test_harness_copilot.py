# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

from infoorgbench_harness.models.copilot import CopilotBackend
from infoorgbench_harness.models.protocols import RESPONSES


class _EndpointServer(BaseHTTPRequestHandler):
    seen = []
    failures = 1

    def log_message(self, _format, *_args):
        return

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        self.__class__.seen.append({"authorization": self.headers.get("Authorization"),
                                    "session": self.headers.get("X-Session"), "body": body})
        if self.__class__.failures:
            self.__class__.failures -= 1
            self.send_response(401)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        payload = json.dumps({"id": "r", "object": "response", "model": body["model"], "status": "completed",
                              "output": [], "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class CopilotBackendTests(unittest.TestCase):
    def setUp(self):
        _EndpointServer.seen = []
        _EndpointServer.failures = 1
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _EndpointServer)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.temp = tempfile.TemporaryDirectory()
        helper = Path(self.temp.name) / "fake_helper.py"
        helper.write_text('''# Copyright (c) Microsoft Corporation.\n# Licensed under the MIT License.\nimport json,sys\ncount=0\nfor line in sys.stdin:\n command=json.loads(line)\n if command["command"]=="init": print(json.dumps({"ok":True}),flush=True)\n elif command["command"]=="endpoint":\n  count+=1\n  print(json.dumps({"ok":True,"endpoint":{"type":"openai","wireApi":"responses","baseUrl":"http://127.0.0.1:%d/v1","apiKey":"base-secret","headers":{"Authorization":"Bearer returned-%%d"%%count},"sessionToken":{"header":"X-Session","token":"session-secret","expiresAt":"2999-01-01T00:00:00Z"}}}),flush=True)\n elif command["command"]=="close": print(json.dumps({"ok":True}),flush=True); break\n''' % self.server.server_port, encoding="utf-8")
        self.helper = helper

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def test_returned_headers_override_api_key_and_refresh_after_401(self):
        backend = CopilotBackend(helper_command=[sys.executable, str(self.helper)],
                                 token_env="COPILOT_GITHUB_TOKEN", working_directory=self.temp.name)
        try:
            raw, content_type = backend.request(RESPONSES, {"model": "gpt-6-luna", "input": "x", "stream": False})
        finally:
            backend.close()
        self.assertEqual(content_type, "application/json")
        self.assertEqual(json.loads(raw)["usage"]["total_tokens"], 2)
        self.assertEqual([row["authorization"] for row in _EndpointServer.seen],
                         ["Bearer returned-1", "Bearer returned-2"])
        self.assertEqual([row["session"] for row in _EndpointServer.seen], ["session-secret", "session-secret"])
        rendered = json.dumps(backend.public_metadata())
        self.assertNotIn("endpoint", rendered.lower())
        for secret in ("base-secret", "returned-1", "returned-2", "session-secret", "127.0.0.1"):
            self.assertNotIn(secret, rendered)


if __name__ == "__main__":
    unittest.main()
