# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Translate OpenAI Responses items, Chat Completions, and Anthropic Messages."""

from __future__ import annotations

import copy
import json
from typing import Any

RESPONSES = "responses"
CHAT = "chat"
ANTHROPIC = "anthropic"
PROTOCOLS = frozenset({RESPONSES, CHAT, ANTHROPIC})


def _text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "".join(str(part.get("text", "")) for part in content
                   if isinstance(part, dict) and part.get("type") in {"text", "input_text", "output_text"})


def _message_item(role: str, text: str) -> dict:
    kind = "output_text" if role == "assistant" else "input_text"
    return {"type": "message", "role": role, "content": [{"type": kind, "text": text}]}


def to_responses_request(body: dict, protocol: str) -> dict:
    """Map a client request to the Responses request/item representation."""
    if protocol == RESPONSES:
        return copy.deepcopy(body)
    if protocol not in PROTOCOLS or not isinstance(body, dict):
        raise ValueError("Unsupported model protocol")
    result = {"model": body.get("model"), "input": [], "stream": body.get("stream", False),
              "store": False}
    instructions = []
    if protocol == CHAT:
        for message in body.get("messages", []):
            role = message.get("role")
            if role in {"system", "developer"}:
                instructions.append(_text_content(message.get("content")))
                continue
            if role == "tool":
                result["input"].append({"type": "function_call_output", "call_id": message.get("tool_call_id"),
                                        "output": _text_content(message.get("content"))})
                continue
            text = _text_content(message.get("content"))
            if text:
                result["input"].append(_message_item(role, text))
            if role == "assistant":
                for call in message.get("tool_calls", []):
                    function = call.get("function", {})
                    result["input"].append({"type": "function_call", "call_id": call.get("id"),
                                            "name": function.get("name"), "arguments": function.get("arguments", "{}")})
        tools = []
        for tool in body.get("tools", []):
            function = tool.get("function", {})
            tools.append({"type": "function", "name": function.get("name"),
                          "description": function.get("description", ""),
                          "parameters": function.get("parameters", {})})
        result["tools"] = tools
        maximum = body.get("max_completion_tokens", body.get("max_tokens"))
        effort = body.get("reasoning_effort")
    else:
        system = body.get("system", [])
        if isinstance(system, str):
            instructions.append(system)
        else:
            instructions.extend(_text_content([part]) for part in system if isinstance(part, dict))
        for message in body.get("messages", []):
            role = message.get("role")
            content = message.get("content", [])
            if isinstance(content, str):
                result["input"].append(_message_item(role, content))
                continue
            texts = []

            def flush_texts():
                if texts:
                    result["input"].append(_message_item(role, "".join(texts)))
                    texts.clear()

            for part in content:
                if part.get("type") == "text":
                    texts.append(part.get("text", ""))
                elif part.get("type") == "tool_use":
                    flush_texts()
                    result["input"].append({"type": "function_call", "call_id": part.get("id"),
                                            "name": part.get("name"),
                                            "arguments": json.dumps(part.get("input", {}), separators=(",", ":"))})
                elif part.get("type") == "tool_result":
                    flush_texts()
                    result["input"].append({"type": "function_call_output", "call_id": part.get("tool_use_id"),
                                            "output": _text_content(part.get("content"))})
            flush_texts()
        result["tools"] = [{"type": "function", "name": tool.get("name"),
                            "description": tool.get("description", ""),
                            "parameters": tool.get("input_schema", {})} for tool in body.get("tools", [])]
        maximum = body.get("max_tokens")
        effort = body.get("output_config", {}).get("effort")
    if instructions:
        result["instructions"] = "\n\n".join(text for text in instructions if text)
    if maximum is not None:
        result["max_output_tokens"] = maximum
    if effort:
        result["reasoning"] = {"effort": effort}
    return result



def _merge_chat_messages(messages):
    merged = []
    for message in messages:
        if merged and message.get("role") == "assistant" == merged[-1].get("role"):
            if message.get("content"):
                prior = merged[-1].get("content") or ""
                merged[-1]["content"] = prior + message["content"]
            merged[-1].setdefault("tool_calls", []).extend(message.get("tool_calls", []))
        else:
            merged.append(copy.deepcopy(message))
    return merged


def _merge_anthropic_messages(messages):
    merged = []
    for message in messages:
        if merged and message.get("role") == merged[-1].get("role"):
            merged[-1]["content"].extend(copy.deepcopy(message.get("content", [])))
        else:
            merged.append(copy.deepcopy(message))
    return merged

