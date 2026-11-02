# Copyright (c) The InfoOrgBench authors.
# Licensed under the MIT License.
"""Attach the main structural score to the frozen track scorers and summarize main results."""

from collections import Counter
import math

from .record_quality import RULE_VERSION, flag_records
from . import structure

MAIN_SUMMARY_KEYS = ("structure_score", "level_balanced_triplet_f1", "folder_economy",
                     "level_precision", "level_recall", "pooled_triplet_f1")
MAIN_COLUMNS = (("structure_score", "Structure score S"), ("level_balanced_triplet_f1", "Level-balanced triplet F1"),
                ("folder_economy", "Folder economy E"))
OPTIONAL_COLUMNS = (("pooled_triplet_f1", "Pooled triplet F1"), ("clade_f1", "Clade F1"),
                    ("exact_tree_rate", "Exact tree"), ("level_precision", "Level precision"),
                    ("level_recall", "Level recall"))


def scored_records(track, packet):
    """Declared scored leaves: every record, except that the meeting track scores notes only."""
    if track == "meeting":
        return sorted(row["id"] for row in packet["records"] if row.get("format") == "note")
    return sorted(row["id"] for row in packet["records"])


def _agree(left, right):
    if left is None or right is None:
        return left is None and right is None
    return math.isclose(left, right, rel_tol=0, abs_tol=1e-12)


def main_block(track, packet, reference, prediction, frozen, *, economy_weight=structure.DEFAULT_ECONOMY_WEIGHT,
               unscored_policy=None):
    scored = scored_records(track, packet)
    gold = {row["id"]: row["path"] for row in reference["records"]}
    flags = flag_records(packet["records"], gold) if unscored_policy == RULE_VERSION else {}
    unscored = {identity: flags[identity] for identity in scored if identity in flags}
    scored = [identity for identity in scored if identity not in unscored]
    metadata = {
        "unscored_policy": unscored_policy,
        "unscored_records": len(unscored),
        "unscored_reasons": dict(sorted(Counter(unscored.values()).items())),
        "frozen_fields_scope": "all records; unchanged by the unscored-records policy",
    }
    if not frozen["valid_output"]:
        return {**structure.invalid_metrics("invalid_output: " + str(frozen.get("error")), len(scored)), **metadata}
    output = {row["id"]: row["path"] for row in prediction["assignments"]}
    block = structure.structure_metrics(output, gold, scored, economy_weight=economy_weight)
    meeting = track == "meeting"
    block["scored_leaves"] = "notes; supplied transcript anchors excluded" if meeting else "all records"
    if unscored:
        block["scored_leaves"] += "; quality-flagged records excluded from triplet credit"
    frozen_pooled = frozen.get("note_triplet_f1") if meeting else frozen.get("triplet_f1")
    if not unscored and not _agree(block["pooled_triplet_f1"], frozen_pooled):
        raise AssertionError("Main and frozen pooled resolved-triplet F1 disagree for " + str(packet.get("task_id")))
    return {**block, **metadata}


def main_summary(rows):
    """Task means; invalid outputs count as zero. E and level precision average valid outputs only."""
    blocks = [row["main"] for row in rows]
    informative = [block for block in blocks if block["structure_score"] is not None]
    valid = [block for block in informative if block["valid"]]

    def mean(key, selected):
        values = [block[key] for block in selected if block[key] is not None]
        return sum(values) / len(values) if values else None

    return {"metric_version": structure.METRIC_VERSION,
            "structure_score": mean("structure_score", informative),
            "level_balanced_triplet_f1": mean("level_balanced_triplet_f1", informative),
            "folder_economy": mean("folder_economy", valid),
            "level_precision": mean("level_precision", valid),
            "level_recall": mean("level_recall", informative),
            "pooled_triplet_f1": mean("pooled_triplet_f1", informative),
            "uninformative_tasks": len(blocks) - len(informative),
            "unscored_policy": blocks[0].get("unscored_policy") if blocks else None,
            "unscored_records": sum(block.get("unscored_records", 0) for block in blocks)}


def with_main(track, score, summarize, *, economy_weight=structure.DEFAULT_ECONOMY_WEIGHT, unscored_policy=None):
    """Wrap a frozen (score, summarize) pair; frozen result fields are returned unchanged."""
    if not 0 <= economy_weight <= 1:
        raise ValueError("The folder-economy weight must lie in [0, 1]")
    if unscored_policy not in (None, RULE_VERSION):
        raise ValueError("Unknown unscored-records policy: " + str(unscored_policy))

    def scored(packet, reference, prediction):
        result = score(packet, reference, prediction)
        result["main"] = main_block(track, packet, reference, prediction, result, economy_weight=economy_weight,
                                    unscored_policy=unscored_policy)
        return result

    def summarized(rows):
        return {**summarize(rows), **main_summary(rows)}

    return scored, summarized


def formatted(value):
    return "n/a" if value is None else f"{value:.3f}"


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def markdown_table(groups, columns, *, label="Group"):
    rows = []
    for name, summary in groups.items():
        values = {**summary, "clade_f1": summary.get("note_clade_f1", summary.get("clade_f1"))}
        rows.append([name, summary.get("tasks", "n/a"), summary.get("valid_outputs", "n/a")]
                    + [formatted(values.get(key)) for key, _ in columns])
    return table([label, "Tasks", "Valid"] + [title for _, title in columns], rows)


def main_results_markdown(title, groups, *, scope, all_metrics=False, label="Group"):
    """Main-score table first; other metrics appear in a second table only on request."""
    lines = [f"# {title}", "",
             "Structure score S = level-balanced resolved-triplet F1 x folder economy E "
             f"({structure.METRIC_VERSION}). Invalid outputs count as zero. See docs/EVALUATION.md.", "",
             markdown_table(groups, MAIN_COLUMNS, label=label), ""]
    if all_metrics:
        lines += ["## Additional metrics", "", markdown_table(groups, OPTIONAL_COLUMNS, label=label), ""]
    return "\n".join(lines + [scope, ""])
