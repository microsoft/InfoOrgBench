# Copyright (c) The InfoOrgBench authors.
# Licensed under the MIT License.
"""Offline InfoOrgBench replay, scoring and baseline experiments."""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import importlib.util
import json
import logging
import math
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / ".local"
TRACKS = ("native", "meeting")
COPILOT_SENTINEL = "INFOORGBENCH_COPILOT_OK"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encoded(value))


def write_new_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(text.encode("utf-8"))


def recipe(track):
    return load(ROOT / "data" / "recipes" / f"{track}.json")


def private_destination(path):
    target = path.resolve()
    if not target.is_relative_to(LOCAL.resolve()) or target == LOCAL.resolve():
        raise ValueError("Generated outputs must be below this repository's ignored .local directory")
    return target


def verify_repository():
    provenance = load(ROOT / "provenance.json")
    seen = set()
    for entry in provenance["files"]:
        relative = PurePosixPath(entry["path"])
        if relative.is_absolute() or ".." in relative.parts or entry["path"] in seen:
            raise ValueError("Unsafe or duplicate provenance path")
        seen.add(entry["path"])
        path = ROOT.joinpath(*relative.parts)
        if not path.is_file() or digest(path) != entry["sha256"]:
            raise ValueError("Changed or missing frozen import: " + entry["path"])
    return {"verified_imports": len(seen), "model_calls": 0}


def module(track, name):
    directory = ROOT / "vendor" / track
    path = directory / (name + ".py")
    sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location(f"infoorgbench_{track}_{name}", path)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load the frozen offline module")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def reference_for(track, task):
    reference = {"task_id": task["id"], "records": task["records"]}
    if track == "meeting":
        reference["provenance"] = task["source_records"]
    return reference


def prepare(track, archive_path):
    verify_repository()
    configuration = recipe(track)
    if digest(archive_path) != configuration["source"]["sha256"]:
        raise ValueError("The supplied archive is not the pinned source snapshot")
    destination = LOCAL / "data" / track
    if destination.exists():
        raise FileExistsError("Prepared data already exists; use verify-data, not an implicit overwrite")
    LOCAL.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="prepare-", dir=LOCAL) as temporary:
        staging = Path(temporary) / track
        with zipfile.ZipFile(archive_path) as archive:
            prefix = archive.namelist()[0].split("/")[0]
            ami = module("meeting", "ami_source") if track == "meeting" else None
            for task in configuration["tasks"]:
                records = []
                if track == "native":
                    for entry in task["source_records"]:
                        source = PurePosixPath(entry["source_path"])
                        if (source.is_absolute() or ".." in source.parts or len(source.parts) != 4
                                or source.parts[0] != "keps" or source.name not in {"README.md", "kep.yaml"}):
                            raise ValueError("Unsafe native source member")
                        text = archive.read(prefix + "/" + source.as_posix()).decode("utf-8")
                        records.append({"id": entry["id"],
                                        "format": "markdown" if source.name == "README.md" else "yaml", "text": text})
                    packet = {"task_id": task["id"], "task": task["task"],
                              "information_boundary": task["information_boundary"], "records": records}
                else:
                    meetings = {name: ami.read_meeting(archive, name) for name in task["selection"]["meetings"]}
                    for entry in task["source_records"]:
                        meeting = meetings[entry["meeting"]]
                        if entry["format"] == "transcript":
                            project = task["selection"]["projects"].index(meeting["project"]) + 1
                            number = ("b", "c").index(entry["meeting"][-1]) + 1
                            records.append({"id": entry["id"], "format": "transcript", "text": meeting["transcript"],
                                            "anchor": {"project": f"Project{project}", "meeting": f"Meeting{number}"}})
                        else:
                            matches = [note for note in meeting["notes"] if note["native_id"] == entry["native_id"]]
                            if len(matches) != 1:
                                raise ValueError("A selected note has no unique native source ID")
                            records.append({"id": entry["id"], "format": "note", "text": matches[0]["text"]})
                    packet = {"task_id": task["id"], "task": task["task"], "records": records,
                              "information_boundary": task["information_boundary"]}
                if hashlib.sha256(encoded(packet)).hexdigest() != task["packet_sha256"]:
                    raise ValueError("Replayed packet differs from the original benchmark: " + task["id"])
                expected = {entry["id"]: entry for entry in task["records"]}
                if len(expected) != len(records):
                    raise ValueError("Record count differs from the reference recipe")
                for record in records:
                    if hashlib.sha256(record["text"].encode("utf-8")).hexdigest() != expected[record["id"]]["content_sha256"]:
                        raise ValueError("Source content differs from the frozen record hash")
                write_new(staging / "public" / f"{task['id']}.json", packet)
                write_new(staging / "references" / f"{task['id']}.json", reference_for(track, task))
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging.rename(destination)
    return verify_data(track)


