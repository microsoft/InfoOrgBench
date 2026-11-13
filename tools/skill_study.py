# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Run and analyse the community-skills study with the Deep Agents harness.

Each (condition, model, family, task) runs as its own harness process. Conditions
are interleaved in a seeded random order. An attempt is retried at most twice,
and only when its worker log shows an infrastructure failure. Outputs, logs and
the attempt ledger stay under the ignored ``.local`` directory.

    python tools/skill_study.py run --out .local/skill-study --workers 10
    python tools/skill_study.py status --out .local/skill-study
    python tools/skill_study.py analyze --out .local/skill-study
    python tools/skill_study.py cost --out .local/skill-study
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
MODELS = ("claude-haiku-5.5", "claude-sonnet-5.5")
ALL_MODELS = MODELS + ("claude-haiku-4.5",)
FAMILIES = ("Recap", "Thread", "Design")
TASKS = tuple("mini-%03d" % number for number in range(1, 51))
CONDITIONS = {
    "control": None,
    "pinned-composio-file-organizer": ("composio-file-organizer", "pinned"),
    "pinned-claude-office-file-organizer": ("claude-office-file-organizer", "pinned"),
    "pinned-composio-invoice-organizer": ("composio-invoice-organizer", "pinned"),
    "available-composio-file-organizer": ("composio-file-organizer", "available"),
    "pinned-irrelevant-mcp-builder": ("anthropic-mcp-builder", "pinned"),
    "control-r2": None,
    "pinned-office-invoice-organizer": ("claude-office-invoice-organizer", "pinned"),
    "pinned-office-email-classifier": ("claude-office-email-classifier", "pinned"),
    "codex-control": None,
    "codex-pinned-composio-file-organizer": ("composio-file-organizer", "pinned"),
    "codex-pinned-claude-office-file-organizer": ("claude-office-file-organizer", "pinned"),
}
CODEX = ("codex-control", "codex-pinned-composio-file-organizer", "codex-pinned-claude-office-file-organizer")
HARNESS = {condition: "codex" for condition in CODEX}
PRIMARY = ("control", "pinned-composio-file-organizer", "pinned-claude-office-file-organizer",
           "pinned-composio-invoice-organizer")
SECONDARY = ("available-composio-file-organizer", "pinned-irrelevant-mcp-builder")
ROUND2 = ("control-r2", "pinned-office-invoice-organizer", "pinned-office-email-classifier")
GROUPS = (PRIMARY, SECONDARY, ROUND2, CODEX)
IRRELEVANT = "pinned-irrelevant-mcp-builder"
SEED = 20261110
MAX_ATTEMPTS = 3
PUBLISHED = {"claude-haiku-5.5": "claude-haiku-5-5__deep-agents",
             "claude-sonnet-5.5": "claude-sonnet-5-5__deep-agents",
             "claude-haiku-4.5": "claude-haiku-4-5__deep-agents"}
# Pre-registered Holm families: (name, treated conditions, reference condition, models).
HOLM_FAMILIES = (
    ("round1", PRIMARY[1:], "control", MODELS),
    ("round2", ROUND2[1:], "control-r2", MODELS),
    ("stageB-haiku45", ("pinned-composio-file-organizer", "pinned-claude-office-file-organizer"), "control",
     ("claude-haiku-4.5",)),
    ("stageC-codex", CODEX[1:], "codex-control", ("claude-haiku-4.5",)),
)
PUBLISHED_CODEX = {"claude-haiku-4.5": "claude-haiku-4-5__codex"}
# USD per million tokens: input, 5-minute cache write, cache read, output. From
# https://platform.claude.com/docs/en/about-claude/pricing, retrieved 2026-11-12. Claude Haiku 5.5 uses
# its tier for prompts up to 100,000 tokens; its other tier has the same ratios, so relative costs do not
# depend on the tier.
PRICES = {"claude-haiku-5.5": (0.10, 0.125, 0.01, 0.50),
          "claude-sonnet-5.5": (2.00, 2.50, 0.10, 10.00),
          "claude-haiku-4.5": (1.00, 1.25, 0.10, 5.00)}