def from_responses_request(body: dict, protocol: str) -> dict:
    """Map a Responses request to a provider request, dropping opaque reasoning items."""
    if protocol == RESPONSES:
        return copy.deepcopy(body)
    if protocol not in PROTOCOLS or not isinstance(body, dict):
        raise ValueError("Unsupported model protocol")
    items = body.get("input", [])
    if isinstance(items, str):
        items = [_message_item("user", items)]
    items = [{"type": "message", **item} if isinstance(item, dict) and "type" not in item and "role" in item else item
             for item in items]
    if protocol == CHAT:
        messages = []
        if body.get("instructions"):
            messages.append({"role": "system", "content": body["instructions"]})
        for item in items:
            kind = item.get("type")
            if kind == "message":
                messages.append({"role": item.get("role"), "content": _text_content(item.get("content"))})
            elif kind == "function_call":
                messages.append({"role": "assistant", "content": None, "tool_calls": [{"id": item.get("call_id"),
                    "type": "function", "function": {"name": item.get("name"), "arguments": item.get("arguments", "{}")}}]})
            elif kind == "function_call_output":
                messages.append({"role": "tool", "tool_call_id": item.get("call_id"), "content": str(item.get("output", ""))})
        result = {"model": body.get("model"), "messages": _merge_chat_messages(messages),
                  "tools": [{"type": "function", "function": {"name": tool.get("name"),
                      "description": tool.get("description", ""), "parameters": tool.get("parameters", {})}}
                            for tool in body.get("tools", [])],
                  "stream": body.get("stream", False)}
        if body.get("max_output_tokens") is not None:
            result["max_completion_tokens"] = body["max_output_tokens"]
        if body.get("reasoning", {}).get("effort"):
            result["reasoning_effort"] = body["reasoning"]["effort"]
        return result
    messages = []
    for item in items:
        kind = item.get("type")
        if kind == "message":
            messages.append({"role": item.get("role"), "content": [{"type": "text", "text": _text_content(item.get("content"))}]})
        elif kind == "function_call":
            try:
                arguments = json.loads(item.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {}
            messages.append({"role": "assistant", "content": [{"type": "tool_use", "id": item.get("call_id"),
                                                                  "name": item.get("name"), "input": arguments}]})
        elif kind == "function_call_output":
            messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": item.get("call_id"),
                                                              "content": str(item.get("output", ""))}]})
    result = {"model": body.get("model"), "messages": _merge_anthropic_messages(messages),
              "system": ([{"type": "text", "text": body["instructions"]}] if body.get("instructions") else []),
              "tools": [{"name": tool.get("name"), "description": tool.get("description", ""),
                          "input_schema": tool.get("parameters", {})} for tool in body.get("tools", [])],
              "max_tokens": body.get("max_output_tokens", 8192), "stream": body.get("stream", False)}
    effort = body.get("reasoning", {}).get("effort")
    if effort:
        result["thinking"] = {"type": "adaptive"}
        result["output_config"] = {"effort": effort}
    return result


def _numeric_usage(value):
    if isinstance(value, dict):
        return {key: filtered for key, item in value.items()
                if (filtered := _numeric_usage(item)) is not None}
    if type(value) in (int, float) and value >= 0:
        return value
    return None


def merge_usage(target, update):
    """Add provider-reported numeric usage, retaining nested token details."""
    for key, value in (update or {}).items():
        if isinstance(value, dict):
            child = target.setdefault(key, {})
            if isinstance(child, dict):
                merge_usage(child, value)
        elif type(value) in (int, float) and value >= 0:
            target[key] = target.get(key, 0) + value
    return target


def _canonical_usage(usage: dict | None) -> dict:
    usage = usage or {}
    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0))
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0))
    total = usage.get("total_tokens", input_tokens + output_tokens)
    result = {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total}
    for key, value in usage.items():
        filtered = _numeric_usage(value)
        if key not in result and filtered is not None:
            result[key] = filtered
    return result


def _sse_values(raw: bytes) -> list[dict]:
    values = []
    pending = []
    for line in raw.decode("utf-8").splitlines():
        if line.startswith("data:"):
            value = line[5:].lstrip()
            if value != "[DONE]":
                pending.append(value)
        elif not line and pending:
            values.append(json.loads("\n".join(pending)))
            pending = []
    if pending:
        values.append(json.loads("\n".join(pending)))
    return values


