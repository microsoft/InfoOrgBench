# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Command-line entry points for running and scoring released harnesses."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sys

from . import __version__
from .adapters import PINS, run_third_party
from .models.copilot import CopilotBackend
from .models.http import ProviderBackend
from .reactfc import run_episode
from .receipts import make_receipt
from .skills import SKILL_MODES, fetch_skills, load_skills, receipt_block

FAMILIES = ("Recap", "Thread", "Design")
HARNESSES = ("react-fc", "codex", "pi", "dsh", "deepagents")
BACKENDS = ("copilot", "openai", "openai-chat", "anthropic")
PAPER_PROFILE = {"max_output_tokens": 128000, "request_seconds": 2400,
                 "decision_turns": None, "episode_seconds": None,
                 "episode_observed_token_stop": None, "reasoning_effort": "medium",
                 "incremental_protocol": True, "search_max_results": 40}
# Provider output limits below the shared request. The paper's transport capped requests at these limits.
MODEL_OUTPUT_LIMITS = {"claude-haiku-4.5": 64000}


def repository_root():
    configured = os.environ.get("INFOORGBENCH_ROOT")
    root = Path(configured).resolve() if configured else Path(__file__).resolve().parents[2]
    if not (root / "benchmark" / "engine").is_dir():
        raise FileNotFoundError("Set INFOORGBENCH_ROOT to the InfoOrgBench repository")
    return root


def load_tasks(root, family, selected=None):
    directory = Path(root) / "benchmark" / "inputs" / "public" / family
    if family == "Thread" and not directory.is_dir():
        raise FileNotFoundError(
            "Thread packets are not distributed. Build them first with python benchmark/build_thread.py "
            "--responses <folder-with-Hadoop-Jira-responses>.")
    if not directory.is_dir():
        raise FileNotFoundError("Public packet directory is missing: " + family)
    names = selected or [path.stem for path in sorted(directory.glob("mini-*.json"))]
    rows = []
    for name in names:
        if not name or Path(name).name != name:
            raise ValueError("Task selectors must be task IDs such as mini-001")
        path = directory / (name + ".json")
        if not path.is_file():
            raise FileNotFoundError(f"Task packet is missing: {family}/{name}")
        rows.append((name, json.loads(path.read_text(encoding="utf-8"))))
    return rows


def _scorer(root):
    engine = str(Path(root) / "benchmark" / "engine")
    if engine not in sys.path:
        sys.path.insert(0, engine)
    module = importlib.import_module("infoorgbench")
    return module.scorer("native", economy_weight=0.2, unscored_policy=None)


def score_run(root, run_dir):
    score, summarize = _scorer(root)
    report = {"schema_version": 1, "tasks_scored": 0, "families": {}, "rows": []}
    for family in FAMILIES:
        directory = Path(run_dir) / family
        if not directory.is_dir():
            continue
        rows = []
        for prediction_path in sorted(directory.glob("mini-*.json")):
            packet_path = Path(root) / "benchmark" / "inputs" / "public" / family / prediction_path.name
            if family == "Thread" and not packet_path.is_file():
                raise FileNotFoundError(
                    "Thread packets must be built with benchmark/build_thread.py before scoring.")
            reference_path = Path(root) / "benchmark" / "inputs" / "reference" / family / prediction_path.name
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            reference = json.loads(reference_path.read_text(encoding="utf-8"))
            prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
            result = score(packet, reference, prediction)
            rows.append(result)
            report["rows"].append({"family": family, "task": prediction_path.stem,
                                   "valid_output": result["valid_output"],
                                   "structure_score": result["main"]["structure_score"],
                                   "level_balanced_triplet_f1": result["main"]["level_balanced_triplet_f1"],
                                   "folder_economy": result["main"]["folder_economy"]})
        if rows:
            report["families"][family] = summarize(rows)
            report["tasks_scored"] += len(rows)
    if not report["tasks_scored"]:
        raise ValueError("Run directory contains no prediction files")
    return report


def _backend(args, work):
    if args.backend == "copilot":
        return CopilotBackend(token_env=args.copilot_token_env, working_directory=work,
                              timeout_seconds=args.request_seconds)
    return ProviderBackend(args.backend, base_url=args.base_url, key_env=args.key_env,
                           key_header=args.key_header, timeout_seconds=args.request_seconds,
                           transport_retries=args.transport_retries)


def _settings(args):
    settings = dict(PAPER_PROFILE)
    settings["request_seconds"] = args.request_seconds
    if args.model == "claude-haiku-4.5":
        settings["reasoning_effort"] = None
    limit = MODEL_OUTPUT_LIMITS.get(args.model)
    if limit is not None:
        settings["max_output_tokens"] = min(settings["max_output_tokens"], limit)
    if getattr(args, "max_output_tokens", None):
        settings["max_output_tokens"] = args.max_output_tokens
    return settings