USAGE_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
INFRA = re.compile(
    r"HTTP Error (?:408|429|5\d\d)|URLError|RemoteDisconnected|ConnectionResetError|ConnectionRefusedError|"
    r"APIConnectionError|APITimeoutError|RateLimitError|InternalServerError|ServiceUnavailableError|"
    r"OverloadedError|APIStatusError: Error code: (?:408|429|5\d\d)|Error code: (?:408|429|5\d\d)|"
    r"gateway request failed|gateway concurrency limit|ReadTimeout|ConnectTimeout|timed out|"
    r"last status: (?:408|429|5\d\d)|thread/start failed|fs sandbox helper did not stop")
# Failures raised before the episode starts (for example the local version check under load).
INFRA_STATUSES = ("no-receipt", "failed:TimeoutExpired")
# Saves each native worker's stderr (and Codex's event stream) so failures can be classified.
BOOTSTRAP = """
import os, subprocess, sys
import infoorgbench_harness.adapters as adapters
original = adapters._run_process
def capture(command, **options):
    log = os.environ.get("SKILL_STUDY_STDERR")
    events = os.environ.get("SKILL_STUDY_EVENTS")
    if log and options.get("stderr") is subprocess.DEVNULL:
        with open(log, "ab") as handle:
            options["stderr"] = handle
            if events and options.get("stdout") is subprocess.DEVNULL:
                with open(events, "ab") as stream:
                    options["stdout"] = stream
                    return original(command, **options)
            return original(command, **options)
    return original(command, **options)
adapters._run_process = capture
from infoorgbench_harness.cli import main
main(sys.argv[1:])
"""
_LEDGER_LOCK = threading.Lock()


def job_list(conditions, models, families=FAMILIES, tasks=TASKS):
    jobs = []
    for offset, group in enumerate(GROUPS):
        rows = [(c, m, f, t) for c in conditions if c in group for m in models for f in families for t in tasks]
        random.Random(SEED + offset).shuffle(rows)
        jobs += rows
    return jobs


def job_dir(out, job):
    condition, model, family, task = job
    return Path(out) / "runs" / condition / model / family / task


def final_attempt(directory):
    """Return the last attempt record if the job needs no further attempt, else None."""
    records = sorted(directory.glob("attempt-*/attempt.json"), key=lambda p: int(p.parent.name.split("-")[1]))
    if not records:
        return None
    last = json.loads(records[-1].read_text(encoding="utf-8"))
    if not last["infrastructure_failure"] or len(records) >= MAX_ATTEMPTS:
        return last
    return None


def _skill_arguments(condition, skills_root):
    spec = CONDITIONS[condition]
    if spec is None:
        return []
    skill_id, mode = spec
    manifest = json.loads((ROOT / "harness" / "configs" / "community-skills.json").read_text(encoding="utf-8"))
    row = next(item for item in manifest["skills"] + manifest.get("controls", []) if item["id"] == skill_id)
    return ["--skill", str(Path(skills_root) / skill_id / row["directory"]), "--skill-mode", mode]


def is_infrastructure_failure(attempt, status):
    """Apply the retry rule: transport, rate-limit or pre-episode failures, never a completed Codex turn."""
    if status in INFRA_STATUSES:
        return True
    if status == "completed":
        return False
    logs = "".join(path.read_text(encoding="utf-8", errors="replace")
                   for path in (attempt / "worker-stderr.log", attempt / "harness.log") if path.is_file())
    events = attempt / "codex-events.jsonl"
    if events.is_file():
        stream = events.read_text(encoding="utf-8", errors="replace")
        if '"type":"turn.completed"' in stream:
            return False
        logs += "".join(line for line in stream.splitlines(True)
                        if '"type":"error"' in line or '"type":"turn.failed"' in line)
    return bool(INFRA.search(logs))