def decode_response(raw: bytes, protocol: str, content_type: str = "application/json") -> dict:
    """Decode one complete JSON or collected SSE response into Responses items."""
    streamed = "text/event-stream" in content_type
    events = _sse_values(raw) if streamed else []
    if any(event.get("type") == "error" or isinstance(event.get("error"), dict) for event in events):
        raise ValueError("Provider stream contained a provider error")
    if protocol == RESPONSES:
        if streamed:
            terminal = [(event.get("type"), event.get("response")) for event in events
                        if event.get("type") in {"response.completed", "response.incomplete"}]
            if len(terminal) != 1 or not isinstance(terminal[0][1], dict):
                raise ValueError("Responses stream requires exactly one terminal response")
            event_type, response = terminal[0]
            expected_status = "incomplete" if event_type == "response.incomplete" else "completed"
            if response.get("status") != expected_status:
                raise ValueError("Responses terminal event and status differ")
            return response
        return json.loads(raw)
    if protocol == CHAT:
        if streamed:
            if not any(line[5:].strip() == b"[DONE]" for line in raw.splitlines() if line.startswith(b"data:")):
                raise ValueError("Chat stream ended without a terminal marker")
            model = next((event.get("model") for event in events if event.get("model")), None)
            content = ""
            calls = {}
            usage = {}
            finish_reason = None
            for event in events:
                usage.update(event.get("usage") or {})
                for choice in event.get("choices", []):
                    finish_reason = choice.get("finish_reason") or finish_reason
                    delta = choice.get("delta", {})
                    content += delta.get("content") or ""
                    for call in delta.get("tool_calls", []):
                        index = call.get("index", 0)
                        current = calls.setdefault(index, {"id": call.get("id"), "name": "", "arguments": ""})
                        current["id"] = call.get("id") or current["id"]
                        current["name"] += call.get("function", {}).get("name", "")
                        current["arguments"] += call.get("function", {}).get("arguments", "")
        else:
            data = json.loads(raw)
            model, usage = data.get("model"), data.get("usage", {})
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            finish_reason = choice.get("finish_reason")
            content = message.get("content") or ""
            calls = {index: {"id": call.get("id"), "name": call.get("function", {}).get("name", ""),
                             "arguments": call.get("function", {}).get("arguments", "")}
                     for index, call in enumerate(message.get("tool_calls", []))}
        output = [{"type": "function_call", "call_id": call["id"], "name": call["name"],
                   "arguments": call["arguments"] or "{}"} for _, call in sorted(calls.items())]
        if content:
            output.append({"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": content}]})
        incomplete = finish_reason == "length"
        return {"id": "translated", "object": "response", "model": model,
                "status": "incomplete" if incomplete else "completed",
                **({"incomplete_details": {"reason": "max_output_tokens"}} if incomplete else {}),
                "output": output, "usage": _canonical_usage(usage)}
    if protocol != ANTHROPIC:
        raise ValueError("Unsupported model protocol")
    if streamed and not any(event.get("type") == "message_stop" for event in events):
        raise ValueError("Anthropic stream ended without message_stop")
    if not streamed:
        data = json.loads(raw)
        model, content, usage = data.get("model"), data.get("content", []), data.get("usage", {})
        stop_reason = data.get("stop_reason")
    else:
        model, usage, blocks, stop_reason = None, {}, {}, None
        for event in events:
            kind = event.get("type")
            if kind == "message_start":
                model = event.get("message", {}).get("model")
                usage.update(event.get("message", {}).get("usage") or {})
            elif kind == "content_block_start":
                blocks[event["index"]] = copy.deepcopy(event.get("content_block", {}))
            elif kind == "content_block_delta":
                block = blocks.setdefault(event["index"], {})
                delta = event.get("delta", {})
                block["text"] = block.get("text", "") + delta.get("text", "")
                block["partial_json"] = block.get("partial_json", "") + delta.get("partial_json", "")
            elif kind == "message_delta":
                usage.update(event.get("usage") or {})
                stop_reason = event.get("delta", {}).get("stop_reason") or stop_reason
        content = []
        for _, block in sorted(blocks.items()):
            if block.get("type") == "tool_use":
                if block.get("partial_json"):
                    block["input"] = json.loads(block.pop("partial_json"))
            else:
                block.pop("partial_json", None)
            content.append(block)
    output = []
    for part in content:
        if part.get("type") == "text":
            output.append({"type": "message", "role": "assistant",
                           "content": [{"type": "output_text", "text": part.get("text", "")}]})
        elif part.get("type") == "tool_use":
            output.append({"type": "function_call", "call_id": part.get("id"), "name": part.get("name"),
                           "arguments": json.dumps(part.get("input", {}), separators=(",", ":"))})
    incomplete = stop_reason == "max_tokens"
    return {"id": "translated", "object": "response", "model": model,
            "status": "incomplete" if incomplete else "completed",
            **({"incomplete_details": {"reason": "max_output_tokens"}} if incomplete else {}),
            "output": output, "usage": _canonical_usage(usage)}


