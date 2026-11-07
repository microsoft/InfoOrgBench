# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import json
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

from infoorgbench_harness.gateway import Gateway
from infoorgbench_harness.models.protocols import CHAT, RESPONSES, encode_response


class FakeBackend:
    protocol = RESPONSES

    def __init__(self):
        self.calls = []

    def request(self, protocol, body):
        self.calls.append((protocol, body))
        response = {"id": "r", "object": "response", "model": body["model"], "status": "completed",
                    "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "ok"}]}],
                    "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}
        return encode_response(response, self.protocol, stream=body.get("stream", False))


class GatewayTests(unittest.TestCase):
    def post(self, url, body):
        request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.headers.get_content_type(), response.read()

    def test_matching_protocol_is_passed_through(self):
        backend = FakeBackend()
        with Gateway(backend) as gateway:
            body = {"model": "m", "input": "hello", "stream": True, "store": False}
            content_type, raw = self.post(gateway.base_url + "/responses", body)
        self.assertEqual(backend.calls, [(RESPONSES, body)])
        self.assertEqual(content_type, "text/event-stream")
        self.assertIn(b"response.completed", raw)

    def test_chat_request_and_stream_are_translated(self):
        backend = FakeBackend()
        with Gateway(backend) as gateway:
            content_type, raw = self.post(gateway.base_url + "/chat/completions", {
                "model": "m", "messages": [{"role": "user", "content": "hello"}], "stream": True})
        self.assertEqual(backend.calls[0][0], CHAT)
        self.assertEqual(content_type, "text/event-stream")
        self.assertTrue(raw.rstrip().endswith(b"data: [DONE]"))

    def test_expected_model_is_enforced_before_forwarding(self):
        backend = FakeBackend()
        with Gateway(backend, expected_model="sealed") as gateway:
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self.post(gateway.base_url + "/responses", {"model": "other", "input": "x"})
        self.assertEqual(raised.exception.code, 400)
        raised.exception.close()
        self.assertEqual(backend.calls, [])


if __name__ == "__main__":
    unittest.main()
