# Copyright (c) The InfoOrgBench authors.
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
EXPECTED_SYSTEMS = 45
EXPECTED_TASKS_PER_FAMILY = 50
EXPECTED_TASK_ROWS = EXPECTED_SYSTEMS * len(FAMILIES) * EXPECTED_TASKS_PER_FAMILY
EXPECTED_COLUMNS = len(FAMILIES) * len(METRICS) + len(METRICS)
EXPECTED_METRIC_CELLS = EXPECTED_SYSTEMS * EXPECTED_COLUMNS
EXPECTED_CONTEXT_DECIMAL_TOKENS = 22
EXPECTED_DECIMAL_TOKENS = EXPECTED_METRIC_CELLS + EXPECTED_CONTEXT_DECIMAL_TOKENS


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
    if len(systems) != EXPECTED_SYSTEMS:
        failures.append(f"system count: expected {EXPECTED_SYSTEMS}, found {len(systems)}")
    if len(task_rows) != EXPECTED_TASK_ROWS:
        failures.append(f"per-task row count: expected {EXPECTED_TASK_ROWS}, found {len(task_rows)}")
    expected_groups = {(system["key"], family) for system in systems for family in FAMILIES}
    if set(grouped) != expected_groups:
        failures.append(f"per-task group count: expected {len(expected_groups)}, found {len(grouped)}")
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
    published_rows = published.get("rows", [])
    prefixes = published.get("row_prefix_decimal_tokens", [])
    columns = published.get("columns", [])
    if len(rendered_rows) != EXPECTED_SYSTEMS:
        failures.append(f"rendered row count: expected {EXPECTED_SYSTEMS}, found {len(rendered_rows)}")
    if len(published_rows) != EXPECTED_SYSTEMS:
        failures.append(f"published row count: expected {EXPECTED_SYSTEMS}, found {len(published_rows)}")
    if len(prefixes) != EXPECTED_SYSTEMS:
        failures.append(f"published prefix count: expected {EXPECTED_SYSTEMS}, found {len(prefixes)}")
    if len(columns) != EXPECTED_COLUMNS:
        failures.append(f"published column count: expected {EXPECTED_COLUMNS}, found {len(columns)}")
    if published.get("metric_cell_count") != EXPECTED_METRIC_CELLS:
        failures.append(f"published metric-cell count: expected {EXPECTED_METRIC_CELLS}, found {published.get('metric_cell_count')}")
    for row in rendered_rows:
        if len(row["values"]) != EXPECTED_COLUMNS:
            failures.append(f"rendered metric-cell count for {row['system']}: expected {EXPECTED_COLUMNS}, found {len(row['values'])}")
    for row in published_rows:
        if len(row.get("values", [])) != EXPECTED_COLUMNS:
            failures.append(f"published metric-cell count for {row.get('system')}: expected {EXPECTED_COLUMNS}, found {len(row.get('values', []))}")
    if len(rendered_rows) == len(published_rows):
        for index in range(len(rendered_rows)):
            if rendered_rows[index] != published_rows[index]:
                failures.append(f"published row mismatch: {rendered_rows[index]['system']}")

    preamble = list(published.get("preamble_decimal_tokens", []))
    context_count = len(preamble) + sum(len(prefix) for prefix in prefixes)
    declared_context = published.get("context_decimal_token_count")
    if declared_context != EXPECTED_CONTEXT_DECIMAL_TOKENS or context_count != EXPECTED_CONTEXT_DECIMAL_TOKENS:
        failures.append(f"published context token count: expected {EXPECTED_CONTEXT_DECIMAL_TOKENS}, "
                        f"declared {declared_context}, found {context_count}")
    sequence = preamble
    if len(prefixes) == len(rendered_rows):
        for index in range(len(rendered_rows)):
            sequence.extend(prefixes[index])
            sequence.extend(rendered_rows[index]["values"])
    decimal_sequence = published.get("decimal_sequence", [])
    declared_tokens = published.get("decimal_token_count")
    if declared_tokens != EXPECTED_DECIMAL_TOKENS:
        failures.append(f"published decimal token count: expected {EXPECTED_DECIMAL_TOKENS}, declared {declared_tokens}")
    if len(decimal_sequence) != declared_tokens:
        failures.append(f"published decimal token count: declared {declared_tokens}, found {len(decimal_sequence)}")
    if len(sequence) != declared_tokens:
        failures.append(f"rendered decimal token count: expected {declared_tokens}, found {len(sequence)}")
    if (type(declared_context) is not int or type(published.get("metric_cell_count")) is not int
            or declared_tokens != declared_context + published["metric_cell_count"]):
        failures.append("published decimal token count does not equal context plus metric cells")
    token_matches = (sum(sequence[index] == decimal_sequence[index] for index in range(len(sequence)))
                     if len(sequence) == len(decimal_sequence) else 0)
    if len(sequence) != len(decimal_sequence) or any(sequence[index] != decimal_sequence[index]
                                                     for index in range(len(sequence))):
        failures.append(f"published decimal sequence matches {token_matches}/{declared_tokens}")

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
