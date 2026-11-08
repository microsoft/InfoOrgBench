# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

from infoorgbench_harness.models.copilot import CopilotBackend, _helper_environment
from infoorgbench_harness.models.http import TransportError
from infoorgbench_harness.models.protocols import ANTHROPIC, RESPONSES


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


class _AnthropicCaptureServer(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, _format, *_args):
        return

    def do_POST(self):
        self.__class__.seen.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        payload = json.dumps({"id": "a", "type": "message", "role": "assistant", "model": "claude",
                              "content": [], "stop_reason": "end_turn",
                              "usage": {"input_tokens": 1, "output_tokens": 1}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class _CopilotRedirectServer(BaseHTTPRequestHandler):
    destination_hits = 0

    def log_message(self, _format, *_args):
        return

    def do_POST(self):
        if self.path == "/destination":
            self.__class__.destination_hits += 1
            self.send_response(200)
        else:
            self.send_response(307)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/destination")
        self.send_header("Content-Length", "0")
        self.end_headers()


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
        previous = os.environ.get("COPILOT_GITHUB_TOKEN")
        os.environ["COPILOT_GITHUB_TOKEN"] = "test-token"
        backend = CopilotBackend(helper_command=[sys.executable, str(self.helper)],
                                 token_env="COPILOT_GITHUB_TOKEN", working_directory=self.temp.name)
        try:
            raw, content_type = backend.request(RESPONSES, {"model": "gpt-6-luna", "input": "x", "stream": False})
        finally:
            backend.close()
            if previous is None:
                os.environ.pop("COPILOT_GITHUB_TOKEN", None)
            else:
                os.environ["COPILOT_GITHUB_TOKEN"] = previous
        self.assertEqual(content_type, "application/json")
        self.assertEqual(json.loads(raw)["usage"]["total_tokens"], 2)
        self.assertEqual([row["authorization"] for row in _EndpointServer.seen],
                         ["Bearer returned-1", "Bearer returned-2"])
        self.assertEqual([row["session"] for row in _EndpointServer.seen], ["session-secret", "session-secret"])
        rendered = json.dumps(backend.public_metadata())
        self.assertNotIn("endpoint", rendered.lower())
        for secret in ("base-secret", "returned-1", "returned-2", "session-secret", "127.0.0.1"):
            self.assertNotIn(secret, rendered)

    def test_copilot_anthropic_same_protocol_is_true_pass_through(self):
        _AnthropicCaptureServer.seen = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), _AnthropicCaptureServer)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        backend = CopilotBackend.__new__(CopilotBackend)
        backend.protocol = ANTHROPIC
        backend.timeout_seconds = 5
        body = {"model": "claude", "messages": [{"role": "user", "content": "x"}],
                "max_tokens": 32, "thinking": {"type": "adaptive"},
                "output_config": {"effort": "medium"}}
        endpoint = {"type": "anthropic", "baseUrl": f"http://127.0.0.1:{server.server_port}"}
        try:
            backend._send(ANTHROPIC, body, endpoint)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
        self.assertEqual(_AnthropicCaptureServer.seen, [body])

    def test_copilot_model_request_does_not_follow_redirect(self):
        _CopilotRedirectServer.destination_hits = 0
        server = ThreadingHTTPServer(("127.0.0.1", 0), _CopilotRedirectServer)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        backend = CopilotBackend.__new__(CopilotBackend)
        backend.protocol = RESPONSES
        backend.timeout_seconds = 5
        endpoint = {"type": "openai", "wireApi": "responses",
                    "baseUrl": f"http://127.0.0.1:{server.server_port}"}
        try:
            with self.assertRaises(TransportError) as raised:
                backend._send(RESPONSES, {"model": "m", "input": "x"}, endpoint)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
        self.assertEqual(raised.exception.http_status, 307)
        self.assertEqual(_CopilotRedirectServer.destination_hits, 0)

    def test_helper_process_environment_is_allowlisted(self):
        source = {"PATH": "bin", "SYSTEMROOT": "system", "USERPROFILE": "profile",
                  "NPM_CONFIG_PREFIX": "prefix", "NPM_CONFIG__AUTHTOKEN": "secret",
                  "COPILOT_GITHUB_TOKEN": "secret", "OPENAI_API_KEY": "secret",
                  "AWS_SECRET_ACCESS_KEY": "secret", "DATABASE_URL": "secret"}
        env = _helper_environment("COPILOT_GITHUB_TOKEN", source)
        self.assertEqual(env, {"PATH": "bin", "SYSTEMROOT": "system", "USERPROFILE": "profile",
                               "NPM_CONFIG_PREFIX": "prefix"})

    @unittest.skipUnless(shutil.which("node"), "Node is not installed")
    def test_node_helper_child_environments_exclude_all_secrets(self):
        helper = ROOT / "harness" / "copilot" / "endpoint.mjs"
        env = {"PATH": os.environ.get("PATH", ""), "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
               "NPM_CONFIG_PREFIX": "prefix", "NPM_CONFIG__AUTHTOKEN": "secret",
               "COPILOT_GITHUB_TOKEN": "secret", "OPENAI_API_KEY": "secret",
               "AWS_SECRET_ACCESS_KEY": "secret", "DATABASE_URL": "secret"}
        value = json.loads(subprocess.run([shutil.which("node"), str(helper), "--test-environments"],
                                          capture_output=True, text=True, check=True, env=env).stdout)
        self.assertIn("NPM_CONFIG_PREFIX", value["npm"])
        self.assertNotIn("NPM_CONFIG_PREFIX", value["runtime"])
        for names in value.values():
            for secret_name in ("COPILOT_GITHUB_TOKEN", "OPENAI_API_KEY", "NPM_CONFIG__AUTHTOKEN",
                                "AWS_SECRET_ACCESS_KEY", "DATABASE_URL"):
                self.assertNotIn(secret_name, names)


if __name__ == "__main__":
    unittest.main()
