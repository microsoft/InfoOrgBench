# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Adapters for the four third-party harnesses evaluated in InfoOrgBench."""

from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from .gateway import Gateway
from .prompt import render_packet
from .record_tools import ADAPTER_INSTRUCTIONS, operate_record_tool, record_tool_schemas
from .workspace import Workspace

PINS = {"codex": "0.162.1", "pi": "1.1.0", "dsh": "0.2.1-alpha.1", "deepagents": "0.7.23"}
_CODEX_INCREMENTAL = Path(__file__).with_name("codex_incremental.txt").read_text(encoding="utf-8").rstrip("\r\n")
DSH_COMMIT = "5badb15009ae1756c3afe0ae0cef1faafc290ccc"
_FAMILIES = {"Recap": ("summary", "v2"), "Thread": ("issue", "v2"),
             "Design": ("design-sections", "v2.2")}


def _child_environment(*, source=None, include_user=False, extra=None):
    """Return only declared process essentials plus explicit per-harness values."""
    source = os.environ if source is None else source
    exact = {"PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
             "TEMP", "TMP", "OS", "NUMBER_OF_PROCESSORS"}
    if include_user:
        exact.update({"HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"})
    env = {key: value for key, value in source.items()
           if key.upper() in exact or key.upper().startswith("PROCESSOR_")
           or key.upper() == "LANG" or key.upper().startswith("LC_")}
    for key, value in (extra or {}).items():
        if value is not None:
            env[str(key)] = str(value)
    return env


def _isolated_user_values(run_root):
    run_root = Path(run_root)
    values = {}
    for name in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP"):
        path = run_root / "child-environment" / name.lower()
        path.mkdir(parents=True, exist_ok=True)
        values[name] = str(path)
    return values


def _run_process(command, *, include_user=False, extra_env=None, **kwargs):
    kwargs["env"] = _child_environment(include_user=include_user, extra=extra_env)
    return subprocess.run([str(part) for part in command], **kwargs)


def build_codex_invocation(binary, workspace, run_root, base_url, model, effort, *, windows_sandbox=None,
                           read_denied_roots=()):
    provider = "infoorgbench_gateway"
    config = [f'model_provider="{provider}"', 'approval_policy="never"', 'web_search="disabled"',
              'features.multi_agent=false', 'features.memories=false', 'features.apps=false',
              'features.unbounded_connection_retries=false',
              f'model_providers.{provider}.name="Local gateway"',
              f'model_providers.{provider}.base_url={json.dumps(base_url)}',
              f'model_providers.{provider}.wire_api="responses"',
              f'model_providers.{provider}.env_key="INFOORGBENCH_GATEWAY_TOKEN"',
              f'model_providers.{provider}.requires_openai_auth=true',
              f'model_providers.{provider}.request_max_retries=0',
              f'model_providers.{provider}.stream_max_retries=0',
              f'model_providers.{provider}.stream_idle_timeout_ms=3600000']
    if effort is not None:
        config.append("model_reasoning_effort=" + json.dumps(effort))
    if windows_sandbox:
        config.append("windows.sandbox=" + json.dumps(windows_sandbox))
    # As in the paper's runs: the workspace is writable, evaluator material is unreadable and network is off.
    if read_denied_roots:
        entries = ['":root"="read"', '":project_roots"="write"']
        entries.extend(json.dumps(str(Path(root).resolve())) + '="deny"' for root in read_denied_roots)
        config.extend(['default_permissions="task"', "permissions.task.filesystem={" + ",".join(entries) + "}",
                       'permissions.task.network.enabled=false', 'include_permissions_instructions=false'])
    argv = [str(binary), "exec", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check",
            "--json", "--color", "never", "-C", str(workspace), "-m", model,
            "-o", str(Path(run_root) / "final.txt")]
    if not read_denied_roots:
        argv.extend(["-s", "workspace-write"])
    for value in config:
        argv.extend(["-c", value])
    argv.append("-")
    return argv


