# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Verify the public InfoOrgBench Table 3 ledger using only the Python standard library."""

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FAMILIES = ("recap", "thread", "design")
METRICS = ("T", "E", "S")
TOLERANCE = 1e-9


def load_json(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def number(value):
    return None if value in (None, "") else float(value)


def display(value, penalty=False):
    return f"{100 * (1 - value):.1f}" if penalty else f"{100 * value:.1f}"


def main():
    ledger = load_json("systems.json")
    published = load_json("table3-published.json")
    systems = ledger["systems"]
    with (ROOT / "per-task.csv").open(encoding="utf-8", newline="") as handle:
        task_rows = list(csv.DictReader(handle))
    grouped = defaultdict(list)
    for row in task_rows:
        grouped[(row["system"], row["family"].lower())].append(row)

    failures = []
    catalog_only = []
    computed = {}
    checked_cells = 0
    for system in systems:
        key = system["key"]
        family_values = {}
        for family in FAMILIES:
            spec = system["families"][family]
            rows = grouped[(key, family)]
            if len(rows) != 50 or len({row["task"] for row in rows}) != 50:
                failures.append(f"{key} {family}: expected 50 uniquely named task rows")
                continue
            catalog_metrics = set(spec.get("catalog_only_metrics", []))
            triplet = [number(row["pooled_triplet_f1"]) for row in rows]
            structure = [number(row["structure_score"]) for row in rows]
            economy = [number(row["folder_economy"]) for row in rows if row["valid_output"].lower() != "false" and row["folder_economy"] != ""]
            current = {
                "T": statistics.mean(triplet) if all(value is not None for value in triplet) else None,
                "S": statistics.mean(structure) if all(value is not None for value in structure) else None,
                "E": statistics.mean(economy) if economy and len([value for value in triplet if value is not None]) == 50 else None,
            }
            family_values[family] = current
            for metric in METRICS:
                label = f"{system['model']['display_name']} / {system['harness']['display_name']} / {family.title()} / {metric}"
                if metric in catalog_metrics:
                    catalog_only.append(label + ": " + spec["catalog_only_reasons"][metric])
                    continue
                if current[metric] is None:
                    failures.append(label + ": per-task value is incomplete")
                elif abs(current[metric] - spec[metric]) > TOLERANCE:
                    failures.append(f"{label}: rows={current[metric]:.17g}, systems.json={spec[metric]:.17g}")
                else:
                    checked_cells += 1
        computed[key] = family_values
        for metric in METRICS:
            expected_avg = statistics.mean(system["families"][family][metric] for family in FAMILIES)
            if abs(expected_avg - system["avg"][metric]) > TOLERANCE:
                failures.append(f"{key} Avg {metric}: family cells do not reproduce systems.json")
            if any(metric in system["families"][family].get("catalog_only_metrics", []) for family in FAMILIES):
                catalog_only.append(f"{system['model']['display_name']} / {system['harness']['display_name']} / Avg / {metric}: one or more family cells are catalog-only")
                continue
            row_avg = statistics.mean(computed[key][family][metric] for family in FAMILIES)
            if abs(row_avg - system["avg"][metric]) > TOLERANCE:
                failures.append(f"{key} Avg {metric}: rows={row_avg:.17g}, systems.json={system['avg'][metric]:.17g}")
            else:
                checked_cells += 1

    rendered_rows = []
    for system in systems:
        values = []
        for family in FAMILIES:
            cell = system["families"][family]
            values.extend((display(cell["T"]), display(cell["E"], True), display(cell["S"])))
        values.extend((display(system["avg"]["T"]), display(system["avg"]["E"], True), display(system["avg"]["S"])))
        rendered_rows.append({"system": system["key"], "values": values})
    if rendered_rows != published["rows"]:
        for actual, expected in zip(rendered_rows, published["rows"]):
            if actual != expected:
                failures.append(f"published row mismatch: {actual['system']}")

    sequence = list(published["preamble_decimal_tokens"])
    for prefix, row in zip(published["row_prefix_decimal_tokens"], rendered_rows):
        sequence.extend(prefix)
        sequence.extend(row["values"])
    token_matches = sum(a == b for a, b in zip(sequence, published["decimal_sequence"]))
    if sequence != published["decimal_sequence"]:
        failures.append(f"published decimal sequence matches {token_matches}/{published['decimal_token_count']}")

    print(f"Systems: {len(systems)}")
    print(f"Per-task rows: {len(task_rows)}")
    print(f"Per-task-derived source cells checked at 1e-9: {checked_cells}")
    print(f"Published decimal tokens: {token_matches}/{published['decimal_token_count']} matched ({published['metric_cell_count']} metric cells)")
    print("Catalog-level checks:")
    for item in catalog_only:
        print(f"  - {item}")
    if failures:
        print("FAIL")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