def verify_data(track):
    verify_repository()
    configuration = recipe(track)
    directory = LOCAL / "data" / track
    records = 0
    for task in configuration["tasks"]:
        public = directory / "public" / f"{task['id']}.json"
        reference = directory / "references" / f"{task['id']}.json"
        if not public.is_file() or digest(public) != task["packet_sha256"]:
            raise ValueError("Missing/changed task data; run prepare first: " + task["id"])
        if not reference.is_file() or reference.read_bytes() != encoded(reference_for(track, task)):
            raise ValueError("Changed portable reference: " + task["id"])
        records += len(load(public)["records"])
    return {"track": track, "tasks": len(configuration["tasks"]), "records": records,
            "original_public_packet_hashes_match": True, "reference_scope": configuration["reference_scope"]}


def fetch(track, accepted):
    if not accepted:
        raise ValueError("Read docs/DATA.md and pass --accept-source-license before downloading")
    verify_repository()
    source = recipe(track)["source"]
    url = source["url"]
    if not url.startswith("https://"):
        raise ValueError("Only the pinned public HTTPS source is allowed")
    target = LOCAL / "sources" / f"{track}.zip"
    if target.exists():
        if digest(target) != source["sha256"]:
            raise ValueError("Existing source archive has the wrong checksum")
        return {"archive": str(target), "sha256": source["sha256"], "downloaded": False}
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fetch-", dir=LOCAL) as temporary:
        downloaded = Path(temporary) / "source.zip"
        request = urllib.request.Request(url, headers={"User-Agent": "InfoOrgBench-source-replay/1.0"})
        with urllib.request.urlopen(request, timeout=90) as response, downloaded.open("xb") as stream:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 64 * 1024 * 1024:
                    raise ValueError("Source exceeds the 64 MiB acquisition bound")
                stream.write(chunk)
        if digest(downloaded) != source["sha256"]:
            raise ValueError("Downloaded source checksum does not match the pinned archive")
        downloaded.rename(target)
    return {"archive": str(target), "sha256": source["sha256"], "downloaded": True}


def scorer(track, economy_weight=None, unscored_policy=None):
    """Frozen track scorer plus the main structural score; frozen result fields stay unchanged."""
    from scoring.results import with_main
    from scoring.structure import DEFAULT_ECONOMY_WEIGHT
    implementation = module(track, "evaluate" if track == "native" else "score_challenge")
    frozen = ((implementation.evaluate_task, implementation.summary) if track == "native"
              else (implementation.score_packet, implementation.summarize))
    weight = DEFAULT_ECONOMY_WEIGHT if economy_weight is None else economy_weight
    return with_main(track, *frozen, economy_weight=weight, unscored_policy=unscored_policy)


