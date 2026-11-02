# Copyright (c) The InfoOrgBench authors.
# Licensed under the MIT License.
"""Verify and score path predictions without any model service or source archive."""

import argparse
from collections import Counter
import hashlib
import json
import logging
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "metrics"))
from hierarchy_scorecard import score

LOG = logging.getLogger(__name__)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    manifest = load(ROOT / "manifest.json")
    construction = load(ROOT / "construction.json")
    seen, records, tasks = set(), 0, {}
    for entry in manifest["tasks"]:
        identity = entry["id"]
        if not isinstance(identity, str) or re.fullmatch(r"(dev|test)-[0-9]{2}", identity) is None:
            raise ValueError("Invalid task identifier")
        packet_path, gold_path = ROOT / "public" / f"{identity}.json", ROOT / "references" / f"{identity}.json"
        if sha(packet_path) != entry["packet_sha256"] or sha(gold_path) != entry["reference_sha256"]:
            raise ValueError("Frozen task/reference changed: " + identity)
        packet, reference = load(packet_path), load(gold_path)
        if packet["task_id"] != identity or reference["task_id"] != identity:
            raise ValueError("Task identity binding differs")
        inputs = {row["id"]: row for row in packet["records"]}
        if len(inputs) != len(packet["records"]) or {r["id"] for r in reference["records"]} != inputs.keys():
            raise ValueError("Input/reference inventory mismatch")
        for row in reference["records"]:
            if hashlib.sha256(inputs[row["id"]]["text"].encode("utf-8")).hexdigest() != row["content_sha256"]:
                raise ValueError("Source body bytes changed")
        units = set(construction["task_units"][identity])
        if len(units) != entry["proposal_units"] or seen & units:
            raise ValueError("Proposal overlap across benchmark tasks")
        seen.update(units)
        records += len(inputs)
        tasks[identity] = entry
    if len(tasks) != 12 or records != 144 or len(seen) != 72:
        raise ValueError("Benchmark cardinality changed")
    return {"passed": True, "tasks": len(tasks), "records": records, "proposal_units": len(seen),
            "splits": manifest["split_counts"], "cross_task_proposal_overlap": 0}


def evaluate_task(packet, reference, prediction):
    inputs = {row["id"]: row for row in packet["records"]}
    gold = [{"id": row["id"], "path": row["path"], "text": inputs[row["id"]]["text"]}
            for row in reference["records"]]
    try:
        if not isinstance(prediction, dict) or set(prediction) != {"assignments"} or not isinstance(prediction["assignments"], list):
            raise ValueError("Expected one assignments array")
        ids = [row.get("id") if isinstance(row, dict) else None for row in prediction["assignments"]]
        if any(not isinstance(identity, str) for identity in ids) or Counter(ids) != Counter(inputs.keys()):
            raise ValueError("Every input ID must occur exactly once")
        actual = []
        for row in prediction["assignments"]:
            if (not isinstance(row, dict) or set(row) != {"id", "path"}
                    or not isinstance(row["id"], str) or row["id"] not in inputs):
                raise ValueError("Invalid or unknown assignment")
            path = row["path"]
            if (not isinstance(path, list) or not 1 <= len(path) <= 4
                    or any(not isinstance(part, str) or not part.strip() or part in {".", ".."}
                           or "/" in part or "\\" in part or any(ord(c) < 32 for c in part)
                           for part in path)):
                raise ValueError("Invalid folder components")
            actual.append({"id": row["id"], "path": path, "text": inputs[row["id"]]["text"]})
        metrics = score(actual, gold)
    except ValueError as error:
        LOG.warning("Invalid prediction for %s: %s", packet["task_id"], error)
        return {"task_id": packet["task_id"], "valid_output": False, "exact_tree": 0,
                "clade_f1": 0.0, "triplet_f1": 0.0, "error": str(error)}
    return {"task_id": packet["task_id"], "valid_output": True,
            "exact_tree": int(metrics["topology_exact_after_unary_suppression"]),
            "clade_f1": metrics["clades"]["f1"], "triplet_f1": metrics["triplets"]["symmetric_f1"],
            "diagnostics": metrics, "error": None,
            "validity_scope": "ID/path prediction validity. Input bodies are immutable by reference; no physical file-mutation claim."}


def summary(rows):
    if not rows or len({row["task_id"] for row in rows}) != len(rows):
        raise ValueError("Need one scored observation per task for this summary")
    return {"tasks": len(rows), "valid_outputs": sum(row["valid_output"] for row in rows),
            "exact_trees": sum(row["exact_tree"] for row in rows),
            "exact_tree_rate": sum(row["exact_tree"] for row in rows) / len(rows),
            "clade_f1": sum(row["clade_f1"] for row in rows) / len(rows),
            "triplet_f1": sum(row["triplet_f1"] for row in rows) / len(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--split", choices=("dev", "test", "all"), default="test")
    args = parser.parse_args()
    verified = verify()
    if args.verify:
        print(json.dumps(verified, indent=2))
        return
    if args.predictions is None:
        parser.error("--predictions or --verify is required")
    rows = []
    for task in load(ROOT / "manifest.json")["tasks"]:
        if args.split != "all" and task["split"] != args.split:
            continue
        prediction_path = args.predictions / f"{task['id']}.json"
        if not prediction_path.is_file():
            raise ValueError("Missing attempted task prediction: " + task["id"])
        rows.append(evaluate_task(load(ROOT / "public" / prediction_path.name),
                                  load(ROOT / "references" / prediction_path.name), load(prediction_path)))
    print(json.dumps({"summary": summary(rows), "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
