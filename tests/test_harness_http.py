# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

from infoorgbench_harness.models.http import ProviderBackend
from infoorgbench_harness.models.protocols import ANTHROPIC, CHAT, RESPONSES, decode_response, encode_response


class _WireServer(BaseHTTPRequestHandler):
    protocol = RESPONSES
    seen = []

    def log_message(self, _format, *_args):
        return

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.__class__.seen.append((self.path, dict(self.headers), body))
        response = {"id": "r", "object": "response", "model": body["model"], "status": "completed",
                    "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "ok"}]}],
                    "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}}
        raw, content_type = encode_response(response, self.__class__.protocol, stream=True)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class ProviderBackendTests(unittest.TestCase):
    def test_all_provider_protocols_accept_responses_and_return_sse(self):
        previous = dict(os.environ)
        try:
            for protocol, backend_name, key_env in ((RESPONSES, "openai", "TEST_OPENAI_KEY"),
                                                     (CHAT, "openai-chat", "TEST_CHAT_KEY"),
                                                     (ANTHROPIC, "anthropic", "TEST_ANTHROPIC_KEY")):
                with self.subTest(protocol=protocol):
                    _WireServer.protocol, _WireServer.seen = protocol, []
                    server = ThreadingHTTPServer(("127.0.0.1", 0), _WireServer)
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    os.environ[key_env] = "test-only-key"
                    try:
                        backend = ProviderBackend(backend_name, base_url=f"http://127.0.0.1:{server.server_port}/v1",
                                                  key_env=key_env)
                        raw, content_type = backend.request(RESPONSES, {
                            "model": "m", "instructions": "rules", "input": "hello", "stream": True,
                            "store": False, "max_output_tokens": 100})
                    finally:
                        server.shutdown(); server.server_close(); thread.join(timeout=5)
                    decoded = decode_response(raw, protocol, content_type)
                    self.assertEqual(decoded["usage"]["total_tokens"], 5)
                    self.assertEqual(decoded["output"][0]["content"][0]["text"], "ok")
                    self.assertNotIn("test-only-key", json.dumps(backend.public_metadata()))
                    if protocol == RESPONSES:
                        self.assertIs(_WireServer.seen[0][2]["store"], False)
        finally:
            os.environ.clear(); os.environ.update(previous)

    def test_base_url_cannot_contain_credentials(self):
        with self.assertRaises(ValueError):
            ProviderBackend("openai-chat", base_url="https://user:password@example.test/v1",
                            key_env="TEST_CHAT_KEY")


if __name__ == "__main__":
    unittest.main()