def run_baselines(track, output, all_metrics=False):
    from scoring.results import main_results_markdown
    verify_data(track)
    output = private_destination(output)
    if output.exists():
        raise FileExistsError("Never overwrite baseline results")
    implementation = module(track, "baselines")
    score, summarize = scorer(track)
    configuration = recipe(track)
    report = {"track": track, "model_calls": 0, "methods": {}}
    for method in implementation.METHODS:
        groups = {"dev": [], "test": []}
        for task in configuration["tasks"]:
            packet = load(LOCAL / "data" / track / "public" / f"{task['id']}.json")
            reference = reference_for(track, task)
            prediction = implementation.predict(packet, method)
            result = score(packet, reference, prediction)
            groups[task["split"]].append(result)
            write_new(output / method / f"{task['id']}.json", prediction)
        report["methods"][method] = {split: {"summary": summarize(rows), "rows": rows}
                                     for split, rows in groups.items()}
    expected = load(ROOT / "artifacts" / "expected-baselines.json")[track]
    for method, splits in expected.items():
        for split, values in splits.items():
            actual = report["methods"][method][split]["summary"]
            for key, value in values.items():
                if not math.isclose(actual[key], value, rel_tol=0, abs_tol=1e-12):
                    raise ValueError(f"Baseline reproduction mismatch: {method}/{split}/{key}")
    report["original_primary_summaries_match"] = True
    write_new(output / "report.json", report)
    groups = {f"{method} / {split}": values["summary"]
              for method, splits in report["methods"].items() for split, values in splits.items()}
    write_new_text(output / "main-results.md", main_results_markdown(
        f"{track} baselines", groups, scope=configuration["reference_scope"], all_metrics=all_metrics,
        label="Method / split"))
    return {"track": track, "baseline_methods": len(report["methods"]), "output": str(output),
            "original_primary_summaries_match": True, "model_calls": 0}


def score_saved(track, output, all_metrics=False):
    from scoring.results import main_results_markdown
    verify_data(track)
    output = private_destination(output)
    if output.exists():
        raise FileExistsError("Never overwrite saved-prediction scores")
    score, summarize = scorer(track)
    tasks = {task["id"]: task for task in recipe(track)["tasks"]}
    prefix = f"artifacts/predictions/{track}/"
    paths = [entry["path"] for entry in load(ROOT / "provenance.json")["files"]
             if entry["path"].startswith(prefix)]
    groups = {}
    for relative in paths:
        path = ROOT / relative
        task = tasks[path.stem]
        label = path.parent.relative_to(ROOT / "artifacts" / "predictions" / track).as_posix()
        packet = load(LOCAL / "data" / track / "public" / path.name)
        groups.setdefault(label, []).append(score(packet, reference_for(track, task), load(path)))
    report = {"track": track, "model_calls": 0, "conditions": len(paths),
              "groups": {name: {"summary": summarize(rows), "rows": rows} for name, rows in groups.items()},
              "scope": recipe(track)["reference_scope"]}
    write_new(output / "report.json", report)
    write_new_text(output / "main-results.md", main_results_markdown(
        f"{track} saved model conditions", {name: group["summary"] for name, group in report["groups"].items()},
        scope=report["scope"], all_metrics=all_metrics, label="Condition"))
    return {"track": track, "conditions_rescored": len(paths), "output": str(output), "model_calls": 0}


def report_run(run, bundle, output, *, economy_weight=None, all_metrics=False, unscored_policy=None):
    """Score finished harness episodes from their captured filesystem state; no model calls."""
    from scoring.runs import run_markdown, run_report
    from scoring.structure import DEFAULT_ECONOMY_WEIGHT
    output = private_destination(output)
    if output.exists():
        raise FileExistsError("Never overwrite run reports")
    weight = DEFAULT_ECONOMY_WEIGHT if economy_weight is None else economy_weight
    score, _ = scorer("native", economy_weight=weight, unscored_policy=unscored_policy)
    report = run_report(run, bundle, score, economy_weight=weight, unscored_policy=unscored_policy)
    write_new(output / "report.json", report)
    write_new_text(output / "MAIN-RESULTS.md", run_markdown(report, all_metrics=all_metrics))
    overall = report["groups"]["all"]
    return {"run": report["run"], "episodes": overall["episodes"], "tasks": overall["tasks"],
            "structure_score": overall["structure_score"], "unscored_records": overall["unscored_records"],
            "excluded_records": (report["quality_filter"] or {}).get("excluded_records", 0),
            "output": str(output), "model_calls": 0}


