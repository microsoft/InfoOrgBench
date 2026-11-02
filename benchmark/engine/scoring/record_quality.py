# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Shared rule for records whose text cannot support a placement.

One definition serves both uses: building a filtered dataset version and
scoring a run while leaving such records unscored. The rule reads only record
text and the task's own reference grouping; it never reads model outputs or
scores, so it cannot be tuned on results.
"""

from collections import defaultdict
import re

RULE_VERSION = "record-quality-v1"
REASONS = ("ambiguous_duplicate", "release_bookkeeping", "acknowledgement_only")

_BOOKKEEPING = (
    re.compile(r"^bulk update: moved all \S+ non-blocker issues\b"),
    re.compile(r"^updated the target version to \S+ for preparing \S+ release\b"),
)
_TOKEN = re.compile(r"[a-z0-9+/.-]+")
_ACKNOWLEDGEMENT = re.compile(
    r"^(?:\+1|n/?a|none|tbd|lgtm|ok(?:ay)?|ack|done|thanks?(?: you)?|thx|ty)$"
    r"|^(?:\+1[.,!]?\s*)?(?:committed|pushed|merged|resolved)"
    r"(?:\s+(?:to|into)\s+(?:trunk|master|main|branch-[\w.]+))*"
    r"(?:\s*[.,!]?\s*(?:thanks?(?: you)?|thx))?$")


def normalized(text):
    return " ".join(str(text).split()).casefold()


def _acknowledgement(text):
    stripped = re.sub(r"[.,!\s]+$", "", text)
    return bool(stripped) and bool(_ACKNOWLEDGEMENT.match(stripped))


def flag_records(records, reference):
    """Return {record_id: reason} for records that the rule removes from placement credit.

    `records` are public packet records ({id, text}); `reference` maps record ID to its gold path
    (any sequence). A record whose normalized text also occurs under a different gold group in the
    same task is `ambiguous_duplicate`; otherwise text-only rules apply.
    """
    groups = defaultdict(set)
    for row in records:
        groups[normalized(row["text"])].add(tuple(reference[row["id"]]))
    flags = {}
    for row in records:
        text = normalized(row["text"])
        if len(groups[text]) > 1:
            flags[row["id"]] = "ambiguous_duplicate"
        elif any(pattern.match(text) for pattern in _BOOKKEEPING):
            flags[row["id"]] = "release_bookkeeping"
        elif _acknowledgement(text):
            flags[row["id"]] = "acknowledgement_only"
    return flags