def codex_denied_roots(repository_root, workspace, *, extra_roots=(), home=None, appdata=None):
    """Existing evaluator and credential locations that must remain unreadable to Codex."""
    workspace = Path(workspace).resolve()
    home = Path(home or Path.home()).resolve()
    configured_appdata = appdata or os.environ.get("APPDATA")
    candidates = [(Path(repository_root) / "benchmark"), (Path(repository_root) / "results"),
                  home / ".ssh", home / ".aws", home / ".azure", home / ".config" / "gh",
                  home / ".copilot", home / ".docker", home / ".kube",
                  home / ".git-credentials", home / ".npmrc", home / ".netrc"]
    if configured_appdata:
        candidates.append(Path(configured_appdata) / "GitHub CLI")
    for root in extra_roots:
        path = Path(root).expanduser().resolve()
        if not path.exists():
            raise ValueError("Codex deny root does not exist: " + str(root))
        candidates.append(path)
    roots = []
    seen = set()
    for candidate in candidates:
        path = Path(candidate).expanduser().resolve()
        if not path.exists() or path == workspace or path in workspace.parents or workspace in path.parents:
            continue
        key = os.path.normcase(str(path))
        if key not in seen:
            roots.append(path)
            seen.add(key)
    return tuple(roots)


def build_dsh_patch(workspace, gateway_url, model, max_tokens, effort, request_seconds=2400):
    timeout_ms = (int(request_seconds) + 60) * 1000
    efforts = "reasoningEfforts: false" if effort is None else f"reasoningEfforts:\n                  {effort}: {effort}"
    return f'''- id: llm-deepseek
  disabled: true
- id: telemetry
  config:
    enabled: false
- id: memory
  config:
    enabled: false
- insert:
    - id: llm-pi-ai
      name: '@deepseek-ai/dsh-llm-pi-ai'
      config:
        providers:
          infoorgbench-gateway:
            displayName: Local model gateway
            apiKeyEnv: INFOORGBENCH_DSH_GATEWAY_KEY
            api: openai-responses
            baseURL: {json.dumps(gateway_url)}
            defaultContextWindow: 200000
            defaultMaxTokens: {int(max_tokens)}
            timeoutMs: {timeout_ms}
            streamIdleTimeoutMs: {timeout_ms}
            retryPolicy:
              mode: normal
              maxRetries: 0
            models:
              - id: {model}
                name: {model}
                contextWindow: 200000
                maxTokens: {int(max_tokens)}
                {efforts}
- id: sandbox-policy
  config:
    mode: workspace-write
    workspaceRoot: {json.dumps(str(Path(workspace).resolve()))}
- id: system-prompt
  config:
    includeHarnessIdentity: false
    includeRuntimeContext: false
    personaPrefix: ""
- id: agent-loop
  config:
    agents: []
'''


def _verify_codex(binary):
    value = _run_process([binary, "--version"], capture_output=True, text=True,
                         timeout=60, check=True).stdout.strip()
    if value != "codex-cli " + PINS["codex"]:
        raise ValueError("Installed Codex CLI differs from the paper pin")


def _run_codex(*, gateway, workspace, run_root, prompt, model, settings, extra_denied_roots=()):
    binary = os.environ.get("INFOORGBENCH_CODEX", "codex")
    _verify_codex(binary)
    from .cli import repository_root
    windows_sandbox = os.environ.get("INFOORGBENCH_CODEX_WINDOWS_SANDBOX", "mxc") if os.name == "nt" else None
    invocation = build_codex_invocation(binary, workspace.root, run_root, gateway.base_url,
                                         model, settings.get("reasoning_effort"), windows_sandbox=windows_sandbox,
                                         read_denied_roots=codex_denied_roots(
                                             repository_root(), workspace.root,
                                             extra_roots=extra_denied_roots))
    codex_home = Path(run_root) / "codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    extra_env = {**_isolated_user_values(run_root), "CODEX_HOME": str(codex_home),
                 "INFOORGBENCH_GATEWAY_TOKEN": gateway.token}
    process = _run_process(invocation, include_user=True, extra_env=extra_env, input=prompt,
                           text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False)
    if process.returncode:
        raise RuntimeError("Codex CLI episode failed")
    final = Path(run_root) / "final.txt"
    return final.read_text(encoding="utf-8") if final.is_file() else ""


def _model_api(model):
    return "anthropic-messages" if model.startswith("claude-") else "openai-responses"


