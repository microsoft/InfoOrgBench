# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Main structural score for record-folder hierarchies.

S = F1_bal * E, where F1_bal is level-balanced resolved-triplet F1 over the
declared scored records and E is a bounded folder-economy factor. The frozen
vendor scorers remain unchanged; docs/EVALUATION.md defines every term.
"""

from collections import defaultdict

METRIC_VERSION = "structure-score-v1"
DEFAULT_ECONOMY_WEIGHT = 0.2
PRECISION_POLICY = ("Precision levels are reference levels that resolve at least one triple; output "
                    "refinement below every reference distinction is reported, not charged.")
COUNTS = ("reference_resolved", "output_resolved", "agreed", "conflicting", "output_unresolved", "unsupported")


def shared_depth(left, right):
    depth = 0
    for first, second in zip(left, right):
        if first != second:
            break
        depth += 1
    return depth


def strip_common_prefix(paths):
    """Remove folders that contain every record, so a neutral wrapper changes no level or folder count."""
    stripped = [tuple(path) for path in paths]
    removed = 0
    while stripped and all(stripped) and len({path[0] for path in stripped}) == 1:
        stripped = [path[1:] for path in stripped]
        removed += 1
    return stripped, removed


def _closest(ab, ac, bc):
    top = max(ab, ac, bc)
    if (ab == top) + (ac == top) + (bc == top) != 1:
        return -1
    return 0 if ab == top else 1 if ac == top else 2


def triplet_levels(output_paths, reference_paths, records=None):
    """Count rooted-triplet outcomes grouped by reference level.

    A triple is resolved in a tree when one pair shares strictly more folders
    than the other two pairs. Its level is the depth of the deepest reference
    folder containing all three records, after removing the reference's common
    wrapper (level 0 is the first reference distinction).
    """
    identities = sorted(reference_paths if records is None else records)
    if len(set(identities)) != len(identities):
        raise ValueError("Scored record identities must be unique")
    if any(identity not in reference_paths or identity not in output_paths for identity in identities):
        raise ValueError("Every scored record needs a reference and an output path")
    reference, _ = strip_common_prefix(reference_paths[identity] for identity in identities)
    output = [tuple(output_paths[identity]) for identity in identities]
    size = len(identities)
    reference_depth = [[shared_depth(reference[i], reference[j]) for j in range(size)] for i in range(size)]
    output_depth = [[shared_depth(output[i], output[j]) for j in range(size)] for i in range(size)]
    totals = defaultdict(lambda: [0] * len(COUNTS))
    for i in range(size):
        reference_i, output_i = reference_depth[i], output_depth[i]
        for j in range(i + 1, size):
            reference_j, output_j = reference_depth[j], output_depth[j]
            reference_ij, output_ij = reference_i[j], output_i[j]
            for k in range(j + 1, size):
                reference_ik, reference_jk = reference_i[k], reference_j[k]
                reference_pair = _closest(reference_ij, reference_ik, reference_jk)
                output_pair = _closest(output_ij, output_i[k], output_j[k])
                row = totals[min(reference_ij, reference_ik, reference_jk)]
                if reference_pair < 0:
                    if output_pair >= 0:
                        row[1] += 1
                        row[5] += 1
                    continue
                row[0] += 1
                if output_pair < 0:
                    row[4] += 1
                else:
                    row[1] += 1
                    row[2 if output_pair == reference_pair else 3] += 1
    return {level: dict(zip(COUNTS, values)) for level, values in sorted(totals.items())}


def level_balanced_f1(levels):
    """Macro-average triplet precision and recall over reference levels, then take F1."""
    reference_levels = {level for level, row in levels.items() if row["reference_resolved"]}
    rows = []
    for level, row in levels.items():
        charged = level in reference_levels and row["output_resolved"] > 0
        rows.append({"level": level, **row,
                     "precision": row["agreed"] / row["output_resolved"] if charged else None,
                     "recall": row["agreed"] / row["reference_resolved"] if level in reference_levels else None,
                     "in_precision": charged, "in_recall": level in reference_levels})
    shared = sum(row["agreed"] for row in levels.values())
    reference_total = sum(row["reference_resolved"] for row in levels.values())
    output_total = sum(row["output_resolved"] for row in levels.values())
    result = {"levels": rows, "agreed": shared, "reference_resolved": reference_total,
              "output_resolved": output_total,
              "pooled_triplet_f1": 2 * shared / (reference_total + output_total) if reference_total + output_total else None,
              "unsupported_refinement": sum(row["output_resolved"] for level, row in levels.items()
                                            if level not in reference_levels)}
    if not reference_levels:
        return {**result, "f1": None, "precision": None, "recall": None}
    recall = sum(row["recall"] for row in rows if row["in_recall"]) / len(reference_levels)
    precisions = [row["precision"] for row in rows if row["in_precision"]]
    precision = sum(precisions) / len(precisions) if precisions else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and precision + recall else 0.0
    return {**result, "f1": f1, "precision": precision, "recall": recall}


def folder_profile(paths_by_id):
    """Count folders and single-child folders after removing a common wrapper."""
    identities = list(paths_by_id)
    stripped, removed = strip_common_prefix(paths_by_id[identity] for identity in identities)
    children = defaultdict(set)
    for identity, path in zip(identities, stripped):
        for depth in range(1, len(path)):
            children[path[:depth]].add(("folder", path[depth]))
        if path:
            children[path].add(("record", identity))
    return {"folders": len(children), "single_child_folders": sum(len(members) == 1 for members in children.values()),
            "removed_wrapper_folders": removed}


def folder_economy(output_paths, reference_paths, weight=DEFAULT_ECONOMY_WEIGHT):
    if not 0 <= weight <= 1:
        raise ValueError("The folder-economy weight must lie in [0, 1]")
    output, reference = folder_profile(output_paths), folder_profile(reference_paths)
    excess = max(0, output["single_child_folders"] - reference["single_child_folders"])
    factor = 1 - weight * excess / output["folders"] if output["folders"] else 1.0
    return {"factor": factor, "weight": weight, "excess_single_child_folders": excess,
            "output": output, "reference": reference}


def structure_metrics(output_paths, reference_paths, scored=None, *, economy_weight=DEFAULT_ECONOMY_WEIGHT):
    """Score one valid output. Paths map record ID to folder components; E uses every supplied record."""
    if set(output_paths) != set(reference_paths):
        raise ValueError("Output and reference must contain the same record identities")
    balanced = level_balanced_f1(triplet_levels(output_paths, reference_paths, scored))
    economy = folder_economy(output_paths, reference_paths, economy_weight)
    f1 = balanced["f1"]
    return {"metric_version": METRIC_VERSION, "valid": True, "reason": None,
            "structure_score": f1 * economy["factor"] if f1 is not None else None,
            "level_balanced_triplet_f1": f1, "level_precision": balanced["precision"],
            "level_recall": balanced["recall"], "folder_economy": economy["factor"],
            "pooled_triplet_f1": balanced["pooled_triplet_f1"],
            "scored_records": len(reference_paths if scored is None else scored),
            "unsupported_refinement_triples": balanced["unsupported_refinement"],
            "levels": balanced["levels"], "economy": economy, "precision_policy": PRECISION_POLICY}


def invalid_metrics(reason, scored_records=None):
    """Zero structural quality for an invalid or ineligible output; the denominator keeps the task."""
    return {"metric_version": METRIC_VERSION, "valid": False, "reason": reason, "structure_score": 0.0,
            "level_balanced_triplet_f1": 0.0, "level_precision": None, "level_recall": 0.0,
            "folder_economy": None, "pooled_triplet_f1": 0.0, "scored_records": scored_records,
            "unsupported_refinement_triples": None, "levels": [], "economy": None,
            "precision_policy": PRECISION_POLICY}
