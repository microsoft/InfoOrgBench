# Copyright (c) The InfoOrgBench authors.
# Licensed under the MIT License.
"""Additive, label-invariant audit of frozen organization outcomes."""

from collections.abc import Mapping, Sequence
from typing import Any

from frozen_tree_helpers import (
    descendant_sets, hierarchy_triplets, partition_diagnostics, pending_records, set_agreement,
)

Row = Mapping[str, Any]
PARTITION_SCOPE = (
    "Partition diagnostics. Mixing is H(reference|output); splitting is H(output|reference), in bits. "
    "Lower is better. B-cubed includes self credit. Parent labels and common wrappers are ignored. "
    "Evaluator-only parent assignments are withheld; allowed source text and metadata remain visible."
)


def validate_rows(rows: Sequence[Row]) -> dict[str, Row]:
    if not rows:
        raise ValueError("An evaluated hierarchy needs at least one record")
    index = {}
    for row in rows:
        identity = row.get("id")
        path = row.get("path")
        if not isinstance(identity, str) or not identity or identity in index:
            raise ValueError("Record identities must be nonempty and unique")
        if not isinstance(path, list) or any(
                not isinstance(part, str) or not part.strip()
                or part in {".", ".."} for part in path):
            raise ValueError(f"Invalid folder path for {identity}")
        if not isinstance(row.get("text"), str):
            raise ValueError(f"Missing record body for {identity}")
        index[identity] = row
    return index


def score(rows: Sequence[Row], reference: Sequence[Row]) -> dict[str, Any]:
    actual = validate_rows(rows)
    gold = validate_rows(reference)
    if actual.keys() != gold.keys():
        raise ValueError("Tree comparison requires identical record identities")
    altered = sorted(key for key in gold if gold[key]["text"] != actual[key]["text"])
    if altered:
        raise ValueError(f"Record preservation failed for: {altered}")
    predicted_clades = descendant_sets(rows)
    gold_clades = descendant_sets(reference)
    clades = set_agreement(predicted_clades, gold_clades)
    forward = hierarchy_triplets(rows, reference)
    reverse = hierarchy_triplets(reference, rows)
    shared = forward["counts"].get("preserved", 0)
    if shared != reverse["counts"].get("preserved", 0):
        raise AssertionError("Rooted-triplet intersection is not symmetric")
    reference_count = forward["resolved_reference_triplets"]
    prediction_count = reverse["resolved_reference_triplets"]
    denominator = reference_count + prediction_count
    depth_scores = [
        item["preserved_fraction"]
        for item in forward["by_reference_folder_depth"].values()
    ]
    partitions = partition_diagnostics(rows, reference)
    return {
        "records": len(gold),
        "inventory_and_content_valid": True,
        "filed_fraction": 1 - len(pending_records(rows)) / len(rows),
        "clades": clades,
        "rooted_rf": len(predicted_clades ^ gold_clades),
        "rooted_rf_normalized": (1 - clades["f1"]) if clades["f1"] is not None else None,
        "topology_exact_after_unary_suppression": predicted_clades == gold_clades,
        "triplets": {
            **forward,
            "prediction_resolved": prediction_count,
            "precision": shared / prediction_count if prediction_count else None,
            "recall": shared / reference_count if reference_count else None,
            "symmetric_f1": 2 * shared / denominator if denominator else None,
            "prediction_resolved_reference_unresolved": reverse["counts"].get("unresolved", 0),
            "depth_macro_recall": sum(depth_scores) / len(depth_scores) if depth_scores else None,
        },
        "partition": {
            **{key: value for key, value in partitions.items()
               if key not in {"per_file", "contingency"}},
            "scope": PARTITION_SCOPE,
        },
        "interpretation": "Source-reference agreement, not uniquely correct human organization.",
    }