def _sse(event: dict, name: str | None = None) -> bytes:
    prefix = f"event: {name}\n" if name else ""
    return (prefix + "data: " + json.dumps(event, separators=(",", ":")) + "\n\n").encode()


def encode_response(response: dict, protocol: str, stream: bool = False) -> tuple[bytes, str]:
    """Encode canonical Responses output for a client protocol."""
    if protocol == RESPONSES:
        if stream:
            event_type = "response.incomplete" if response.get("status") == "incomplete" else "response.completed"
            return _sse({"type": event_type, "response": response}), "text/event-stream"
        return json.dumps(response, separators=(",", ":")).encode(), "application/json"
    text = "".join(part.get("text", "") for item in response.get("output", []) if item.get("type") == "message"
                   for part in item.get("content", []) if part.get("type") == "output_text")
    calls = [item for item in response.get("output", []) if item.get("type") == "function_call"]
    usage = _canonical_usage(response.get("usage"))
    if protocol == CHAT:
        tool_calls = [{"index": index, "id": item.get("call_id"), "type": "function", "function": {
            "name": item.get("name"), "arguments": item.get("arguments", "{}")}}
                      for index, item in enumerate(calls)]
        message = {"role": "assistant", "content": text or None, "tool_calls": tool_calls}
        finish_reason = ("length" if response.get("status") == "incomplete"
                         else "tool_calls" if calls else "stop")
        chat_usage = {"prompt_tokens": usage["input_tokens"], "completion_tokens": usage["output_tokens"],
                      "total_tokens": usage["total_tokens"]}
        if stream:
            chunk = {"id": response.get("id", "translated"), "object": "chat.completion.chunk",
                     "model": response.get("model"), "choices": [{"index": 0, "delta": message,
                     "finish_reason": finish_reason}], "usage": chat_usage}
            return _sse(chunk) + b"data: [DONE]\n\n", "text/event-stream"
        value = {"id": response.get("id", "translated"), "object": "chat.completion", "model": response.get("model"),
                 "choices": [{"index": 0, "message": message,
                              "finish_reason": finish_reason}], "usage": chat_usage}
        return json.dumps(value, separators=(",", ":")).encode(), "application/json"
    if protocol != ANTHROPIC:
        raise ValueError("Unsupported model protocol")
    content = []
    for item in response.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    content.append({"type": "text", "text": part.get("text", "")})
        elif item.get("type") == "function_call":
            try:
                arguments = json.loads(item.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {}
            content.append({"type": "tool_use", "id": item.get("call_id"), "name": item.get("name"), "input": arguments})
    anthropic_usage = {"input_tokens": usage["input_tokens"], "output_tokens": usage["output_tokens"]}
    stop_reason = ("max_tokens" if response.get("status") == "incomplete"
                   else "tool_use" if calls else "end_turn")
    message = {"id": response.get("id", "translated"), "type": "message", "role": "assistant",
               "model": response.get("model"), "content": content,
               "stop_reason": stop_reason, "usage": anthropic_usage}
    if not stream:
        return json.dumps(message, separators=(",", ":")).encode(), "application/json"
    raw = _sse({"type": "message_start", "message": {**message, "content": [], "stop_reason": None}}, "message_start")
    for index, part in enumerate(content):
        empty = ({**part, "input": {}} if part["type"] == "tool_use" else {"type": "text", "text": ""})
        raw += _sse({"type": "content_block_start", "index": index, "content_block": empty}, "content_block_start")
        delta = ({"type": "input_json_delta", "partial_json": json.dumps(part["input"], separators=(",", ":"))}
                 if part["type"] == "tool_use" else {"type": "text_delta", "text": part["text"]})
        raw += _sse({"type": "content_block_delta", "index": index, "delta": delta}, "content_block_delta")
        raw += _sse({"type": "content_block_stop", "index": index}, "content_block_stop")
    raw += _sse({"type": "message_delta", "delta": {"stop_reason": message["stop_reason"]},
                 "usage": anthropic_usage}, "message_delta")
    raw += _sse({"type": "message_stop"}, "message_stop")
    return raw, "text/event-stream"