def matrix():
    configuration = load(ROOT / "configs" / "main-study.json")
    counts = configuration["targets"]
    expected = counts["models"] * counts["harnesses"] * counts["test_collections"] * counts["repetitions"]
    if configuration["status"] != "authoring_plan_not_an_execution_approval" or expected != counts["main_conditions"]:
        raise ValueError("The non-executable study matrix is inconsistent")
    return {"execution_approved": False, "candidate_rows": counts["models"] * counts["harnesses"],
            "tasks_per_row": counts["test_collections"], "episodes_per_row": counts["test_collections"] * counts["repetitions"],
            "candidate_episodes": expected, "implemented_live_harness_adapters": ["runtime.dsh"],
            "note": "Later ReAct/DeepSeek/Copilot recommendations are candidates, not admitted runs."}


def publication_check():
    publication = load(ROOT / "publication.json")
    if not all(publication.get(key) for key in ("github_owner", "visibility", "original_code_license", "release_approved")):
        raise ValueError("Publication blocked: GitHub owner/visibility, original-code license and author approval are required")
    raise ValueError("No upload command is implemented; content/attribution review must precede a separately authorized push")


def smoke():
    """Provider-free smoke of workspace mutation, capture, preservation and scoring."""
    verify_repository()
    score, _ = scorer("native")
    bodies = {
        "R001": b"alpha planning record\n",
        "R002": b"alpha decision record\n",
        "R003": b"beta planning record\n",
        "R004": b"beta decision record\n",
    }
    expected_hashes = {identity: hashlib.sha256(body).hexdigest() for identity, body in bodies.items()}
    packet = {"task_id": "smoke", "records": [
        {"id": identity, "text": body.decode("utf-8")} for identity, body in bodies.items()]}
    reference = {"records": [
        {"id": identity, "path": ["Reference", "Group-A" if identity in {"R001", "R002"} else "Group-B"]}
        for identity in bodies]}
    with tempfile.TemporaryDirectory(prefix="infoorgbench-smoke-") as directory:
        workspace = Path(directory) / "workspace"
        inbox = workspace / "inbox"
        inbox.mkdir(parents=True)
        for identity, body in bodies.items():
            (inbox / f"{identity}.txt").write_bytes(body)
        moves = {"R001": "Alpha", "R002": "Alpha", "R003": "Beta", "R004": "Beta"}
        for identity, folder in moves.items():
            destination = workspace / "organized" / folder
            destination.mkdir(parents=True, exist_ok=True)
            (inbox / f"{identity}.txt").replace(destination / f"{identity}.txt")
        assignments, actual_hashes = [], {}
        for path in sorted(workspace.rglob("*.txt")):
            if path.is_symlink():
                raise ValueError("Smoke capture does not accept symlinked records")
            match = re.fullmatch(r"(R[0-9]{3})\.txt", path.name)
            if match is None:
                raise ValueError("Smoke capture found an unknown record")
            identity = match[1]
            actual_hashes[identity] = hashlib.sha256(path.read_bytes()).hexdigest()
            assignments.append({"id": identity, "path": list(path.relative_to(workspace).parts[:-1])})
        if actual_hashes != expected_hashes:
            raise ValueError("Smoke workspace did not preserve all record bytes")
        result = score(packet, reference, {"assignments": assignments})
        prior_disable = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            invalid = score(packet, reference, {"assignments": assignments[:-1]})
        finally:
            logging.disable(prior_disable)
    if (not result["valid_output"] or not result["exact_tree"] or result["clade_f1"] != 1
            or result["triplet_f1"] != 1 or result["main"]["structure_score"] != 1 or invalid["valid_output"]
            or invalid["main"]["structure_score"] != 0):
        raise ValueError("Workspace/evaluator smoke did not satisfy its positive and negative controls")
    return {"passed": True, "records": len(bodies), "files_preserved": len(actual_hashes),
            "valid_output": bool(result["valid_output"]), "exact_tree": bool(result["exact_tree"]),
            "clade_f1": result["clade_f1"], "triplet_f1": result["triplet_f1"],
            "structure_score": result["main"]["structure_score"],
            "invalid_output_rejected": not invalid["valid_output"], "model_calls": 0,
            "network_calls": 0, "live_harness_adapters_exercised": [],
            "scope": "Self-contained workspace/evaluator smoke; not source replay or harness/model admission."}


