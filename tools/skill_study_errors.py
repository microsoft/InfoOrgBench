# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Error analysis for the community-skills study: where, if anywhere, do skills help?

Rescores every final output with the released scorer, adds family-specific error
modes, and compares each condition with the concurrent no-skill control inside
task strata. Task difficulty comes from the published no-skill run, not from the
control, so strata do not regress toward the mean. Exploratory analysis.

    python tools/skill_study_errors.py --out .local/skill-study
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_study as study  # noqa: E402

REFERENCES = ("published", "pinned-irrelevant-mcp-builder")
ORGANIZING = ("pinned-composio-file-organizer", "pinned-claude-office-file-organizer",
              "pinned-composio-invoice-organizer")
CONTRASTS = ORGANIZING + ("available-composio-file-organizer",) + REFERENCES
RESAMPLES = 4000


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _published_outputs():
    rows = {}
    for model, system in study.PUBLISHED.items():
        for key, row in _load(study.ROOT / "results" / "assignments" / (system + ".json"))["tasks"].items():
            family, task = key.split("/")
            rows[(model, family, task)] = row["assignments"]
    return rows


def _share(numerator, denominator):
    return numerator / denominator if denominator else None


def error_modes(family, reference, assignments):
    truth = {row["id"]: row["path"] for row in reference["records"]}
    placed = {row["id"]: row["path"] for row in assignments}
    tops = defaultdict(list)
    for identity, path in placed.items():
        tops[path[0] if path else ""].append(identity)
    modes = {}
    if family == "Recap":
        meetings = defaultdict(list)
        for identity, path in truth.items():
            meetings[path[0]].append(identity)
        modes["mixed_top_folders"] = _share(sum(len({truth[i][0] for i in ids}) > 1 for ids in tops.values()), len(tops))
        modes["split_meetings"] = _share(sum(len({(placed[i] or [""])[0] for i in ids}) > 1
                                             for ids in meetings.values()), len(meetings))
    if family == "Design":
        proposals = defaultdict(list)
        for identity, path in truth.items():
            proposals[tuple(path)].append(identity)
        majority = {top: Counter(truth[i][0] for i in ids).most_common(1)[0][0] for top, ids in tops.items()}
        intact = misfiled = 0
        for (sig, _), ids in proposals.items():
            folders = {(placed[i] or [""])[0] for i in ids}
            if len(folders) == 1:
                intact += 1
                misfiled += majority[folders.pop()] != sig
        modes["intact_proposals"] = intact
        modes["misfiled_intact_proposals"] = misfiled
    return modes


def rescore(out):
    score, _ = study._scorer()
    published = _published_outputs()
    rows = []
    for family in study.FAMILIES:
        for task in study.TASKS:
            packet = _load(study.ROOT / "benchmark" / "inputs" / "public" / family / (task + ".json"))
            reference = _load(study.ROOT / "benchmark" / "inputs" / "reference" / family / (task + ".json"))
            features = {"records": len(reference["records"]),
                        "parents": len({row["path"][0] for row in reference["records"]}),
                        "leaves": len({tuple(row["path"]) for row in reference["records"]})}
            for model in study.MODELS:
                sources = [(condition, study._final_assignments(out, (condition, model, family, task)))
                           for condition in study.CONDITIONS]
                sources = [(condition, assignments) for condition, assignments in sources if assignments is not None]
                if (model, family, task) in published:
                    sources.append(("published", published[(model, family, task)]))
                for condition, assignments in sources:
                    result = score(packet, reference, {"assignments": assignments})
                    main = result["main"]
                    row = {"condition": condition, "model": model, "family": family, "task": task, **features,
                           "valid": bool(result["valid_output"]), "structure_score": 100 * main["structure_score"],
                           "folder_economy": main["folder_economy"]}
                    for level in main.get("levels") or []:
                        if level["level"] not in (0, 1):
                            continue
                        resolved = level["reference_resolved"]
                        name = "parent" if level["level"] == 0 else "leaf"
                        for outcome in ("agreed", "conflicting", "output_unresolved"):
                            row["%s_%s" % (name, outcome)] = _share(level[outcome], resolved)
                    row.update(error_modes(family, reference, assignments))
                    rows.append(row)
    return rows


