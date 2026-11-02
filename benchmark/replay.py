# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Provider-disabled, standard-library-only replay of the local saved-output package.

Thread packets are built locally from Apache Hadoop Jira with build_thread.py.
Until they are built, Thread outputs are skipped and reported; pass
--require-thread to fail instead.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import sys


def relative_file(root, parts):
    if (not isinstance(parts, list) or not parts
            or any(not isinstance(p, str) or not p or p in {".", ".."}
                   or any(c in p for c in "\\/:") for p in parts)):
        raise ValueError("Manifest paths must be safe relative component arrays")
    path = root.joinpath(*parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Linked path escapes package")
    return path


def compare(expected, actual, path="metric"):
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(expected) != set(actual):
            raise AssertionError("Mapping differs: " + path)
        for key in expected:
            compare(expected[key], actual[key], path + "." + key)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            raise AssertionError("List denominator differs: " + path)
        for i, (left, right) in enumerate(zip(expected, actual)):
            compare(left, right, path + "." + str(i))
    elif isinstance(expected, float):
        if type(actual) not in (float, int) or not math.isclose(expected, actual, abs_tol=1e-12, rel_tol=0):
            raise AssertionError("Float differs: " + path)
    elif expected != actual:
        raise AssertionError("Value differs: " + path)


def deny_external(event, args):
    if event.startswith("socket.") or event in {"subprocess.Popen", "os.system", "os.posix_spawn"}:
        raise PermissionError("Network and child processes are disabled during saved-output replay")


def replay(package, require_thread=False):
    sys.addaudithook(deny_external)
    sys.dont_write_bytecode = True
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    unbuilt = set()
    for entry in manifest["files"]:
        path = relative_file(package, entry["parts"])
        if entry.get("build") and not path.exists():
            if require_thread:
                raise AssertionError("Locally built file missing; run " + entry["build"] + ": " + "/".join(entry["parts"]))
            unbuilt.add(tuple(entry["parts"]))
            continue
        if sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise AssertionError("Package byte binding differs: " + "/".join(entry["parts"]))
    sys.path.insert(0, str(package / "engine"))
    from infoorgbench import scorer
    from scoring.structure import folder_economy
    score, _ = scorer("native", economy_weight=0.2, unscored_policy=None)
    rows = json.loads((package / "saved-results.json").read_text(encoding="utf-8"))
    if len(rows) != manifest["expected_outputs"]:
        raise AssertionError("Saved-output denominator changed")
    checked, tasks, skipped, skipped_tasks = 0, set(), 0, set()
    for row in rows:
        if tuple(row["packet"]) in unbuilt:
            skipped += 1
            skipped_tasks.add(row["canonical_task_id"])
            continue
        packet = json.loads(relative_file(package, row["packet"]).read_text(encoding="utf-8"))
        reference = json.loads(relative_file(package, row["reference"]).read_text(encoding="utf-8"))
        prediction = json.loads(relative_file(package, row["prediction"]).read_text(encoding="utf-8"))
        body_hashes = {r["id"]: sha256(r["text"].encode("utf-8")).hexdigest() for r in packet["records"]}
        compare(row["body_sha256"], body_hashes, "record bodies")
        actual = score(packet, reference, prediction)
        expected = row["expected"]
        for key in ["valid_output", "exact_tree", "clade_f1"]:
            compare(expected[key], actual[key], key)
        compare(expected["primary"], {k: actual["main"][k] for k in expected["primary"]}, "primary")
        compare(expected["levels"], actual["main"]["levels"], "levels")
        compare(expected["economy"], actual["main"]["economy"], "economy")
        paths = {r["id"]: r["path"] for r in prediction["assignments"]}
        gold = {r["id"]: r["path"] for r in reference["records"]}
        for weight, value in expected["lambda_diagnostics"].items():
            economy = folder_economy(paths, gold, weight=float(weight))["factor"]
            compare(value, {"structure_score": actual["main"]["level_balanced_triplet_f1"] * economy,
                            "folder_economy": economy}, "lambda." + weight)
        checked += 1
        tasks.add(row["canonical_task_id"])
    if len(tasks) + len(skipped_tasks) != manifest["expected_tasks"]:
        raise AssertionError("Task denominator changed")
    modules = {}
    for name, module in sys.modules.items():
        if name == "infoorgbench" or name.startswith(("scoring", "infoorgbench_native")) or name in {
                "hierarchy_scorecard", "frozen_tree_helpers"}:
            file = getattr(module, "__file__", None)
            if file is None or not Path(file).resolve().is_relative_to(package.resolve()):
                raise AssertionError("Undeclared/private scorer import: " + name)
            modules[name] = list(Path(file).relative_to(package).parts)
    return {"passed": True, "outputs_replayed": checked, "tasks": len(tasks),
            "outputs_skipped_unbuilt": skipped, "tasks_skipped_unbuilt": len(skipped_tasks),
            "primary_lambda": 0.2, "lambda_checks": 5 * checked,
            "metric_tolerance": 1e-12, "network_and_subprocesses_denied": True,
            "isolated_python": bool(sys.flags.isolated), "site_disabled": bool(sys.flags.no_site),
            "scorer_modules": modules, "manifest_sha256": sha256((package / "manifest.json").read_bytes()).hexdigest(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "scope": "Saved-output metric replay, not model regeneration or an access audit."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--require-thread", action="store_true", help="fail if the Thread packets have not been built")
    args = parser.parse_args()
    result = replay(args.package.resolve(), args.require_thread)
    with args.receipt.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "scorer_modules"}))
    if result["outputs_skipped_unbuilt"]:
        print(f"Skipped {result['outputs_skipped_unbuilt']} Thread outputs: build the Thread packets with build_thread.py (see docs/THREAD-DATA.md).")


if __name__ == "__main__":
    main()