def command_reclassify(args):
    """Re-apply the retry rule to finished attempts of the given conditions, keeping the original label."""
    out = Path(args.out)
    changed = 0
    for condition in args.conditions:
        for record_path in sorted((out / "runs" / condition).glob("*/*/*/attempt-*/attempt.json")):
            record = json.loads(record_path.read_text(encoding="utf-8"))
            verdict = is_infrastructure_failure(record_path.parent, record["status"])
            if verdict == record["infrastructure_failure"]:
                continue
            record.setdefault("original_infrastructure_failure", record["infrastructure_failure"])
            record["infrastructure_failure"] = verdict
            record["reclassified_at"] = datetime.now(timezone.utc).isoformat()
            record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            with open(out / "ledger.jsonl", "a", encoding="utf-8") as ledger:
                ledger.write(json.dumps({**record, "event": "reclassified"}) + "\n")
            changed += 1
            print("reclassified", record_path.parent.relative_to(out), record["status"], "->", verdict)
    print("changed:", changed)


def run_job(job, out, skills_root, python):
    directory = job_dir(out, job)
    condition, model, family, task = job
    done = final_attempt(directory)
    if done is not None:
        return done
    existing = len(list(directory.glob("attempt-*/attempt.json")))
    record = None
    for number in range(existing + 1, MAX_ATTEMPTS + 1):
        attempt = directory / ("attempt-%d" % number)
        if attempt.exists():
            continue
        attempt.mkdir(parents=True)
        log = attempt / "worker-stderr.log"
        harness = HARNESS.get(condition, "deepagents")
        if harness == "codex":
            # The Codex prompt embeds the interpreter path, so it must not sit under a path the prompt lint rejects.
            python = os.environ.get("SKILL_STUDY_CODEX_PYTHON", python)
        command = [python, "-c", BOOTSTRAP, "run", "--harness", harness, "--model", model,
                   "--backend", "copilot", "--family", family, "--tasks", task, "--out", str(attempt / "out")]
        command += _skill_arguments(condition, skills_root)
        env = dict(os.environ, SKILL_STUDY_STDERR=str(log), PYTHONIOENCODING="utf-8",
                   PYTHONPATH=str(ROOT / "harness"))
        if harness == "codex":
            env["SKILL_STUDY_EVENTS"] = str(attempt / "codex-events.jsonl")
        started = time.time()
        with open(attempt / "harness.log", "wb") as handle:
            process = subprocess.run(command, cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT, check=False)
        receipt_path = attempt / "out" / "receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else None
        status = receipt["tasks"][0]["status"] if receipt and receipt.get("tasks") else "no-receipt"
        infrastructure = is_infrastructure_failure(attempt, status)
        record = {"condition": condition, "model": model, "family": family, "task": task, "attempt": number,
                  "status": status, "returncode": process.returncode, "infrastructure_failure": infrastructure,
                  "seconds": round(time.time() - started, 1),
                  "finished_at": datetime.now(timezone.utc).isoformat()}
        (attempt / "attempt.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        with _LEDGER_LOCK, open(Path(out) / "ledger.jsonl", "a", encoding="utf-8") as ledger:
            ledger.write(json.dumps(record) + "\n")
        if not infrastructure:
            break
        time.sleep(30 * number)
    return record


def command_run(args):
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    jobs = job_list(args.conditions, args.models)
    if args.limit:
        jobs = jobs[:args.limit]
    pending = [job for job in jobs if final_attempt(job_dir(out, job)) is None]
    print("jobs %d, pending %d" % (len(jobs), len(pending)), flush=True)
    finished = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_job, job, out, Path(args.skills).resolve(), args.python): job for job in pending}
        for future in concurrent.futures.as_completed(futures):
            finished += 1
            try:
                record = future.result()
                print("[%d/%d] %s %s %s/%s attempt %s %s %.0fs" % (
                    finished, len(pending), record["condition"], record["model"], record["family"],
                    record["task"], record["attempt"], record["status"], record["seconds"]), flush=True)
            except Exception as error:  # Keep the pool running; the job stays pending for a rerun.
                print("[%d/%d] %s error %s" % (finished, len(pending), futures[future], error), flush=True)


