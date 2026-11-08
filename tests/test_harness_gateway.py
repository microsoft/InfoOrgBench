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
    def post(self, url, body, token=None, content_type="application/json", api_key=False):
        headers = {"Content-Type": content_type}
        if token:
            headers["x-api-key" if api_key else "Authorization"] = token if api_key else "Bearer " + token
        request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers=headers)
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.headers.get_content_type(), response.read()

    def test_matching_protocol_is_passed_through(self):
        backend = FakeBackend()
        with Gateway(backend) as gateway:
            body = {"model": "m", "input": "hello", "stream": True, "store": False}
            content_type, raw = self.post(gateway.base_url + "/responses", body, gateway.token)
        self.assertEqual(backend.calls, [(RESPONSES, body)])
        self.assertEqual(content_type, "text/event-stream")
        self.assertIn(b"response.completed", raw)

    def test_chat_request_and_stream_are_translated(self):
        backend = FakeBackend()
        with Gateway(backend) as gateway:
            content_type, raw = self.post(gateway.base_url + "/chat/completions", {
                "model": "m", "messages": [{"role": "user", "content": "hello"}], "stream": True}, gateway.token)
        self.assertEqual(backend.calls[0][0], CHAT)
        self.assertEqual(content_type, "text/event-stream")
        self.assertTrue(raw.rstrip().endswith(b"data: [DONE]"))

    def test_expected_model_is_enforced_before_forwarding(self):
        backend = FakeBackend()
        with Gateway(backend, expected_model="sealed") as gateway:
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self.post(gateway.base_url + "/responses", {"model": "other", "input": "x"}, gateway.token)
        self.assertEqual(raised.exception.code, 400)
        raised.exception.close()
        self.assertEqual(backend.calls, [])

    def test_gateway_rejects_missing_authentication_before_forwarding(self):
        backend = FakeBackend()
        with Gateway(backend) as gateway:
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self.post(gateway.base_url + "/responses", {"model": "m", "input": "secret body"})
        self.assertEqual(raised.exception.code, 401)
        raised.exception.close()
        self.assertEqual(backend.calls, [])

    def test_gateway_accepts_x_api_key_and_requires_json(self):
        backend = FakeBackend()
        with Gateway(backend) as gateway:
            _, raw = self.post(gateway.base_url + "/responses", {"model": "m", "input": "x"},
                               gateway.token, api_key=True)
            self.assertIn(b'"status":"completed"', raw)
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self.post(gateway.base_url + "/responses", {"model": "m"}, gateway.token,
                          content_type="text/plain")
        self.assertEqual(raised.exception.code, 415)
        raised.exception.close()

    def test_gateway_bounds_concurrent_requests(self):
        import threading
        import time

        entered = threading.Event()
        release = threading.Event()

        def handler(_name, _arguments):
            entered.set()
            release.wait(5)
            return {"ok": True}

        with Gateway(FakeBackend(), tool_handler=handler, max_concurrent_requests=1) as gateway:
            first = threading.Thread(target=self.post,
                                     args=(gateway.base_url + "/tools/record_move", {}, gateway.token))
            first.start()
            self.assertTrue(entered.wait(2))
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self.post(gateway.base_url + "/tools/record_move", {}, gateway.token)
            self.assertEqual(raised.exception.code, 503)
            raised.exception.close()
            release.set()
            first.join(5)

    def test_invalid_tool_call_returns_tool_error(self):
        def handler(_name, _arguments):
            raise ValueError("Read pages must contain 1 to 8000 characters")

        with Gateway(FakeBackend(), tool_handler=handler) as gateway:
            _, raw = self.post(gateway.base_url + "/tools/record_read", {"file_id": "F001"}, gateway.token)
        self.assertEqual(json.loads(json.loads(raw)["text"]), {"error": "Read pages must contain 1 to 8000 characters"})

    def test_parallel_tool_calls_run_one_at_a_time(self):
        import threading
        import time

        state = {"active": 0, "peak": 0}
        guard = threading.Lock()

        def handler(_name, _arguments):
            with guard:
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            time.sleep(0.05)
            with guard:
                state["active"] -= 1
            return {"ok": True}

        with Gateway(FakeBackend(), tool_handler=handler) as gateway:
            threads = [threading.Thread(target=self.post, args=(gateway.base_url + "/tools/record_move", {}, gateway.token))
                       for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        self.assertEqual(state["peak"], 1)


if __name__ == "__main__":
    unittest.main()