def _worker_config(workspace, gateway, prompt, model, settings, run_root):
    endpoint = gateway.base_url
    # Anthropic clients append /v1/messages themselves; OpenAI clients append only the operation.
    if _model_api(model) == "anthropic-messages" and endpoint.endswith("/v1"):
        endpoint = endpoint[:-3]
    return {"workspace": str(workspace.root), "sandbox": str(run_root), "prompt": prompt,
            "adapter": ADAPTER_INSTRUCTIONS, "tools": record_tool_schemas(), "endpoint": endpoint,
            "model": {"id": model, "name": model, "api": _model_api(model),
                      "reasoning": settings.get("reasoning_effort") is not None,
                      "contextWindow": 200000, "maxTokens": settings.get("max_output_tokens", 128000)},
            "result": str(Path(run_root) / "worker-result.json"),
            "requestTimeoutMs": settings.get("request_seconds", 2400) * 1000,
            "requestSeconds": settings.get("request_seconds", 2400)}


def _run_pi(*, gateway, workspace, run_root, prompt, model, settings):
    pi_root = os.environ.get("INFOORGBENCH_PI_ROOT")
    if not pi_root:
        raise RuntimeError("Set INFOORGBENCH_PI_ROOT to the pinned Pi installation")
    config = _worker_config(workspace, gateway, prompt, model, settings, run_root)
    modules = Path(pi_root) / "node_modules" / "@earendil-works"
    config.update(piPackage=str(modules / "pi-coding-agent"), piAiPackage=str(modules / "pi-ai"))
    for name in ("pi-coding-agent", "pi-ai", "pi-agent-core", "pi-codemode", "pi-mcp", "pi-tui", "chord"):
        manifest = json.loads((modules / name / "package.json").read_text(encoding="utf-8"))
        if manifest.get("version") != PINS["pi"]:
            raise RuntimeError("Installed Pi packages differ from the paper pin: " + name)
    config_path = Path(run_root) / "worker.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    worker = Path(__file__).with_name("pi_worker.mjs")
    extra_env = {**_isolated_user_values(run_root), "INFOORGBENCH_GATEWAY_TOKEN": gateway.token,
                 "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false",
                 "NO_PROXY": "127.0.0.1,localhost,::1", "no_proxy": "127.0.0.1,localhost,::1"}
    process = _run_process([os.environ.get("INFOORGBENCH_NODE", "node"), worker, config_path],
                           include_user=True, extra_env=extra_env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if process.returncode:
        raise RuntimeError("Pi episode failed")
    return json.loads((Path(run_root) / "worker-result.json").read_text(encoding="utf-8"))["final"]


def _run_deepagents(*, gateway, workspace, run_root, prompt, model, settings):
    expected = {"deepagents": "0.7.23", "langchain": "1.4.4", "langchain-core": "1.6.9",
                "langchain-openai": "1.7.0", "langchain-anthropic": "1.7.5", "langgraph": "1.2.14"}
    for package, version in expected.items():
        if importlib.metadata.version(package) != version:
            raise RuntimeError("Installed Deep Agents packages differ from the paper pins")
    config = _worker_config(workspace, gateway, prompt, model, settings, run_root)
    config["packages"] = expected
    config_path = Path(run_root) / "worker.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    worker = Path(__file__).with_name("deepagents_worker.py")
    extra_env = {**_isolated_user_values(run_root), "INFOORGBENCH_GATEWAY_TOKEN": gateway.token,
                 "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false",
                 "NO_PROXY": "127.0.0.1,localhost,::1", "no_proxy": "127.0.0.1,localhost,::1"}
    process = _run_process([sys.executable, worker, config_path], include_user=True, extra_env=extra_env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if process.returncode:
        raise RuntimeError("Deep Agents episode failed")
    return json.loads((Path(run_root) / "worker-result.json").read_text(encoding="utf-8"))["final"]


def _run_dsh(*, gateway, workspace, run_root, prompt, model, settings):
    source_value = os.environ.get("INFOORGBENCH_DSH_SOURCE")
    if not source_value:
        raise RuntimeError("Set INFOORGBENCH_DSH_SOURCE to the pinned DSH source checkout")
    source = Path(source_value).resolve()
    commit = _run_process(["git", "-C", source, "rev-parse", "HEAD"], capture_output=True,
                          text=True, timeout=30, check=True).stdout.strip()
    if commit != DSH_COMMIT:
        raise RuntimeError("Installed DSH source differs from the paper pin")
    patch = Path(run_root) / "dsh.patch.yml"
    patch.write_text(build_dsh_patch(workspace.root, gateway.base_url, model,
                                     settings.get("max_output_tokens", 128000),
                                     settings.get("reasoning_effort"),
                                     settings.get("request_seconds", 2400)), encoding="utf-8")
    node = os.environ.get("INFOORGBENCH_NODE", "node")
    result_path = Path(run_root) / "dsh-worker-result.json"
    config = {"source": str(source), "model": model,
              "reasoning_effort": settings.get("reasoning_effort"),
              "max_tokens": settings.get("max_output_tokens", 128000),
              "workspace": str(workspace.root), "patch": str(patch), "prompt": prompt,
              "request_timeout_seconds": settings.get("request_seconds", 2400) + 60,
              "launch_args": [node, str(source / "apps" / "cli" / "lib" / "bin.js"),
                              "--profile", "sdk-minimal", "--patch", str(patch)],
              "result": str(result_path)}
    config_path = Path(run_root) / "dsh-worker.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    dsh_home = Path(run_root) / "dsh-home"
    dsh_home.mkdir(parents=True, exist_ok=True)
    extra_env = {**_isolated_user_values(run_root), "INFOORGBENCH_DSH_GATEWAY_KEY": gateway.token,
                 "DSH_HOME": str(dsh_home), "NO_PROXY": "127.0.0.1,localhost,::1",
                 "no_proxy": "127.0.0.1,localhost,::1"}
    worker = Path(__file__).with_name("dsh_worker.py")
    process = _run_process([sys.executable, worker, config_path], include_user=True, extra_env=extra_env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if process.returncode:
        raise RuntimeError("DSH episode failed")
    return json.loads(result_path.read_text(encoding="utf-8"))["final"]


def run_third_party(packet, *, harness, family, model, backend, settings, run_root,
                    codex_extra_denied_roots=()):
    """Run one native third-party harness, then independently capture the workspace."""
    if harness not in {"codex", "pi", "dsh", "deepagents"} or family not in _FAMILIES:
        raise ValueError("Unknown harness or family")
    run_root = Path(run_root)
    run_root.mkdir(parents=True, exist_ok=False)
    workspace = Workspace(run_root / "workspace", packet["records"])
    prompt_family, version = _FAMILIES[family]
    if harness in {"codex", "dsh"}:
        (run_root / "input-records.json").write_text(json.dumps(packet["records"], ensure_ascii=False), encoding="utf-8")
        shutil.copyfile(Path(__file__).with_name("checker.py"), run_root / "check_inventory.py")
        checker = f'"{sys.executable}" "../check_inventory.py" --workspace "." --records "../input-records.json"'
    else:
        checker = "record_inventory"
    prompt, manifest = render_packet(packet, prompt_family, workspace=".", checker=checker,
                                     protocol_version=version)
    if harness == "codex":
        prompt = _CODEX_INCREMENTAL + "\n\n" + prompt
    tool_handler = None if harness in {"codex", "dsh"} else lambda name, args: operate_record_tool(workspace, name, args)
    runners = {"codex": _run_codex, "pi": _run_pi, "dsh": _run_dsh, "deepagents": _run_deepagents}
    failure_type = None
    final_text = ""
    with Gateway(backend, tool_handler=tool_handler, expected_model=model) as gateway:
        try:
            runner_options = {"extra_denied_roots": codex_extra_denied_roots} if harness == "codex" else {}
            final_text = runners[harness](gateway=gateway, workspace=workspace, run_root=run_root,
                                          prompt=prompt, model=model, settings=settings, **runner_options)
        except Exception as error:
            failure_type = type(error).__name__
        usage = dict(gateway.usage)
        requests = gateway.requests
    capture = Workspace.capture(workspace.root, packet["records"])
    return {"status": "completed" if failure_type is None else "failed:" + failure_type,
            "error_type": failure_type, "assignments": capture["assignments"],
            "inventory_preserved": capture["inventory_preserved"], "pending_ids": capture["pending_ids"],
            "usage": usage, "requests": requests, "prompt_manifest": manifest, "final_text": final_text}