def command_status(args):
    out = Path(args.out)
    counts = {}
    for job in job_list(tuple(CONDITIONS), ALL_MODELS):
        record = final_attempt(job_dir(out, job))
        key = (job[0], job[1])
        row = counts.setdefault(key, {"final": 0, "completed": 0, "failed": 0, "infra_final": 0})
        if record is not None:
            row["final"] += 1
            row["completed" if record["status"] == "completed" else "failed"] += 1
            row["infra_final"] += int(record["infrastructure_failure"])
    for (condition, model), row in sorted(counts.items()):
        if row["final"]:
            print("%-40s %-18s final %3d/150 completed %3d failed %3d infra-final %d" % (
                condition, model, row["final"], row["completed"], row["failed"], row["infra_final"]))


def _scorer():
    engine = str(ROOT / "benchmark" / "engine")
    if engine not in sys.path:
        sys.path.insert(0, engine)
    import importlib
    return importlib.import_module("infoorgbench").scorer("native", economy_weight=0.2, unscored_policy=None)


def score_jobs(out):
    score, _ = _scorer()
    rows = []
    for job in job_list(tuple(CONDITIONS), ALL_MODELS):
        directory = job_dir(out, job)
        record = final_attempt(directory)
        if record is None:
            continue
        condition, model, family, task = job
        attempt = directory / ("attempt-%d" % record["attempt"])
        prediction_path = attempt / "out" / family / (task + ".json")
        packet = json.loads((ROOT / "benchmark" / "inputs" / "public" / family / (task + ".json")).read_text(encoding="utf-8"))
        reference = json.loads((ROOT / "benchmark" / "inputs" / "reference" / family / (task + ".json")).read_text(encoding="utf-8"))
        receipt_path = attempt / "out" / "receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))["tasks"][0] if receipt_path.is_file() else {}
        if prediction_path.is_file():
            prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
            result = score(packet, reference, prediction)
            main = result["main"]
            inbox = sum(1 for row in prediction["assignments"] if not row["path"] or row["path"][0] == "inbox")
            values = {"valid_output": bool(result["valid_output"]), "structure_score": 100 * main["structure_score"],
                      "triplet_f1": 100 * main["level_balanced_triplet_f1"],
                      "folder_economy": main["folder_economy"], "inbox_records": inbox}
        else:
            values = {"valid_output": False, "structure_score": 0.0, "triplet_f1": 0.0,
                      "folder_economy": None, "inbox_records": None}
        stats = receipt.get("agent_stats") or {}
        usage = receipt.get("provider_reported_usage") or {}
        rows.append({"condition": condition, "model": model, "family": family, "task": task,
                     "attempts": record["attempt"], "status": record["status"], **values,
                     "model_turns": stats.get("model_turns"),
                     "tool_calls": sum((stats.get("tool_calls") or {}).values()) if stats else None,
                     "record_moves": (stats.get("tool_calls") or {}).get("record_move") if stats else None,
                     "skill_md_reads": stats.get("skill_md_reads"),
                     "pinned_skill_messages": stats.get("pinned_skill_messages"),
                     "output_tokens": usage.get("output_tokens"),
                     "input_tokens": sum(usage.get(key) or 0 for key in
                                         ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
                     "seconds": record["seconds"]})
    return rows


def _mean(values):
    return sum(values) / len(values) if values else float("nan")


def paired_analysis(differences_by_family, *, resamples=10000, permutations=20000, seed=SEED):
    """Equal-family-weight mean difference, stratified bootstrap interval and sign-flip p-value."""
    families = [values for values in differences_by_family.values() if values]
    estimate = _mean([_mean(values) for values in families])
    rng = random.Random(seed)
    boots = []
    for _ in range(resamples):
        boots.append(_mean([_mean([values[rng.randrange(len(values))] for _ in values]) for values in families]))
    boots.sort()
    low, high = boots[int(0.025 * resamples)], boots[int(0.975 * resamples) - 1]
    extreme = 0
    for _ in range(permutations):
        flipped = _mean([_mean([value if rng.random() < 0.5 else -value for value in values]) for values in families])
        extreme += abs(flipped) >= abs(estimate) - 1e-12
    return {"difference": estimate, "ci95": [low, high], "p_value": (extreme + 1) / (permutations + 1),
            "tasks": sum(len(values) for values in families)}


def holm(p_values):
    order = sorted(range(len(p_values)), key=lambda index: p_values[index])
    adjusted = [0.0] * len(p_values)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (len(p_values) - rank) * p_values[index]))
        adjusted[index] = running
    return adjusted


