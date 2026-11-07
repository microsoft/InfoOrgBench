# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Native Deep Agents graph with only capability-scoped record tools."""

from importlib.metadata import version
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen


EXCLUDED_TOOLS = frozenset({
    "ls", "read_file", "write_file", "edit_file", "glob", "grep",
    "execute", "task", "write_todos", "delete",
})


def build_model(config):
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI

    selected = config["model"]
    common = {"model": selected["id"], "api_key": "local-capability-only",
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
    provider = "anthropic" if config["model"]["api"] == "anthropic-messages" else "openai"
    register_harness_profile(provider + ":" + config["model"]["id"], HarnessProfile(
        excluded_tools=EXCLUDED_TOOLS,
        excluded_middleware=frozenset({"SummarizationMiddleware"}),
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)))
    tools = []
    for row in config["tools"]:
        def handler(_name=row["name"], **arguments):
            request = Request(config["endpoint"] + "/tools/" + _name,
                              data=json.dumps(arguments).encode("utf-8"),
                              headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read())["text"]
        tools.append(StructuredTool(name=row["name"], description=row["description"],
                                    args_schema=row["parameters"], func=handler))
    agent = create_deep_agent(model=model, tools=tools, system_prompt=config["adapter"],
                              subagents=[], skills=None, memory=None, checkpointer=None)
    result = agent.invoke({"messages": [{"role": "user", "content": config["prompt"]}]},
                          config={"recursion_limit": sys.maxsize})
    last = result["messages"][-1]
    if last.type != "ai" or last.tool_calls:
        raise RuntimeError("Native Deep Agents graph did not finish with a terminal assistant message")
    return {"final": last.content, "completed": True}


def main():
    config = json.loads(Path(sys.argv[1]).read_bytes())
    result = run(config)
    Path(config["result"]).write_bytes(json.dumps(result, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
