# Copyright (c) The InfoOrgBench authors.
# Licensed under the MIT License.
"""Read-only checker exposed to native external harnesses."""

import argparse
import hashlib
import json
from pathlib import Path
import re


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(workspace, records):
    workspace = Path(workspace).resolve()
    expected = {}
    for row in records:
        identity = row.get("id")
        if (not isinstance(identity, str)
                or re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", identity) is None
                or identity in expected
                or not isinstance(row.get("text"), str)):
            raise ValueError("Invalid input records")
        expected[identity] = hashlib.sha256(row["text"].encode("utf-8")).hexdigest()
    found = {}
    for path in workspace.rglob("*"):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ValueError("Unexpected linked workspace entry")
        if path.is_dir():
            continue
        if not path.is_file() or path.suffix != ".txt" or path.stat().st_nlink != 1:
            raise ValueError("Unexpected workspace entry")
        identity = path.stem
        if identity not in expected or identity in found or _hash(path) != expected[identity]:
            raise ValueError("Record identity, multiplicity or body changed")
        found[identity] = path
    if found.keys() != expected.keys():
        raise ValueError("Missing workspace record")
    assignments = []
    for row in records:
        relative = found[row["id"]].relative_to(workspace)
        assignments.append({"id": row["id"], "path": list(relative.parts[:-1])})
    pending = [
        row["id"] for row in assignments
        if not row["path"] or row["path"][0] == "inbox"
    ]
    return {
        "inventory_preserved": True,
        "records": len(assignments),
        "pending_ids": pending,
        "assignments": assignments,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    args = parser.parse_args()
    records = json.loads(args.records.read_text(encoding="utf-8"))
    result = check(args.workspace, records)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