def published_scores(systems=None):
    path = ROOT / "results" / "per-task.csv"
    rows = {}
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            for model, system in (systems or PUBLISHED).items():
                if row["system"] == system:
                    rows[(model, row["family"], row["task"])] = 100 * float(row["structure_score"])
    return rows


def command_analyze(args):
    out = Path(args.out)
    rows = score_jobs(out)
    with open(out / "per-task.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    by_key = {(row["condition"], row["model"], row["family"], row["task"]): row for row in rows}
    summary = {"conditions": {}, "comparisons": [], "published_check": {}}
    for condition in CONDITIONS:
        for model in ALL_MODELS:
            selected = [row for row in rows if row["condition"] == condition and row["model"] == model]
            if not selected:
                continue
            families = {family: _mean([row["structure_score"] for row in selected if row["family"] == family])
                        for family in FAMILIES}
            numeric = lambda name: [row[name] for row in selected if isinstance(row[name], (int, float))]
            summary["conditions"]["%s|%s" % (condition, model)] = {
                "condition": condition, "model": model, "tasks": len(selected),
                "structure_score": _mean([value for value in families.values() if not math.isnan(value)]),
                "families": families,
                "valid_outputs": sum(row["valid_output"] for row in selected),
                "failed_episodes": sum(row["status"] != "completed" for row in selected),
                "retried_tasks": sum(row["attempts"] > 1 for row in selected),
                "mean_inbox_records": _mean(numeric("inbox_records")),
                "mean_tool_calls": _mean(numeric("tool_calls")),
                "mean_model_turns": _mean(numeric("model_turns")),
                "mean_output_tokens": _mean(numeric("output_tokens")),
                "mean_seconds": _mean(numeric("seconds")),
                "tasks_reading_skill": sum(1 for row in selected if (row["skill_md_reads"] or 0) > 0),
                "tasks_with_pinned_skill": sum(1 for row in selected if (row["pinned_skill_messages"] or 0) > 0)}
    comparisons = []
    contrasts = [(name, "control") for name in CONDITIONS if name != "control" and name not in CODEX[1:]]
    contrasts += [(name, IRRELEVANT) for name in PRIMARY if name != "control"]
    contrasts += [(name, "control-r2") for name in ROUND2 if name != "control-r2"]
    contrasts += [(name, "codex-control") for name in CODEX if name != "codex-control"]
    for condition, reference in contrasts:
        for model in ALL_MODELS:
            differences = {family: [] for family in FAMILIES}
            for family in FAMILIES:
                for task in TASKS:
                    treated = by_key.get((condition, model, family, task))
                    control = by_key.get((reference, model, family, task))
                    if treated and control:
                        differences[family].append(treated["structure_score"] - control["structure_score"])
            if not any(differences.values()):
                continue
            result = paired_analysis(differences)
            result["families"] = {family: _mean(values) for family, values in differences.items() if values}
            family = next((name for name, treated, base, models in HOLM_FAMILIES
                           if condition in treated and reference == base and model in models), None)
            comparisons.append({"condition": condition, "reference": reference, "model": model,
                                "primary": family is not None, "holm_family": family, **result})
    for name, *_ in HOLM_FAMILIES:
        members = [row for row in comparisons if row["holm_family"] == name]
        for row, adjusted in zip(members, holm([row["p_value"] for row in members])):
            row["p_holm"] = adjusted
    summary["comparisons"] = comparisons
    published = published_scores()
    for model in ALL_MODELS:
        differences = {family: [] for family in FAMILIES}
        for family in FAMILIES:
            for task in TASKS:
                control = by_key.get(("control", model, family, task))
                if control and (model, family, task) in published:
                    differences[family].append(control["structure_score"] - published[(model, family, task)])
        if any(differences.values()):
            summary["published_check"][model] = paired_analysis(differences)
    for model, system in PUBLISHED_CODEX.items():
        published = published_scores({model: system})
        differences = {family: [] for family in FAMILIES}
        for family in FAMILIES:
            for task in TASKS:
                control = by_key.get(("codex-control", model, family, task))
                if control and (model, family, task) in published:
                    differences[family].append(control["structure_score"] - published[(model, family, task)])
        if any(differences.values()):
            summary["published_check"]["codex|" + model] = paired_analysis(differences)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for key, row in summary["conditions"].items():
        print("%-58s S=%5.1f  R=%5.1f T=%5.1f D=%5.1f  n=%d failed=%d" % (
            key, row["structure_score"], row["families"]["Recap"], row["families"]["Thread"],
            row["families"]["Design"], row["tasks"], row["failed_episodes"]))
    for row in comparisons:
        print("%-40s vs %-30s %-18s diff=%+5.2f CI[%+5.2f,%+5.2f] p=%.4f%s" % (
            row["condition"], row["reference"], row["model"], row["difference"], row["ci95"][0], row["ci95"][1],
            row["p_value"], " holm=%.4f" % row["p_holm"] if "p_holm" in row else ""))


def _adjusted_rand(first, second):
    """Adjusted Rand index between two labelings of the same records (1 = identical partition)."""
    pairs = lambda counts: sum(n * (n - 1) / 2 for n in counts)
    joint = {}
    for key in first:
        joint[(first[key], second[key])] = joint.get((first[key], second[key]), 0) + 1
    rows = {}
    columns = {}
    for (left, right), count in joint.items():
        rows[left] = rows.get(left, 0) + count
        columns[right] = columns.get(right, 0) + count
    index, row_pairs, column_pairs = pairs(joint.values()), pairs(rows.values()), pairs(columns.values())
    expected = row_pairs * column_pairs / pairs([len(first)])
    maximum = (row_pairs + column_pairs) / 2
    return 1.0 if maximum == expected else (index - expected) / (maximum - expected)


def _partitions(assignments):
    leaf = {row["id"]: tuple(row["path"]) for row in assignments}
    parent = {row["id"]: tuple(row["path"][:1]) for row in assignments}
    return leaf, parent


def _final_assignments(out, job):
    record = final_attempt(job_dir(out, job))
    if record is None:
        return None
    path = job_dir(out, job) / ("attempt-%d" % record["attempt"]) / "out" / job[2] / (job[3] + ".json")
    return json.loads(path.read_text(encoding="utf-8"))["assignments"]


def command_similarity(args):
    """Exploratory: how much each condition changes the grouping relative to reruns without a skill."""
    out = Path(args.out)
    published = {}
    for model, system in PUBLISHED.items():
        path = ROOT / "results" / "assignments" / (system + ".json")
        for key, row in json.loads(path.read_text(encoding="utf-8"))["tasks"].items():
            published[(model, *key.split("/"))] = row["assignments"]
    pairs = [("control", "published")] + [(name, "control") for name in CONDITIONS if name != "control"]
    summary = []
    for left, right in pairs:
        for model in MODELS:
            values = {"leaf": [], "parent": [], "identical": 0, "tasks": 0}
            for family in FAMILIES:
                for task in TASKS:
                    first = _final_assignments(out, (left, model, family, task))
                    second = (published.get((model, family, task)) if right == "published"
                              else _final_assignments(out, (right, model, family, task)))
                    if second is None:
                        continue
                    leaf_a, parent_a = _partitions(first)
                    leaf_b, parent_b = _partitions(second)
                    values["leaf"].append(_adjusted_rand(leaf_a, leaf_b))
                    values["parent"].append(_adjusted_rand(parent_a, parent_b))
                    values["identical"] += _adjusted_rand(leaf_a, leaf_b) == 1.0 and _adjusted_rand(parent_a, parent_b) == 1.0
                    values["tasks"] += 1
            row = {"condition": left, "reference": right, "model": model, "tasks": values["tasks"],
                   "mean_leaf_ari": _mean(values["leaf"]), "mean_parent_ari": _mean(values["parent"]),
                   "identical_partitions": values["identical"]}
            summary.append(row)
            print("%-38s vs %-10s %-18s n=%3d leaf ARI %.3f parent ARI %.3f identical %d" % (
                left, right, model, row["tasks"], row["mean_leaf_ari"], row["mean_parent_ari"], row["identical_partitions"]))
    (out / "grouping-similarity.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def episode_usage(out, job):
    """Provider-reported tokens, cost and time of a job's final attempt, or None if it has none."""
    record = final_attempt(job_dir(out, job))
    if record is None:
        return None
    path = job_dir(out, job) / ("attempt-%d" % record["attempt"]) / "out" / "receipt.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))["tasks"][0] if path.is_file() else {}
    usage = receipt.get("provider_reported_usage") or {}
    row = {key: usage.get(key) or 0 for key in USAGE_KEYS}
    row["tokens_read"] = sum(row[key] for key in USAGE_KEYS[:3])
    row["usd"] = sum(row[key] * price for key, price in zip(USAGE_KEYS, PRICES[job[1]])) / 1e6
    row["model_turns"] = (receipt.get("agent_stats") or {}).get("model_turns") or 0
    row["seconds"] = record["seconds"]
    return row


def relative_change(pairs, *, resamples=10000, seed=SEED):
    """Change of the summed metric against its reference, with a 95% bootstrap interval over tasks by family."""
    families = {}
    for family, treated, reference in pairs:
        families.setdefault(family, []).append((treated, reference))
    rng = random.Random(seed)
    boots = []
    for _ in range(resamples):
        sample = [rows[rng.randrange(len(rows))] for rows in families.values() for _ in rows]
        boots.append(sum(t for t, _ in sample) / sum(r for _, r in sample) - 1)
    boots.sort()
    change = sum(t for _, t, _ in pairs) / sum(r for _, _, r in pairs) - 1
    return {"change": change, "ci95": [boots[int(0.025 * resamples)], boots[int(0.975 * resamples) - 1]]}


def command_cost(args):
    """What each skill adds to tokens, API cost and time per task, against its same-day no-skill run."""
    out = Path(args.out)
    metrics = ("tokens_read", "output_tokens", "usd", "model_turns", "seconds")
    episodes, usage_rows = {}, []
    for condition in CONDITIONS:
        if condition in CODEX:
            continue
        for model in ALL_MODELS:
            for family in FAMILIES:
                for task in TASKS:
                    row = episode_usage(out, (condition, model, family, task))
                    if row is not None:
                        episodes[(condition, model, family, task)] = row
                        usage_rows.append({"condition": condition, "model": model, "family": family, "task": task,
                                           **{key: row[key] for key in USAGE_KEYS}, "seconds": row["seconds"]})
    summary = {"prices_usd_per_million_tokens": {model: dict(zip(USAGE_KEYS, price)) for model, price in PRICES.items()},
               "conditions": {}}
    for condition in CONDITIONS:
        for model in ALL_MODELS:
            rows = {(f, t): r for (c, m, f, t), r in episodes.items() if c == condition and m == model}
            if not rows:
                continue
            entry = {"condition": condition, "model": model, "tasks": len(rows),
                     "per_task": {key: _mean([r[key] for r in rows.values()]) for key in metrics}}
            if CONDITIONS[condition] is not None:
                reference = "control-r2" if condition in ROUND2 else "control"
                base = {(f, t): r for (c, m, f, t), r in episodes.items() if c == reference and m == model}
                keys = [key for key in rows if key in base]
                entry["reference"] = reference
                entry["extra_per_task"] = {key: _mean([rows[k][key] - base[k][key] for k in keys]) for key in metrics}
                entry["relative"] = {key: relative_change([(k[0], rows[k][key], base[k][key]) for k in keys])
                                     for key in metrics}
                print("%-38s %-18s tokens read %+6.1f%%  output %+5.1f%%  cost %+5.1f%% [%+.1f%%, %+.1f%%]  time %+5.1f%%" % (
                    condition, model, *(100 * entry["relative"][key]["change"] for key in ("tokens_read", "output_tokens", "usd")),
                    *(100 * value for value in entry["relative"]["usd"]["ci95"]), 100 * entry["relative"]["seconds"]["change"]))
            summary["conditions"]["%s|%s" % (condition, model)] = entry
    (out / "cost.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with open(out / "per-task-usage.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(usage_rows[0]))
        writer.writeheader()
        writer.writerows(usage_rows)


def command_watchdog(args):
    """Terminate Codex processes that stay alive after their turn has ended (see the protocol log)."""
    import signal
    import subprocess as process
    out = Path(args.out).resolve()
    log = out / "codex-watchdog.log"
    while True:
        listing = process.run(["powershell", "-NoProfile", "-Command",
                               "Get-CimInstance Win32_Process -Filter \"Name='codex.exe'\" | "
                               "Select-Object ProcessId, CommandLine | ConvertTo-Json -Compress"],
                              capture_output=True, text=True, check=False).stdout.strip()
        rows = json.loads(listing) if listing else []
        rows = [rows] if isinstance(rows, dict) else rows
        alive = False
        for condition in CODEX:
            for events in (out / "runs" / condition).glob("*/*/*/attempt-*/codex-events.jsonl"):
                attempt = events.parent
                if (attempt / "attempt.json").exists():
                    continue
                alive = True
                text = events.read_text(encoding="utf-8", errors="replace")
                ended = '"type":"turn.completed"' in text or '"type":"turn.failed"' in text
                if not ended or time.time() - events.stat().st_mtime < args.grace:
                    continue
                for row in rows:
                    if str(attempt) in (row.get("CommandLine") or ""):
                        try:
                            os.kill(int(row["ProcessId"]), signal.SIGTERM)
                        except OSError:
                            continue
                        with open(log, "a", encoding="utf-8") as handle:
                            handle.write(json.dumps({"attempt": str(attempt.relative_to(out)), "pid": row["ProcessId"],
                                                     "idle_seconds": round(time.time() - events.stat().st_mtime),
                                                     "at": datetime.now(timezone.utc).isoformat()}) + "\n")
        if not alive and args.exit_when_idle:
            return
        time.sleep(30)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--out", required=True)
    run.add_argument("--skills", default=str(ROOT / ".local" / "community-skills"))
    run.add_argument("--workers", type=int, default=8)
    run.add_argument("--conditions", nargs="+", default=list(PRIMARY), choices=list(CONDITIONS))
    run.add_argument("--models", nargs="+", default=list(MODELS), choices=list(ALL_MODELS))
    run.add_argument("--limit", type=int)
    run.add_argument("--python", default=sys.executable)
    for name in ("status", "analyze", "similarity", "cost"):
        sub = commands.add_parser(name)
        sub.add_argument("--out", required=True)
    reclassify = commands.add_parser("reclassify")
    reclassify.add_argument("--out", required=True)
    reclassify.add_argument("--conditions", nargs="+", required=True, choices=list(CONDITIONS))
    watchdog = commands.add_parser("watchdog")
    watchdog.add_argument("--out", required=True)
    watchdog.add_argument("--grace", type=int, default=120)
    watchdog.add_argument("--exit-when-idle", action="store_true")
    args = parser.parse_args(argv)
    {"run": command_run, "status": command_status, "analyze": command_analyze,
     "similarity": command_similarity, "cost": command_cost, "watchdog": command_watchdog,
     "reclassify": command_reclassify}[args.command](args)


if __name__ == "__main__":
    main()
