# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

from infoorgbench_harness.models.protocols import (
    ANTHROPIC, CHAT, RESPONSES, decode_response, encode_response,
    from_responses_request, to_responses_request,
)


class ProtocolTranslationTests(unittest.TestCase):
    def setUp(self):
        self.request = {
            "model": "model-a",
            "instructions": "system rules",
            "input": [
                {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "organize"}]},
                {"type": "reasoning", "summary": [{"type": "summary_text", "text": "opaque"}]},
                {"type": "function_call", "call_id": "c1", "name": "list_files", "arguments": "{\"start_at\":0,\"max_results\":10}"},
                {"type": "function_call_output", "call_id": "c1", "output": "{\"files\":[]}"},
            ],
            "tools": [{"type": "function", "name": "list_files", "description": "list", "parameters": {"type": "object", "properties": {}, "required": []}}],
            "max_output_tokens": 128000,
            "stream": True,
            "store": False,
            "reasoning": {"effort": "medium"},
        }

    def test_responses_chat_mapping_preserves_tools_and_results(self):
        chat = from_responses_request(self.request, CHAT)
        self.assertEqual(chat["messages"][0], {"role": "system", "content": "system rules"})
        tool = next(m for m in chat["messages"] if m.get("tool_calls"))
        self.assertEqual(tool["tool_calls"][0]["function"]["name"], "list_files")
        self.assertEqual(next(m for m in chat["messages"] if m["role"] == "tool")["tool_call_id"], "c1")
        self.assertNotIn("opaque", json.dumps(chat))
        restored = to_responses_request(chat, CHAT)
        self.assertTrue(any(x.get("type") == "function_call_output" for x in restored["input"]))

    def test_responses_anthropic_mapping_preserves_tools_and_system(self):
        anthropic = from_responses_request(self.request, ANTHROPIC)
        self.assertEqual(anthropic["system"], [{"type": "text", "text": "system rules"}])
        assistant = next(m for m in anthropic["messages"] if m["role"] == "assistant")
        self.assertEqual(assistant["content"][0]["type"], "tool_use")
        result = next(m for m in anthropic["messages"] if m["role"] == "user" and any(p.get("type") == "tool_result" for p in m["content"]))
        self.assertEqual(result["content"][0]["tool_use_id"], "c1")
        restored = to_responses_request(anthropic, ANTHROPIC)
        self.assertTrue(any(x.get("type") == "function_call" for x in restored["input"]))

    def test_stream_encoders_decode_to_same_responses_items(self):
        response = {
            "id": "r1", "object": "response", "model": "model-a", "status": "completed",
            "output": [
                {"type": "function_call", "call_id": "c2", "name": "check_inventory", "arguments": "{}"},
                {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "done"}]},
            ],
            "usage": {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10},
        }
        for protocol in (RESPONSES, CHAT, ANTHROPIC):
            with self.subTest(protocol=protocol):
                raw, content_type = encode_response(response, protocol, stream=True)
                decoded = decode_response(raw, protocol, content_type)
                self.assertEqual(decoded["model"], "model-a")
                self.assertEqual(decoded["usage"]["total_tokens"], 10)
                self.assertEqual(decoded["output"][0]["name"], "check_inventory")
                self.assertEqual(decoded["output"][1]["content"][0]["text"], "done")

    def test_anthropic_mixed_content_preserves_block_order(self):
        request = {"model": "m", "messages": [{"role": "assistant", "content": [
            {"type": "text", "text": "before"},
            {"type": "tool_use", "id": "c", "name": "list_files", "input": {}},
            {"type": "text", "text": "after"},
        ]}], "max_tokens": 10}
        mapped = to_responses_request(request, ANTHROPIC)
        self.assertEqual([item["type"] for item in mapped["input"]],
                         ["message", "function_call", "message"])
        self.assertEqual(mapped["input"][0]["content"][0]["text"], "before")
        self.assertEqual(mapped["input"][2]["content"][0]["text"], "after")

    def test_incomplete_or_error_streams_are_rejected(self):
        chat = b'data: {"model":"m","choices":[{"delta":{"content":"partial"}}]}\n\n'
        with self.assertRaisesRegex(ValueError, "terminal"):
            decode_response(chat, CHAT, "text/event-stream")
        anthropic = b'event: message_start\ndata: {"type":"message_start","message":{"model":"m","usage":{}}}\n\n'
        with self.assertRaisesRegex(ValueError, "message_stop"):
            decode_response(anthropic, ANTHROPIC, "text/event-stream")
        error = b'data: {"type":"error","error":{"message":"sensitive"}}\n\n'
        with self.assertRaisesRegex(ValueError, "provider error"):
            decode_response(error, RESPONSES, "text/event-stream")


if __name__ == "__main__":
    unittest.main()
