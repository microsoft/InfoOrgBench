# Copyright (c) The InfoOrgBench authors.
# Licensed under the MIT License.
from collections import Counter
import json
from pathlib import Path
import random
import re

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs" / "paper-pilot-20261019.json").read_text(encoding="utf-8"))


def public_projection(packet):
    records = packet.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("A public packet needs nonempty records")
    result = []
    for row in records:
        if (not isinstance(row, dict) or not isinstance(row.get("id"), str)
                or re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", row["id"]) is None
                or not isinstance(row.get("text"), str)
                or not isinstance(row.get("format"), str)):
            raise ValueError("Malformed public record")
        result.append({k: row[k] for k in CONFIG["public_record_fields"]})
    if len({row["id"] for row in result}) != len(result):
        raise ValueError("Duplicate public identifiers")
    return {"task_id": packet.get("task_id"), "records": result}


def _lexical(records):
    cfg = CONFIG["lexical"]
    vectorizer = TfidfVectorizer(
        lowercase=cfg["lowercase"], strip_accents=cfg["strip_accents"],
        stop_words=cfg["stop_words"], token_pattern=cfg["token_pattern"],
        ngram_range=tuple(cfg["ngram_range"]), sublinear_tf=cfg["sublinear_tf"],
        norm=cfg["norm"], max_features=cfg["max_features"])
    try:
        vectors = vectorizer.fit_transform([r["text"] for r in records])
        similarity = (vectors @ vectors.T).toarray()
        features = vectors.shape[1]
        zeros = int(np.count_nonzero(np.asarray(vectors.getnnz(axis=1)) == 0))
        degeneracy = "none"
    except ValueError as error:
        if "empty vocabulary" not in str(error):
            raise
        similarity = np.zeros((len(records), len(records)))
        features, zeros, degeneracy = 0, len(records), "empty_vocabulary"
    distances = np.clip(1 - similarity, 0, 1)
    np.fill_diagonal(distances, 0)
    if len(records) == 1:
        lower = upper = np.array([1])
    else:
        tree = linkage(squareform(distances, checks=True), method=cfg["linkage"])
        lower = fcluster(tree, cfg["lower_distance_threshold"], criterion="distance")
        upper = fcluster(tree, cfg["upper_distance_threshold"], criterion="distance")
    lower_order = {value: i + 1 for i, value in enumerate(dict.fromkeys(lower.tolist()))}
    upper_order = {value: i + 1 for i, value in enumerate(dict.fromkeys(upper.tolist()))}
    parents = {}
    assignments = []
    for row, lo, hi in zip(records, lower.tolist(), upper.tolist()):
        if lo in parents and parents[lo] != hi:
            raise AssertionError("Cuts of the same dendrogram must be nested")
        parents[lo] = hi
        assignments.append({"id": row["id"], "path": [
            f"topic-{upper_order[hi]:03d}", f"cluster-{lower_order[lo]:03d}"]})
    return assignments, {"features": features, "zero_vectors": zeros, "degeneracy": degeneracy,
                         "top_groups": len(upper_order), "lower_groups": len(lower_order)}


def predict(packet, method, seed=None):
    records = sorted(public_projection(packet)["records"], key=lambda row: row["id"])
    if method == "filed_flat":
        assignments = [{"id": row["id"], "path": ["collection", "records"]} for row in records]
        diagnostics = {"top_groups": 1, "lower_groups": 1, "degeneracy": "intentional_flat"}
    elif method in {"lexical", "random_shape"}:
        assignments, diagnostics = _lexical(records)
        if method == "random_shape":
            if type(seed) is not int or seed not in CONFIG["random_seeds"]:
                raise ValueError("Random assignments require a frozen seed")
            identities = [r["id"] for r in records]
            random.Random(seed).shuffle(identities)
            assignments = sorted(
                [{"id": identity, "path": row["path"]} for identity, row in zip(identities, assignments)],
                key=lambda row: row["id"])
            diagnostics = {**diagnostics, "seed": seed, "shape_source": "lexical_public_text_only"}
    else:
        raise ValueError("Unknown frozen method")
    if Counter(r["id"] for r in assignments) != Counter(r["id"] for r in records):
        raise AssertionError("Prediction inventory changed")
    return {"assignments": assignments, "diagnostics": diagnostics}
