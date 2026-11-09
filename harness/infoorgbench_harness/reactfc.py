# Copyright (c) The InfoOrgBench authors.
# Licensed under the MIT License.
"""The ReAct-FC loop released with InfoOrgBench."""

from __future__ import annotations

from collections import Counter
import itertools
import json
from pathlib import Path
import time

from .models.protocols import RESPONSES, decode_response, merge_usage
from .prompt import render_packet
from .workspace import Workspace, tool_schemas

_BASE_RULES = Path(__file__).with_name("h0_system.txt").read_text(encoding="utf-8").rstrip("\r\n")
_INCREMENTAL = Path(__file__).with_name("h0_incremental.txt").read_text(encoding="utf-8").rstrip("\r\n")
_FAMILIES = {"Recap": ("summary", "v2"), "Thread": ("issue", "v2"),
             "Design": ("design-sections", "v2.2")}
_BATCH_ERROR = ("Tool batch exceeds the 200-call limit. None of this batch was executed. "
                "Resubmit at most 200 tool calls in one response.")


def initial_history(prompt):
    return [{"type": "message", "role": "user",
             "content": [{"type": "input_text", "text": prompt}]}]


def _declaration_matches(text, assignments):
    try:
        value = json.loads(text)
        rows = value["assignments"]
        expected = {row["id"]: row["path"] for row in assignments}
        return (isinstance(value, dict) and set(value) == {"assignments"} and isinstance(rows, list)
                and all(isinstance(row, dict) and set(row) == {"id", "path"} for row in rows)
                and Counter(row["id"] for row in rows) == Counter(expected)
                and all(row["path"] == expected[row["id"]] for row in rows))
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return False


def request_packet(model, history, settings):
    rules = _BASE_RULES
    if settings.get("incremental_protocol", True):
        rules += "\n\n" + _INCREMENTAL
    request = {
        "model": model,
        "instructions": rules,
        "input": history,
        "tools": tool_schemas(settings.get("search_max_results", 40)),
        "stream": True,
        "store": False,
        "parallel_tool_calls": True,
    }
    if settings.get("max_output_tokens") is not None:
        request["max_output_tokens"] = settings["max_output_tokens"]
    if settings.get("reasoning_effort") is not None:
        request["reasoning"] = {"effort": settings["reasoning_effort"]}
    return request


def run_episode(packet, *, family, model, backend, settings, workspace_root, clock=time.monotonic):
    """Run one episode while retaining every returned item in the next request history."""
    if family not in _FAMILIES:
        raise ValueError("Unknown task family")
    prompt_family, protocol_version = _FAMILIES[family]
    prompt, prompt_manifest = render_packet(packet, prompt_family, workspace=".", checker="check_inventory",
                                            protocol_version=protocol_version)
    records = packet.get("records")
    workspace = Workspace(workspace_root, records, search_max_results=settings.get("search_max_results", 40))
    history = initial_history(prompt)
    latest_check = None
    final_text = ""
    seen_calls = set()
    tool_calls = 0
    rejected_tools = 0
    requests = 0
    usage = {}
    status = "budget_stop"
    stop_reason = "decision_turn_limit"
    error_type = None
    started = clock()
    turns = settings.get("decision_turns")
    iterator = itertools.count(1) if turns is None else range(1, turns + 1)
    for _number in iterator:
        try:
            episode_seconds = settings.get("episode_seconds")
            if episode_seconds is not None and clock() - started >= episode_seconds:
                stop_reason = "episode_time_limit"
                break
            token_stop = settings.get("episode_observed_token_stop")
            if token_stop is not None and usage.get("total_tokens", 0) >= token_stop:
                stop_reason = "episode_token_limit"
                break
            raw, content_type = backend.request(RESPONSES, request_packet(model, history, settings))
            requests += 1
            response = decode_response(raw, backend.protocol, content_type)
            merge_usage(usage, response.get("usage", {}))
            output = response.get("output")
            if not isinstance(output, list):
                raise ValueError("Native response output must be a list")
            history.extend(output)
            actions = [item for item in output if item.get("type") == "function_call"]
            if not actions:
                final_text = "\n".join(part.get("text", "") for item in output if item.get("type") == "message"
                                       for part in item.get("content", []) if part.get("type") == "output_text")
                status, stop_reason = "completed", "model_final_response"
                break
            oversized = len(actions) > 200
            for item in actions:
                call_id = item.get("call_id")
                if call_id in seen_calls:
                    raise ValueError("Duplicate native tool call ID")
                seen_calls.add(call_id)
                tool_calls += 1
                try:
                    arguments = json.loads(item.get("arguments", ""))
                    if oversized:
                        raise ValueError(_BATCH_ERROR)
                    returned = workspace.operate(item.get("name"), arguments)
                    if item.get("name") == "check_inventory":
                        latest_check = returned
                except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
                    returned = {"error": str(error)}
                    rejected_tools += 1
                history.append({"type": "function_call_output", "call_id": call_id,
                                "output": json.dumps(returned, ensure_ascii=False, separators=(",", ":"))})
        except Exception as error:
            status, stop_reason = "stopped", "execution_failure"
            error_type = type(error).__name__
            break
    captured = Workspace.capture(workspace_root, records)
    assignments = captured["assignments"]
    checker = bool(latest_check and not latest_check["pending_ids"]
                   and latest_check["assignments"] == assignments)
    return {
        "status": status,
        "stop_reason": stop_reason,
        "error_type": error_type,
        "assignments": assignments,
        "inventory_preserved": captured["inventory_preserved"],
        "pending_ids": captured["pending_ids"],
        "checker_matches_final_state": checker,
        "declaration_matches_state": _declaration_matches(final_text, assignments),
        "contract_passed": bool(captured["inventory_preserved"] and not captured["pending_ids"] and checker),
        "requests": requests,
        "tool_calls": tool_calls,
        "rejected_tools": rejected_tools,
        "usage": usage,
        "prompt_manifest": prompt_manifest,
        "elapsed_seconds": clock() - started,
    }
