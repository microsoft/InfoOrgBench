# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Rebuild the 50 Thread task packets from Apache Hadoop Jira responses.

Thread record text comes from the public Apache Hadoop issue tracker and is
not redistributed with this benchmark. Download the issue responses listed in
sources/hadoop-jira/issues.json (see docs/THREAD-DATA.md), then run:

    python build_thread.py --responses <folder with HADOOP-*.json>

Each record is rebuilt from the reference provenance:

- comment records: the comment body;
- subtask records: summary, a blank line, description, a blank line and
  "Status: <name>".

Every record is checked against the reference content SHA-256, and every
packet against benchmark/manifest.json, before it is written to
inputs/public/Thread/. Records whose upstream text has changed since the study
are reported and their packets are not written. Uses only the standard library
and never accesses the network.
"""
import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent


def record_text(issue, role, native_id):
    fields = issue["fields"]
    if role == "comment":
        comment_id = native_id.split("/")[2]
        for comment in (fields.get("comment") or {}).get("comments", []):
            if comment["id"] == comment_id:
                return comment["body"]
        raise KeyError(f"comment {native_id} not found")
    if role == "subtask":
        return (fields["summary"] + "\n\n" + (fields.get("description") or "")
                + "\n\nStatus: " + fields["status"]["name"])
    raise ValueError(f"unknown record role {role!r}")


def serialize(packet):
    text = json.dumps(packet, indent=2, ensure_ascii=False) + "\n"
    return text.replace("\n", "\r\n").encode("utf-8")


def load_responses(folder):
    responses = {}
    for path in sorted(Path(folder).glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and "key" in data and "fields" in data:
            responses[data["key"]] = data
    return responses


def build(package, responses_dir, check_only=False):
    issues = json.loads((package / "sources" / "hadoop-jira" / "issues.json").read_text(encoding="utf-8"))["issues"]
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    expected = {"/".join(f["parts"]): f["sha256"] for f in manifest["files"]}
    responses = load_responses(responses_dir)
    missing = [i for i in issues if i["key"] not in responses]
    if missing:
        return {"built": 0, "total": 0, "failed": [], "missing_issues": [
            {"key": i["key"], "rest_url": i["rest_url"], "save_as": i["save_as"]} for i in missing]}
    built, failed = 0, []
    ref_paths = sorted((package / "inputs" / "reference" / "Thread").glob("*.json"))
    out_dir = package / "inputs" / "public" / "Thread"
    for ref_path in ref_paths:
        reference = json.loads(ref_path.read_text(encoding="utf-8"))
        provenance = {p["id"]: p for p in reference["provenance"]}
        records, changed = [], []
        for ref in reference["records"]:
            prov = provenance[ref["id"]]
            try:
                text = record_text(responses[prov["native_id"].split("/")[0]], prov["role"], prov["native_id"])
            except (KeyError, ValueError) as err:
                changed.append(f"{ref['id']}: {err}")
                continue
            if sha256(text.encode("utf-8")).hexdigest() != ref["content_sha256"]:
                changed.append(f"{ref['id']}: upstream text of {prov['native_id']} has changed")
                continue
            records.append({"id": ref["id"], "format": "text", "text": text})
        rel = f"inputs/public/Thread/{ref_path.name}"
        if changed:
            failed.append({"task": reference["task_id"], "problems": changed})
            continue
        data = serialize({"task_id": reference["task_id"], "records": records})
        if sha256(data).hexdigest() != expected.get(rel):
            failed.append({"task": reference["task_id"], "problems": ["packet hash differs from manifest.json"]})
            continue
        if not check_only:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / ref_path.name).write_bytes(data)
        built += 1
    return {"built": built, "total": len(ref_paths), "failed": failed, "missing_issues": []}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--responses", type=Path, required=True, help="folder containing the downloaded HADOOP-*.json files")
    parser.add_argument("--package", type=Path, default=PACKAGE)
    parser.add_argument("--check-only", action="store_true", help="verify without writing packets")
    args = parser.parse_args(argv)
    result = build(args.package.resolve(), args.responses, args.check_only)
    if result["missing_issues"]:
        print(f"Missing {len(result['missing_issues'])} issue response(s). Download each rest_url and save it as shown:")
        for item in result["missing_issues"]:
            print(f"  {item['save_as']}  <-  {item['rest_url']}")
        return 2
    verb = "verified" if args.check_only else "built"
    print(f"Thread packets {verb}: {result['built']} of {result['total']}")
    for item in result["failed"]:
        print(f"  {item['task']}: " + "; ".join(item["problems"][:3]))
    return 0 if result["total"] and result["built"] == result["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