def _tertiles(values):
    ordered = sorted(values)
    cut = (ordered[len(ordered) // 3], ordered[(2 * len(ordered)) // 3])
    return lambda value: 0 if value < cut[0] else (1 if value < cut[1] else 2)


def strata(rows, model):
    """Return {cell name: set of (family, task)} for one model."""
    control = {(r["family"], r["task"]): r for r in rows if r["condition"] == "control" and r["model"] == model}
    published = {(r["family"], r["task"]): r["structure_score"] for r in rows
                 if r["condition"] == "published" and r["model"] == model}
    cells = defaultdict(set)
    for family in study.FAMILIES:
        keys = [key for key in control if key[0] == family]
        cells["family: " + family].update(keys)
        scored = [key for key in keys if key in published]
        bucket = _tertiles([published[key] for key in scored])
        for key in scored:
            cells["%s difficulty: %s" % (family, ("hard", "middle", "easy")[bucket(published[key])])].add(key)
        if family == "Design":
            continue
        for feature, labels in (("leaves", ("few", "middle", "many")), ("records", ("fewer", "middle", "more"))):
            bucket = _tertiles([control[key][feature] for key in keys])
            for key in keys:
                cells["%s %s: %s" % (family, feature, labels[bucket(control[key][feature])])].add(key)
        for key in keys:
            parents = control[key]["parents"]
            label = "2" if parents == 2 else ("3-4" if family == "Recap" else "3")
            cells["%s parent groups: %s" % (family, label)].add(key)
    return cells


def _cell_test(differences, rng):
    mean = sum(differences) / len(differences)
    boots = sorted(sum(rng.choice(differences) for _ in differences) / len(differences) for _ in range(RESAMPLES))
    extreme = sum(abs(sum(d if rng.random() < 0.5 else -d for d in differences)) / len(differences) >= abs(mean) - 1e-12
                  for _ in range(RESAMPLES))
    return {"n": len(differences), "mean": mean, "ci95": [boots[int(0.025 * RESAMPLES)], boots[int(0.975 * RESAMPLES) - 1]],
            "p": (extreme + 1) / (RESAMPLES + 1)}


def stratum_analysis(rows):
    by_key = {(r["condition"], r["model"], r["family"], r["task"]): r for r in rows}
    rng = random.Random(study.SEED)
    results = []
    for model in study.MODELS:
        for cell, keys in sorted(strata(rows, model).items()):
            for condition in CONTRASTS:
                differences = [by_key[(condition, model) + key]["structure_score"] - by_key[("control", model) + key]["structure_score"]
                               for key in sorted(keys) if (condition, model) + key in by_key]
                if len(differences) >= 5:
                    results.append({"model": model, "cell": cell, "condition": condition, **_cell_test(differences, rng)})
    for group in (ORGANIZING, ("available-composio-file-organizer",)):
        tested = [row for row in results if row["condition"] in group]
        for row, adjusted in zip(tested, study.holm([row["p"] for row in tested])):
            row["p_holm"] = adjusted
    lookup = {(r["model"], r["cell"], r["condition"]): r for r in results}
    for row in results:
        if row["condition"] not in ORGANIZING:
            continue
        other = [m for m in study.MODELS if m != row["model"]][0]
        replicate = lookup.get((other, row["cell"], row["condition"]))
        irrelevant = lookup.get((row["model"], row["cell"], "pinned-irrelevant-mcp-builder"))
        row["helps_by_decision_rule"] = bool(
            row["mean"] > 0 and row["p_holm"] < 0.05 and replicate and replicate["mean"] > 0
            and irrelevant and row["mean"] > irrelevant["mean"])
    return results


def _pearson(x, y):
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return sxy / (sx * sy) if sx and sy else float("nan")


def replication(rows):
    """Correlation over tasks of Haiku and Sonnet per-task differences for the same contrast."""
    by_key = {(r["condition"], r["model"], r["family"], r["task"]): r for r in rows}
    rng = random.Random(study.SEED)
    results = []
    for condition in CONTRASTS:
        for family in ("all",) + study.FAMILIES:
            pairs = []
            for fam in (study.FAMILIES if family == "all" else (family,)):
                for task in study.TASKS:
                    keys = [(condition, model, fam, task) for model in study.MODELS]
                    controls = [("control", model, fam, task) for model in study.MODELS]
                    if all(key in by_key for key in keys + controls):
                        pairs.append(tuple(by_key[k]["structure_score"] - by_key[c]["structure_score"]
                                           for k, c in zip(keys, controls)))
            x, y = [p[0] for p in pairs], [p[1] for p in pairs]
            r = _pearson(x, y)
            shuffled = y[:]
            extreme = 0
            for _ in range(RESAMPLES):
                rng.shuffle(shuffled)
                extreme += abs(_pearson(x, shuffled)) >= abs(r) - 1e-12
            results.append({"condition": condition, "family": family, "tasks": len(pairs), "r": r,
                            "p": (extreme + 1) / (RESAMPLES + 1)})
    return results


def error_mode_shifts(rows):
    by_key = {(r["condition"], r["model"], r["family"], r["task"]): r for r in rows}
    metrics = ("parent_agreed", "parent_conflicting", "parent_output_unresolved", "leaf_agreed",
               "leaf_conflicting", "leaf_output_unresolved", "folder_economy", "mixed_top_folders",
               "split_meetings", "misfiled_intact_proposals", "intact_proposals")
    rng = random.Random(study.SEED)
    results = []
    for model in study.MODELS:
        for family in study.FAMILIES:
            for metric in metrics:
                base = [by_key[("control", model, family, t)].get(metric) for t in study.TASKS]
                if all(value is None for value in base):
                    continue
                row = {"model": model, "family": family, "metric": metric,
                       "control_mean": sum(v for v in base if v is not None) / sum(v is not None for v in base)}
                for condition in CONTRASTS:
                    differences = []
                    for task, value in zip(study.TASKS, base):
                        other = by_key.get((condition, model, family, task), {}).get(metric)
                        if value is not None and other is not None:
                            differences.append(other - value)
                    if differences:
                        mean = sum(differences) / len(differences)
                        boots = sorted(sum(rng.choice(differences) for _ in differences) / len(differences)
                                       for _ in range(1000))
                        row[condition] = {"diff": mean, "ci95": [boots[25], boots[974]], "n": len(differences)}
                results.append(row)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    target = out / "error-analysis"
    target.mkdir(parents=True, exist_ok=True)
    rows = rescore(out)
    fields = sorted({key for row in rows for key in row}, key=lambda k: (k not in rows[0], k))
    with open(target / "per-output.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    strata_rows = stratum_analysis(rows)
    (target / "strata.json").write_text(json.dumps(strata_rows, indent=2) + "\n", encoding="utf-8")
    replication_rows = replication(rows)
    (target / "replication.json").write_text(json.dumps(replication_rows, indent=2) + "\n", encoding="utf-8")
    shifts = error_mode_shifts(rows)
    (target / "error-modes.json").write_text(json.dumps(shifts, indent=2) + "\n", encoding="utf-8")
    helps = [row for row in strata_rows if row.get("helps_by_decision_rule")]
    print("outputs rescored:", len(rows), " stratum cells:", len(strata_rows), " cells meeting the help rule:", len(helps))
    for row in helps:
        print("  HELP", row["model"], row["cell"], row["condition"], "%+.2f" % row["mean"])


if __name__ == "__main__":
    main()
