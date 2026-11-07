# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Rescore released Table 3 assignment trees with the released scorer."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys

FAMILIES = ("Recap", "Thread", "Design")
METRICS = ("structure_score", "pooled_triplet_f1", "folder_economy", "clade_f1", "exact_tree")
TOLERANCE = 1e-9


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def packet_for(root: Path, family: str, task: str, reference: dict, *,
               thread_packets: Path | None, reference_only_thread: bool) -> dict | None:
    public = root / "benchmark" / "inputs" / "public" / family / f"{task}.json"
    if public.is_file():
        return load_json(public)
    if family != "Thread":
        raise FileNotFoundError(f"Missing public packet: {public}")
    if thread_packets is not None:
        choices = (thread_packets / f"{task}.json", thread_packets / "Thread" / f"{task}.json")
        packet = next((path for path in choices if path.is_file()), None)
        if packet is not None:
            return load_json(packet)
    if reference_only_thread:
        return {"task_id": reference["task_id"],
                "records": [{"id": row["id"], "text": ""} for row in reference["records"]]}
    return None


def expected_rows(root: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    with (root / "results" / "per-task.csv").open(encoding="utf-8", newline="") as stream:
        return {(row["system"], row["family"], row["task"]): row for row in csv.DictReader(stream)}


def metric_values(actual: dict) -> dict[str, float | int | None]:
    return {
        "structure_score": actual["main"]["structure_score"],
        "pooled_triplet_f1": actual["main"]["pooled_triplet_f1"],
        "folder_economy": actual["main"]["folder_economy"],
        "clade_f1": actual["clade_f1"],
        "exact_tree": actual["exact_tree"],
    }


def rescore(root: Path, *, families: tuple[str, ...] = FAMILIES,
            thread_packets: Path | None = None, reference_only_thread: bool = False,
            require_thread: bool = False, require_complete: bool = False) -> dict:
    root = root.resolve()
    unknown = set(families) - set(FAMILIES)
    if unknown:
        raise ValueError("Unknown task families: " + ", ".join(sorted(unknown)))
    if thread_packets is not None:
        thread_packets = thread_packets.resolve()

    systems = load_json(root / "results" / "systems.json")["systems"]
    ledger = expected_rows(root)
    assignments_dir = root / "results" / "assignments"
    engine = root / "benchmark" / "engine"
    sys.path.insert(0, str(engine))
    try:
        from infoorgbench import scorer
        score, _ = scorer("native", economy_weight=0.2, unscored_policy=None)
    finally:
        sys.path.pop(0)

    thread_available = False
    if "Thread" in families:
        sample_reference = load_json(root / "benchmark" / "inputs" / "reference" / "Thread" / "mini-001.json")
        thread_available = packet_for(root, "Thread", "mini-001", sample_reference,
                                      thread_packets=thread_packets,
                                      reference_only_thread=reference_only_thread) is not None
        if require_thread and not thread_available:
            raise AssertionError("Thread packets are not built; pass --thread-packets or --reference-only-thread")

    coverage: dict[str, dict[str, dict[str, int]]] = {}
    mismatches: list[dict] = []
    catalog_only_differences: list[dict] = []
    missing: list[str] = []
    checked = 0
    for system in systems:
        key = system["key"]
        path = assignments_dir / f"{key}.json"
        released = load_json(path) if path.is_file() else {"tasks": {}}
        if not path.is_file():
            missing.append(f"{key}: assignment file")
        tasks = released.get("tasks", {})
        coverage[key] = {}
        for family in families:
            if family == "Thread" and not thread_available:
                coverage[key][family] = {"released": 0, "verified": 0, "missing": 0, "skipped_unbuilt": 50}
                continue
            verified = 0
            family_values: list[dict[str, float | int | None]] = []
            for number in range(1, 51):
                task = f"mini-{number:03d}"
                task_key = f"{family}/{task}"
                value = tasks.get(task_key)
                if value is None:
                    missing.append(f"{key}|{task_key}")
                    continue
                expected = ledger[(key, family, task)]
                if value.get("run") != expected["run"]:
                    mismatches.append({"system": key, "task": task_key, "metric": "run",
                                       "expected": expected["run"], "actual": value.get("run")})
                    continue
                reference = load_json(root / "benchmark" / "inputs" / "reference" / family / f"{task}.json")
                packet = packet_for(root, family, task, reference, thread_packets=thread_packets,
                                    reference_only_thread=reference_only_thread)
                if packet is None:
                    raise AssertionError(f"Thread packet source changed while scoring {task_key}")
                actual = score(packet, reference, {"assignments": value["assignments"]})
                values = metric_values(actual)
                family_values.append(values)
                task_ok = True
                if expected["valid_output"]:
                    wanted_valid = expected["valid_output"].lower() == "true"
                    if bool(actual["valid_output"]) != wanted_valid:
                        mismatches.append({"system": key, "task": task_key, "metric": "valid_output",
                                           "expected": wanted_valid, "actual": actual["valid_output"]})
                        task_ok = False
                for metric in METRICS:
                    if expected[metric] == "":
                        continue
                    wanted, observed = float(expected[metric]), values[metric]
                    if observed is None or not math.isclose(wanted, float(observed), rel_tol=0, abs_tol=TOLERANCE):
                        mismatches.append({"system": key, "task": task_key, "metric": metric,
                                           "expected": wanted, "actual": observed})
                        task_ok = False
                checked += 1
                verified += int(task_ok)
            released_count = sum(name.startswith(family + "/") for name in tasks)
            if released_count == 50 and len(family_values) == 50:
                published = system["families"][family.lower()]
                for field, column in (("S", "structure_score"), ("T", "pooled_triplet_f1"),
                                      ("E", "folder_economy")):
                    observed = sum(float(row[column]) for row in family_values if row[column] is not None) / 50
                    wanted = float(published[field])
                    if not math.isclose(wanted, observed, rel_tol=0, abs_tol=TOLERANCE):
                        difference = {"system": key, "task": family, "metric": "family." + column,
                                      "expected": wanted, "actual": observed}
                        per_task_available = all(ledger[(key, family, f"mini-{number:03d}")][column]
                                                 for number in range(1, 51))
                        (mismatches if per_task_available else catalog_only_differences).append(difference)
            coverage[key][family] = {"released": released_count, "verified": verified,
                                     "missing": 50 - released_count, "skipped_unbuilt": 0}

    passed = not mismatches and (not require_complete or not missing)
    return {
        "passed": passed,
        "outputs_checked": checked,
        "metric_tolerance": TOLERANCE,
        "metric_mismatches": mismatches,
        "catalog_only_differences": catalog_only_differences,
        "missing_outputs": missing,
        "coverage": coverage,
        "thread_mode": ("built" if thread_available and not reference_only_thread
                        else "reference-only" if reference_only_thread else "skipped-unbuilt"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--families", nargs="+", choices=FAMILIES, default=list(FAMILIES))
    parser.add_argument("--thread-packets", type=Path,
                        help="directory containing locally built Thread mini-NNN.json packets")
    parser.add_argument("--reference-only-thread", action="store_true",
                        help="score Thread structure from released references without Jira text")
    parser.add_argument("--require-thread", action="store_true",
                        help="fail unless Thread is scored rather than skipped")
    parser.add_argument("--require-complete", action="store_true",
                        help="treat missing assignment outputs as failure")
    args = parser.parse_args(argv)
    try:
        result = rescore(args.root, families=tuple(args.families), thread_packets=args.thread_packets,
                         reference_only_thread=args.reference_only_thread,
                         require_thread=args.require_thread, require_complete=args.require_complete)
    except (AssertionError, FileNotFoundError, ValueError) as error:
        print(f"FAIL: {error}")
        return 1
    for system, families in result["coverage"].items():
        text = ", ".join(f"{family} {row['verified']}/{row['released']} verified"
                         + (f" ({row['skipped_unbuilt']} skipped)" if row["skipped_unbuilt"] else "")
                         for family, row in families.items())
        print(f"{system}: {text}")
    print(f"Checked {result['outputs_checked']} outputs; {len(result['metric_mismatches'])} per-task metric mismatches; "
          f"{len(result['catalog_only_differences'])} catalog-only aggregate differences; "
          f"{len(result['missing_outputs'])} missing outputs; Thread={result['thread_mode']}")
    for row in result["catalog_only_differences"]:
        print(f"CATALOG-ONLY: {row['system']} {row['task']} {row['metric']}: "
              f"expected {row['expected']!r}, rescored {row['actual']!r}")
    print("PASS" if result["passed"] else "FAIL")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
