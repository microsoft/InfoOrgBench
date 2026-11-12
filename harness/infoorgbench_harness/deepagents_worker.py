# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Native Deep Agents graph with only capability-scoped record tools and optional Agent Skills."""

from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import threading
from urllib.request import Request, urlopen


EXCLUDED_TOOLS = frozenset({
    "ls", "read_file", "write_file", "edit_file", "glob", "grep",
    "execute", "task", "write_todos", "delete",
})
SKILLS_SOURCE = "/skills/"


def build_model(config):
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI

    selected = config["model"]
    common = {"model": selected["id"], "api_key": os.environ["INFOORGBENCH_GATEWAY_TOKEN"],
              "base_url": config["endpoint"], "streaming": True,
              "max_retries": 0, "timeout": config.get("requestSeconds", 120),
              "profile": {"max_input_tokens": selected["contextWindow"],
                          "max_output_tokens": selected["maxTokens"],
                          "tool_calling": True}}
    if selected["api"] == "anthropic-messages":
        effort = {"thinking": {"type": "adaptive"}, "effort": "medium"} if selected["reasoning"] else {}
        return ChatAnthropic(**common, max_tokens=selected["maxTokens"], **effort)
    if selected["api"] == "openai-responses":
        effort = {"reasoning": {"effort": "medium"}} if selected["reasoning"] else {}
        return ChatOpenAI(**common, use_responses_api=True, max_tokens=selected["maxTokens"],
                          store=False, **effort)
    if selected["api"] == "openai-completions":
        effort = {"reasoning_effort": "medium"} if selected["reasoning"] else {}
        return ChatOpenAI(**common, use_responses_api=False, stream_usage=True,
                          extra_body={"max_tokens": selected["maxTokens"]}, **effort)
    raise ValueError("Unsupported exact model API: " + selected["api"])


def run(config):
    from deepagents import (
        create_deep_agent, GeneralPurposeSubagentProfile, HarnessProfile, register_harness_profile,
    )
    from langchain_core.tools import StructuredTool

    for package, expected in config["packages"].items():
        if version(package) != expected:
            raise ValueError("Installed native package differs from frozen profile: " + package)
    model = build_model(config)
    skills = config.get("skills")
    excluded_tools = EXCLUDED_TOOLS
    if skills and skills["mode"] == "available":
        # Progressive disclosure needs read_file; the default state backend holds only the skill files.
        excluded_tools = EXCLUDED_TOOLS - {"read_file"}
    provider = "anthropic" if config["model"]["api"] == "anthropic-messages" else "openai"
    register_harness_profile(provider + ":" + config["model"]["id"], HarnessProfile(
        excluded_tools=excluded_tools,
        excluded_middleware=frozenset({"SummarizationMiddleware"}),
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)))
    tools = []
    # The gateway applies record operations one at a time and rejects connections beyond its
    # concurrency bound, so parallel tool calls from one model turn are sent sequentially.
    tool_lock = threading.Lock()
    for row in config["tools"]:
        def handler(_name=row["name"], **arguments):
            request = Request(config["endpoint"] + "/tools/" + _name,
                              data=json.dumps(arguments).encode("utf-8"),
                              headers={"Content-Type": "application/json",
                                       "Authorization": "Bearer " + os.environ["INFOORGBENCH_GATEWAY_TOKEN"]})
            with tool_lock, urlopen(request, timeout=30) as response:
                return json.loads(response.read())["text"]
        tools.append(StructuredTool(name=row["name"], description=row["description"],
                                    args_schema=row["parameters"], func=handler))
    state = {"messages": [{"role": "user", "content": config["prompt"]}]}
    if skills:
        from deepagents.backends.utils import create_file_data
        state["files"] = {path: create_file_data(text) for path, text in skills["files"].items()}
        if skills["mode"] == "pinned":
            state["pinned_skills"] = list(skills["names"])
    agent = create_deep_agent(model=model, tools=tools, system_prompt=config["adapter"],
                              subagents=[], skills=[SKILLS_SOURCE] if skills else None,
                              memory=None, checkpointer=None)
    result = agent.invoke(state, config={"recursion_limit": sys.maxsize})
    last = result["messages"][-1]
    if last.type != "ai" or last.tool_calls:
        raise RuntimeError("Native Deep Agents graph did not finish with a terminal assistant message")
    return {"final": last.content, "completed": True, "stats": episode_stats(result["messages"])}


def episode_stats(messages):
    """Content-free counts of the episode: tool calls by name and skill-file reads."""
    calls = {}
    skill_reads = {}
    pinned = 0
    for message in messages:
        if message.type == "human" and message.additional_kwargs.get("lc_source") == "pinned_skill":
            pinned += 1
        for call in getattr(message, "tool_calls", None) or []:
            calls[call["name"]] = calls.get(call["name"], 0) + 1
            path = str((call.get("args") or {}).get("file_path", ""))
            if call["name"] == "read_file" and path.startswith(SKILLS_SOURCE):
                skill_reads[call["id"]] = path
    read_ok = sum(1 for message in messages if message.type == "tool"
                  and message.tool_call_id in skill_reads and getattr(message, "status", "success") != "error")
    return {"model_turns": sum(1 for message in messages if message.type == "ai"),
            "tool_calls": calls, "skill_file_reads": len(skill_reads), "skill_file_reads_ok": read_ok,
            "skill_md_reads": sum(1 for path in skill_reads.values() if path.endswith("/SKILL.md")),
            "pinned_skill_messages": pinned}


def main():
    config = json.loads(Path(sys.argv[1]).read_bytes())
    result = run(config)
    Path(config["result"]).write_bytes(json.dumps(result, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