def exact_copilot_model(value):
    model = value.strip() if isinstance(value, str) else ""
    if (not model or value != model or model.casefold() == "auto" or ".." in model
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", model) is None):
        raise ValueError("Pass an exact model ID with --model; 'auto', paths and whitespace are not accepted")
    return model


def _run_copilot_sentinel(*, model, runtime_home, workspace):
    from copilot import CopilotClient
    from copilot.rpc import PermissionDecisionUserNotAvailable

    def deny_all(_request, _invocation):
        return PermissionDecisionUserNotAvailable()

    async def invoke():
        async with CopilotClient(
            mode="empty",
            base_directory=str(runtime_home),
            working_directory=str(workspace),
            use_logged_in_user=True,
        ) as client:
            status = await client.get_status()
            # v1.0.16 applies this allowlist to the full merged tool catalog.
            # Source: https://github.com/github/copilot-sdk/blob/v1.0.16/python/copilot/client.py
            async with await client.create_session(
                model=model,
                available_tools=[],
                on_permission_request=deny_all,
                working_directory=str(workspace),
                enable_skills=False,
                enable_config_discovery=False,
                skip_custom_instructions=True,
                enable_file_hooks=False,
                enable_host_git_operations=False,
                enable_file_change_tracking=False,
                enable_session_store=False,
                enable_session_telemetry=False,
                mcp_servers={},
                custom_agents=[],
                streaming=False,
            ) as session:
                response = await session.send_and_wait(
                    "Reply with exactly INFOORGBENCH_COPILOT_OK and no other text. "
                    "Do not request or invoke any tool.",
                    timeout=90,
                )
        if response is None:
            raise ValueError("GitHub Copilot returned no assistant response")
        data = response.data
        return {
            "content": data.content,
            "reported_model": data.model,
            "provider_id": data.provider_id,
            "output_tokens": data.output_tokens,
            "tool_requests": data.tool_requests or [],
            "sdk_version": metadata.version("github-copilot-sdk"),
            "runtime_version": status.version,
            "protocol_version": status.protocol_version,
        }

    return asyncio.run(invoke())


def copilot_smoke(*, accepted, model, output=None, runner=None):
    """Run one explicitly authorized, tool-free GitHub Copilot SDK preflight."""
    if not accepted:
        raise ValueError(
            "Live Copilot usage is disabled; pass --accept-copilot-usage to confirm allowance consumption"
        )
    requested_model = exact_copilot_model(model)
    hold = LOCAL / "provider-hold.json"
    if hold.exists():
        raise ValueError("Provider generation is held: " + load(hold)["reason"])
    verify_repository()
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%S%fZ")
    runtime_home = private_destination(LOCAL / "copilot" / "home")
    workspace = private_destination(LOCAL / "copilot" / run_id / "workspace")
    destination = private_destination(
        output if output is not None else LOCAL / "preflights" / f"copilot-{run_id}.json"
    )
    if destination.exists():
        raise FileExistsError("Copilot preflight receipt already exists; choose a new .local output path")
    runtime_home.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True)
    execute = runner or _run_copilot_sentinel
    try:
        live = execute(model=requested_model, runtime_home=runtime_home, workspace=workspace)
    except ModuleNotFoundError as error:
        if error.name == "copilot" or (error.name and error.name.startswith("copilot.")):
            raise ValueError(
                "GitHub Copilot SDK is not installed; run "
                "'python -m pip install -r requirements-copilot.txt' and "
                "'python -m copilot download-runtime'"
            ) from error
        raise
    if not isinstance(live, dict):
        raise ValueError("GitHub Copilot preflight returned an invalid result")
    content = live.get("content")
    reported_model = live.get("reported_model")
    tool_requests = live.get("tool_requests", [])
    if not isinstance(content, str) or content != COPILOT_SENTINEL:
        raise ValueError("GitHub Copilot response did not match the required sentinel")
    if reported_model != requested_model:
        raise ValueError(
            f"GitHub Copilot model identity mismatch: requested {requested_model!r}, "
            f"reported {reported_model!r}"
        )
    if not isinstance(tool_requests, list) or tool_requests:
        raise ValueError("GitHub Copilot emitted a tool request in a tool-free preflight")
    finished = datetime.now(timezone.utc)
    receipt = {
        "schema_version": 1,
        "passed": True,
        "provider": "github-copilot",
        "client": "github-copilot-sdk",
        "sdk_version": live.get("sdk_version"),
        "runtime_version": live.get("runtime_version"),
        "protocol_version": live.get("protocol_version"),
        "requested_model": requested_model,
        "reported_model": reported_model,
        "provider_id": live.get("provider_id"),
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "response_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "output_tokens": live.get("output_tokens"),
        "available_tools": [],
        "tool_requests": 0,
        "permission_policy": "explicit-deny",
        "model_calls": 1,
        "consumes_copilot_allowance": True,
        "matrix_route_admitted": False,
    }
    write_new(destination, receipt)
    receipt["receipt"] = str(destination)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("verify", "smoke", "matrix", "publish-check"):
        commands.add_parser(name)
    for name in ("prepare", "fetch", "verify-data", "baselines", "score-saved"):
        command = commands.add_parser(name)
        command.add_argument("--track", choices=TRACKS, required=True)
        if name == "prepare":
            command.add_argument("--archive", type=Path, required=True)
        elif name == "fetch":
            command.add_argument("--accept-source-license", action="store_true")
        elif name in {"baselines", "score-saved"}:
            command.add_argument("--output", type=Path, required=True)
            command.add_argument("--all-metrics", action="store_true",
                                 help="Add the optional-metric table to main-results.md")
    run_report_command = commands.add_parser(
        "report-run", help="Score finished episode captures against a materialized bundle (main results)")
    run_report_command.add_argument("--run", type=Path, required=True, help="Run directory containing episodes/*/")
    run_report_command.add_argument("--bundle", type=Path, required=True, help="Materialized bundle with manifest.json")
    run_report_command.add_argument("--output", type=Path, required=True)
    run_report_command.add_argument("--economy-weight", type=float, help="Folder-economy weight; default 0.2")
    run_report_command.add_argument("--unscored-records", choices=("record-quality-v1",),
                                    help="Keep flagged records in the tree but remove their triplet credit")
    run_report_command.add_argument("--all-metrics", action="store_true",
                                    help="Add the optional-metric table to MAIN-RESULTS.md")
    copilot = commands.add_parser("copilot-smoke")
    copilot.add_argument("--accept-copilot-usage", action="store_true")
    copilot.add_argument("--model", required=True)
    copilot.add_argument("--output", type=Path)
    generator = commands.add_parser("generate-tasks", help="Construct new source-disjoint candidates without model calls")
    generator.add_argument("--track", choices=TRACKS, required=True)
    generator.add_argument("--archive", type=Path, required=True)
    generator.add_argument("--output", type=Path, required=True)
    generator.add_argument("--seed", required=True)
    generator.add_argument("--dev-tasks", type=int, default=1)
    generator.add_argument("--test-tasks", type=int, default=0)
    generator.add_argument("--roots", type=int)
    generator.add_argument("--units-per-root", type=int, default=2, help="Native proposals per SIG; meeting uses fixed b/c meetings")
    generator.add_argument("--min-records", type=int, default=12)
    generator.add_argument("--max-records", type=int, default=200)
    generator.add_argument("--max-file-bytes", type=int, default=40000, help="Native whole-file rejection limit; never truncates")
    generator.add_argument("--exclude-file", type=Path, action="append", default=[])
    generator.add_argument("--exclude-generated", type=Path, action="append", default=[])
    generator.add_argument("--accept-source-license", action="store_true")
    generated_verify = commands.add_parser("verify-generated", help="Replay a generated dataset from its pinned source")
    generated_verify.add_argument("--dataset", type=Path, required=True)
    generated_verify.add_argument("--archive", type=Path, required=True)
    configure = commands.add_parser("live-configure")
    configure.add_argument("--llm-api-directory", type=Path, required=True)
    configure.add_argument("--node", type=Path)
    commands.add_parser("live-tasks", help="List fixed tasks, generated packets and metadata-only catalog entries")
    profiles = commands.add_parser("live-profiles", help="List the fixed hybrid model-harness setting pool")
    profiles.add_argument("--pool", type=Path)
    preview = commands.add_parser("live-preview", help="Write exact model inputs and separate evaluator expectations without provider calls")
    preview.add_argument("--track", choices=TRACKS, required=True)
    preview.add_argument("--task", required=True)
    preview.add_argument("--dataset", help="Exact generated catalog ID; omit for historical fixed recipes")
    preview.add_argument("--model")
    preview.add_argument("--setting", type=Path)
    preview.add_argument("--profile")
    preview.add_argument("--pool", type=Path)
    preview.add_argument("--output", type=Path, required=True)
    rehearsal = commands.add_parser("live-rehearse")
    rehearsal.add_argument("--track", choices=TRACKS, required=True)
    rehearsal.add_argument("--task", required=True)
    rehearsal.add_argument("--output", type=Path, required=True)
    rehearsal.add_argument("--dataset")
    rehearsal.add_argument("--model")
    rehearsal.add_argument("--setting", type=Path)
    rehearsal.add_argument("--profile")
    rehearsal.add_argument("--pool", type=Path)
    prepare_live = commands.add_parser("live-prepare")
    prepare_live.add_argument("--job", required=True)
    prepare_live.add_argument("--track", choices=TRACKS, required=True)
    prepare_live.add_argument("--task", required=True)
    prepare_live.add_argument("--model")
    prepare_live.add_argument("--dataset")
    prepare_live.add_argument("--setting", type=Path)
    prepare_live.add_argument("--profile")
    prepare_live.add_argument("--pool", type=Path)
    approve_live = commands.add_parser("live-approve")
    approve_live.add_argument("--job", required=True)
    approve_live.add_argument("--profile-sha256", required=True)
    approve_live.add_argument("--notes", required=True)
    for name in ("live-preflight", "live-run", "live-status"):
        command = commands.add_parser(name)
        command.add_argument("--job", required=True)
        if name != "live-status":
            command.add_argument("--accept-copilot-usage", action="store_true")
    args = parser.parse_args()
    try:
        if args.command.startswith("live-"):
            import live_experiments as live
            if args.command == "live-configure":
                result = live.configure(args.llm_api_directory, args.node)
            elif args.command == "live-tasks":
                from experiment_tasks import available_tasks
                result = available_tasks()
            elif args.command == "live-profiles":
                from runtime.contract import load_setting_pool
                pool = load_setting_pool(args.pool)
                result = {
                    "pool": {
                        "id": pool["id"], "status": pool["status"], "path": pool["pool_path"],
                        "sha256": pool["pool_sha256"], "common": pool["common"], "boundary": pool["boundary"],
                    },
                    "profiles": [{
                        "id": profile["id"], "model": profile["model"], "harness": profile["harness"],
                        "effort": profile["setting"]["effort"], "status": profile["status"],
                        "priority_rank": pool["models"][profile["model"]]["priority_rank"],
                        "adapter_implemented": pool["harnesses"][profile["harness"]]["implemented"],
                        "benchmark_admitted": profile["benchmark_admitted"],
                        "profile_sha256": profile["profile_sha256"],
                    } for profile in pool["profiles"]],
                    "model_calls": 0,
                }
            elif args.command in {"live-preview", "live-rehearse", "live-prepare"}:
                from runtime.contract import select_setting
                model = args.model or ("claude-haiku-5.5" if args.command == "live-rehearse"
                                       and args.setting is None and args.profile is None else None)
                setting, experiment_profile = select_setting(
                    profile_id=args.profile, model=model, setting_path=args.setting, pool_path=args.pool,
                    required_adapter="runtime.h0",
                )
                overrides = {key: value for key, value in setting.items() if key != "model"}
                if args.command == "live-preview":
                    result = live.preview_task(args.track, args.task, setting["model"], args.output,
                                               dataset=args.dataset, setting=overrides,
                                               experiment_profile=experiment_profile)
                elif args.command == "live-rehearse":
                    result = live.rehearse(args.track, args.task, args.output, dataset=args.dataset,
                                           model=setting["model"], setting=overrides,
                                           experiment_profile=experiment_profile)
                else:
                    profile = live.prepare_job(args.job, args.track, args.task, setting["model"],
                                               dataset=args.dataset, setting=overrides,
                                               experiment_profile=experiment_profile)
                    result = {"job": args.job, "selection": profile["selection"], "experiment_setting": profile["experiment_setting"],
                              "experiment_profile": profile.get("experiment_profile"),
                              "fixed_harness": profile["contract"]["fixed_harness"],
                              "input_guide": str(live.job_directory(args.job) / "inputs.md"),
                              "profile_sha256": digest(live.job_directory(args.job) / "profile.json"), "model_calls": 0}
            elif args.command == "live-approve":
                result = live.approve_job(args.job, args.profile_sha256, args.notes)
            elif args.command == "live-status":
                result = live.status(args.job)
            else:
                operation = live.preflight_job if args.command == "live-preflight" else live.run_job
                result = operation(args.job, accepted=args.accept_copilot_usage)
                if result.get("usage_complete") is False or result.get("status") == "stopped":
                    print(json.dumps(result, indent=2))
                    return 1
        elif args.command == "generate-tasks":
            from task_generation import generate
            result = generate(args.track, args.archive, args.output, seed=args.seed, dev_tasks=args.dev_tasks,
                test_tasks=args.test_tasks, roots=args.roots, units_per_root=args.units_per_root,
                min_records=args.min_records, max_records=args.max_records, max_file_bytes=args.max_file_bytes,
                exclusion_files=args.exclude_file, exclude_generated=args.exclude_generated,
                accepted=args.accept_source_license)
        elif args.command == "verify-generated":
            from task_generation import verify_generated
            result = verify_generated(args.dataset, args.archive)
        elif args.command == "verify":
            result = verify_repository()
        elif args.command == "smoke":
            result = smoke()
        elif args.command == "matrix":
            verify_repository()
            result = matrix()
        elif args.command == "publish-check":
            publication_check()
        elif args.command == "copilot-smoke":
            result = copilot_smoke(
                accepted=args.accept_copilot_usage,
                model=args.model,
                output=args.output,
            )
        elif args.command == "prepare":
            result = prepare(args.track, args.archive)
        elif args.command == "fetch":
            result = fetch(args.track, args.accept_source_license)
        elif args.command == "verify-data":
            result = verify_data(args.track)
        elif args.command == "baselines":
            result = run_baselines(args.track, args.output, all_metrics=args.all_metrics)
        elif args.command == "report-run":
            result = report_run(args.run, args.bundle, args.output, economy_weight=args.economy_weight,
                                all_metrics=args.all_metrics, unscored_policy=args.unscored_records)
        else:
            result = score_saved(args.track, args.output, all_metrics=args.all_metrics)
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as error:
        print(json.dumps({"status": "error", "operation": args.command, "message": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