def run_command(args):
    root = repository_root()
    skills = None
    if args.skill:
        if args.harness not in {"deepagents", "codex"}:
            raise ValueError("--skill is supported only with --harness deepagents or codex")
        skills = load_skills(args.skill, args.skill_mode)
    skill_receipt = receipt_block(skills) if skills is not None else None
    destination = args.out.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError("Output directory must be new or empty")
    destination.mkdir(parents=True, exist_ok=True)
    runtime = destination / ".runtime"
    runtime.mkdir()
    settings = _settings(args)
    selected = args.tasks.split(",") if args.tasks else None
    tasks = load_tasks(root, args.family, selected)
    backend = _backend(args, runtime / "copilot")
    receipts = []
    failed = False
    try:
        for task_name, packet in tasks:
            task_runtime = runtime / task_name
            try:
                if args.harness == "react-fc":
                    task_runtime.mkdir()
                    result = run_episode(packet, family=args.family, model=args.model, backend=backend,
                                         settings=settings, workspace_root=task_runtime / "workspace")
                else:
                    result = run_third_party(packet, harness=args.harness, family=args.family,
                                             model=args.model, backend=backend, settings=settings,
                                             run_root=task_runtime,
                                             codex_extra_denied_roots=args.codex_deny_root,
                                             skills=skills)
                prediction = {"assignments": result["assignments"]}
                target = destination / args.family / (task_name + ".json")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(prediction, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                manifest = result["prompt_manifest"]
                hashes = {"packet_sha256": hashlib.sha256(json.dumps(packet, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")).encode()).hexdigest(), **manifest["hashes"]}
                receipts.append(make_receipt(harness=args.harness, model=args.model, backend=args.backend,
                    family=args.family, task_id=task_name, status=result["status"], settings=settings,
                    hashes=hashes, usage=result.get("usage", {}), versions={
                        "package": __version__, "harness": "1.0.0" if args.harness == "react-fc" else PINS[args.harness],
                        "task": packet.get("task_version", "release-packet"),
                        "protocol": manifest["prompt_version"], "family": manifest["family_version"]},
                    skills=skill_receipt, agent_stats=result.get("agent_stats")))
                if result["status"] == "stopped" or result["status"].startswith("failed:"):
                    failed = True
                    break
            except Exception as error:
                failed = True
                receipts.append(make_receipt(harness=args.harness, model=args.model, backend=args.backend,
                    family=args.family, task_id=task_name, status="failed:" + type(error).__name__, settings=settings,
                    hashes={"packet_sha256": hashlib.sha256(json.dumps(packet, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":")).encode()).hexdigest()}, usage={},
                    versions={"package": __version__}, skills=skill_receipt))
                break
            finally:
                shutil.rmtree(task_runtime, ignore_errors=True)
    finally:
        close = getattr(backend, "close", None)
        if close:
            close()
        shutil.rmtree(runtime, ignore_errors=True)
    receipt = {"schema_version": 1, "package_version": __version__, "backend": backend.public_metadata(),
               "settings": settings, "tasks": receipts}
    (destination / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if failed:
        raise RuntimeError("A task failed; see the content-free status in receipt.json")
    return receipt


def parser():
    root = argparse.ArgumentParser(description="Run and score the released InfoOrgBench agent harnesses")
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--harness", choices=HARNESSES, required=True)
    run.add_argument("--model", required=True)
    run.add_argument("--backend", choices=BACKENDS, required=True)
    run.add_argument("--family", choices=FAMILIES, required=True)
    run.add_argument("--tasks", help="Comma-separated task IDs, for example mini-001,mini-002")
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--base-url", default=os.environ.get("INFOORGBENCH_BASE_URL"))
    run.add_argument("--key-env", default=os.environ.get("INFOORGBENCH_API_KEY_ENV"))
    run.add_argument("--key-header", default=os.environ.get("INFOORGBENCH_API_KEY_HEADER"))
    run.add_argument("--copilot-token-env", default=os.environ.get("INFOORGBENCH_COPILOT_TOKEN_ENV", "COPILOT_GITHUB_TOKEN"))
    run.add_argument("--transport-retries", type=int, default=int(os.environ.get("INFOORGBENCH_TRANSPORT_RETRIES", "0")))
    run.add_argument("--request-seconds", type=int, default=2400)
    run.add_argument("--codex-deny-root", type=Path, action="append", default=[],
                     help="Additional existing host path to deny Codex; may be repeated")
    run.add_argument("--max-output-tokens", type=int,
                     help="Override the per-response output cap (default 128,000, capped at known model limits)")
    run.add_argument("--skill", type=Path, action="append", default=[],
                     help="Deep Agents or Codex: a skill directory containing SKILL.md; may be repeated")
    run.add_argument("--skill-mode", choices=SKILL_MODES, default="available",
                     help="available: listed for the agent to open when relevant; "
                          "pinned: SKILL.md is also added to the conversation before the first model call")
    score = commands.add_parser("score")
    score.add_argument("--run", type=Path, required=True)
    score.add_argument("--out", type=Path)
    fetch = commands.add_parser("fetch-skills", help="Download community skills at pinned commits")
    fetch.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parents[1]
                       / "configs" / "community-skills.json")
    fetch.add_argument("--out", type=Path, required=True)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "run":
        result = run_command(args)
    elif args.command == "fetch-skills":
        result = {"skills": fetch_skills(args.manifest, args.out)}
    else:
        result = score_run(repository_root(), args.run.resolve())
        if args.out:
            args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
