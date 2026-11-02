# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import json
import math
from pathlib import Path
import random
import re

import numpy as np
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.spatial.distance import squareform
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score

from paper_pilot.baselines import public_projection, predict as weak_predict

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs" / "completion-20261020.json").read_text(encoding="utf-8"))


def mask_text(text):
    count = 0
    for pattern in CONFIG["identifier_masking"]["patterns"]:
        text, matches = re.subn(pattern, " ", text, flags=re.I)
        count += matches
    return text, count


def _flat(records, reason, **details):
    return {"assignments": [{"id": row["id"], "path": ["collection", "records"]} for row in records],
            "diagnostics": {"degeneracy": reason, "top_groups": 1, "lower_groups": 1, **details}}


def silhouette_tree(records, masked=False):
    if len(records) < 3:
        return _flat(records, "fewer_than_three_records")
    cfg = CONFIG["silhouette"]["tfidf"]
    texts, matches = [], 0
    for record in records:
        value, count = mask_text(record["text"]) if masked else (record["text"], 0)
        texts.append(value)
        matches += count
    vectorizer = TfidfVectorizer(**{**cfg, "ngram_range": tuple(cfg["ngram_range"])})
    try:
        vectors = vectorizer.fit_transform(texts)
    except ValueError as error:
        if "empty vocabulary" not in str(error):
            raise
        return _flat(records, "empty_vocabulary", identifier_matches=matches)
    distances = np.clip(1 - (vectors @ vectors.T).toarray(), 0, 1)
    zeros = np.asarray(vectors.getnnz(axis=1)) == 0
    distances[np.ix_(zeros, zeros)] = 0
    distances[distances <= 1e-12] = 0
    np.fill_diagonal(distances, 0)
    if not np.any(distances):
        return _flat(records, "identical_vectors", identifier_matches=matches)
    tree = linkage(squareform(distances, checks=True), method="average")
    n = len(records)
    top_candidates = range(2, min(math.ceil(math.sqrt(n)), n - 1) + 1)
    leaf_candidates = range(3, min(n // 2, n - 1) + 1)
    cuts, scores, rejected = {}, {}, []
    same = np.triu(distances <= 1e-12, 1)
    for k in sorted(set(top_candidates) | set(leaf_candidates)):
        labels = cut_tree(tree, n_clusters=[k]).ravel()
        if np.any(same & (labels[:, None] != labels[None, :])):
            rejected.append(k)
            continue
        cuts[k] = labels
        scores[k] = float(silhouette_score(distances, labels, metric="precomputed"))
    pairs = [(top, leaf) for top in top_candidates for leaf in leaf_candidates
             if leaf >= 2 * top and top in cuts and leaf in cuts]
    if pairs:
        top_k, leaf_k = max(pairs, key=lambda x: (
            round((scores[x[0]] + scores[x[1]]) / 2, 12), -(x[0] + x[1]), -x[1], -x[0]))
        top, leaf = cuts[top_k], cuts[leaf_k]
        objective = (scores[top_k] + scores[leaf_k]) / 2
        reason = "none"
    elif cuts:
        leaf_k = max(cuts, key=lambda k: (round(scores[k], 12), -k))
        top_k, top, leaf, objective = 1, np.zeros(n, dtype=int), cuts[leaf_k], scores[leaf_k]
        reason = "no_valid_two_cut_pair"
    else:
        return _flat(records, "no_admissible_silhouette_cut", identifier_matches=matches,
                     rejected_duplicate_splitting_counts=rejected)
    upper_names = {k: i + 1 for i, k in enumerate(dict.fromkeys(top.tolist()))}
    lower_names = {k: i + 1 for i, k in enumerate(dict.fromkeys(leaf.tolist()))}
    parents, assignments = {}, []
    for record, upper, lower in zip(records, top.tolist(), leaf.tolist()):
        if lower in parents and parents[lower] != upper:
            raise AssertionError("Dendrogram cuts are not nested")
        parents[lower] = upper
        assignments.append({"id": record["id"], "path": [
            f"topic-{upper_names[upper]:03d}", f"cluster-{lower_names[lower]:03d}"]})
    return {"assignments": assignments, "diagnostics": {
        "degeneracy": reason, "top_groups": len(upper_names), "lower_groups": len(lower_names),
        "chosen_top_k": top_k, "chosen_leaf_k": leaf_k, "objective": objective,
        "upper_silhouette": scores.get(top_k), "lower_silhouette": scores[leaf_k],
        "admissible_pairs": len(pairs), "candidate_silhouettes": scores,
        "rejected_duplicate_splitting_counts": rejected, "zero_vectors": int(zeros.sum()),
        "identifier_matches": matches, "feature_view_masked": masked}}


def predict(packet, method, seed=None):
    public = public_projection(packet)
    records = sorted(public["records"], key=lambda r: r["id"])
    if method in {"filed_flat", "fixed_cut"}:
        return weak_predict(public, "filed_flat" if method == "filed_flat" else "lexical")
    masked = method in {"silhouette_identifier_masked", "random_identifier_masked_shape"}
    if method not in {"silhouette", "random_silhouette_shape", "silhouette_identifier_masked",
                      "random_identifier_masked_shape"}:
        raise ValueError("Unknown prespecified method")
    result = silhouette_tree(records, masked)
    if method.startswith("random_"):
        if type(seed) is not int or seed not in CONFIG["random_seeds"]:
            raise ValueError("Random method needs a prespecified seed")
        identities = [r["id"] for r in records]
        random.Random(seed).shuffle(identities)
        result = {"assignments": sorted(
            [{"id": identity, "path": row["path"]} for identity, row in zip(identities, result["assignments"])],
            key=lambda r: r["id"]), "diagnostics": {**result["diagnostics"], "seed": seed,
                                                   "shape": "public-only silhouette hierarchy"}}
    return result
