# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Build and verify the anonymized review copy of InfoOrgBench.

The copy is what reviewers see through an anonymous.4open.science mirror of
the ``anonymous-review`` branch, or as the two supplementary archives that
ACL Rolling Review accepts (software and data in separate .zip files).

Checks, all of which must pass:
1. No Anonymous GitHub replacement term occurs in any file, so the service
   cannot alter data and break the SHA-256 bindings.
2. No identity marker or private term from the untracked .release-denylist
   occurs outside upstream source text. Upstream text may
   mention Microsoft (for example Windows support in Kubernetes proposals).
3. The offline replay passes inside the anonymized copy.

Building does not upload or publish anything.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_release import list_files, load_denylist  # noqa: E402

UPSTREAM_ALLOWED = {"Microsoft", "Redmond"}
ZIP_TIME = (2026, 1, 1, 0, 0, 0)
COPYRIGHT = b"Copyright (c) Microsoft Corporation."
ANON_COPYRIGHT = b"Copyright (c) The InfoOrgBench authors."
HEADER_PREFIXES = {".py": b"# ", ".toml": b"# ", ".mjs": b"// ", ".js": b"// "}
PACKAGE_AUTHOR = b'authors = [{name = "Microsoft Corporation"}]'
ANON_PACKAGE_AUTHOR = b'authors = [{name = "The InfoOrgBench authors"}]'


def transform(dest: str, data: bytes) -> bytes:
    """Neutralize the Microsoft copyright header and package author for the review copy."""
    prefix = HEADER_PREFIXES.get(Path(dest).suffix)
    if prefix is not None:
        data = data.replace(prefix + COPYRIGHT, prefix + ANON_COPYRIGHT, 1)
    if dest.endswith("pyproject.toml"):
        data = data.replace(PACKAGE_AUTHOR, ANON_PACKAGE_AUTHOR, 1)
    return data


def matches(path: str, patterns) -> bool:
    return any(fnmatch.fnmatchcase(path, p) for p in patterns)


def plan(root: Path, config: dict) -> dict[str, Path]:
    tree = {dest: root / src for dest, src in config["replace"].items()}
    for path in list_files(root):
        if path not in tree and matches(path, config["include"]):
            tree[path] = root / path
    return dict(sorted(tree.items()))


def verify(tree: dict[str, Path], config: dict) -> list[str]:
    problems = []
    terms = [t.lower() for t in config["anonymous_github_terms"]]
    identity = [(p, re.compile(p)) for p in config["identity_patterns"]]
    identity += [("private term", re.compile(re.escape(t), re.I)) for t in config.get("private_terms", [])]
    for dest, src in tree.items():
        try:
            text = transform(dest, src.read_bytes()).decode("utf-8")
        except UnicodeDecodeError:
            continue
        lowered = text.lower()
        for term in terms:
            if term in lowered:
                problems.append(f"{dest}: contains anonymization term {term!r}; the mirror would alter it")
        upstream = matches(dest, config["upstream_text_patterns"])
        for source, pattern in identity:
            if upstream and source in UPSTREAM_ALLOWED:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    problems.append(f"{dest}:{lineno}: identity marker {source!r}")
    return problems


def materialize(tree: dict[str, Path], out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    rewritten = set()
    for dest, src in tree.items():
        target = out / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()
        new = transform(dest, data)
        target.write_bytes(new)
        if new != data:
            rewritten.add(dest)
    manifest = out / "benchmark" / "manifest.json"
    if rewritten and manifest.is_file():
        # Rewritten headers change file bytes, so the replay manifest must be rebound.
        m = json.loads(manifest.read_text(encoding="utf-8"))
        for entry in m["files"]:
            if "benchmark/" + "/".join(entry["parts"]) in rewritten:
                entry["sha256"] = hashlib.sha256((out / "benchmark").joinpath(*entry["parts"]).read_bytes()).hexdigest()
        manifest.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")


def replay(out: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        receipt = Path(tmp) / "receipt.json"
        subprocess.run([sys.executable, "-I", "-S", "-B", "replay.py", "--receipt", str(receipt)],
                       cwd=out / "benchmark", check=True, capture_output=True)
        return json.loads(receipt.read_text(encoding="utf-8"))


def write_zip(out: Path, files: list[str], target: Path) -> str:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            info = zipfile.ZipInfo("InfoOrgBench/" + rel, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, (out / rel).read_bytes())
    return hashlib.sha256(target.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    root_default = Path(__file__).resolve().parents[1]
    parser.add_argument("--root", type=Path, default=root_default)
    parser.add_argument("--out", type=Path, default=root_default.parent / "InfoOrgBench-anonymous-review")
    parser.add_argument("--archives", action="store_true", help="also write ARR supplementary archives")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    config = json.loads((root / "release" / "anonymization.json").read_text(encoding="utf-8"))
    config["private_terms"] = load_denylist(root)
    tree = plan(root, config)
    problems = verify(tree, config)
    if problems:
        print(f"Anonymized copy: FAIL, {len(problems)} problem(s)")
        for p in problems[:50]:
            print(f"  - {p}")
        return 1

    out = args.out.resolve()
    materialize(tree, out / "tree")
    result = replay(out / "tree")
    summary = {"files": len(tree), "replay": {k: result[k] for k in ("passed", "outputs_replayed", "tasks", "lambda_checks")}}

    if args.archives:
        names = list(tree)
        software = [n for n in names if matches(n, config["software_archive"])]
        data = [n for n in names if matches(n, config["data_archive"])]
        missing = sorted(set(names) - set(software) - set(data))
        if missing:
            print("Files in neither archive:", missing)
            return 1
        summary["archives"] = {}
        for label, files in (("software", software), ("data", data)):
            target = out / f"InfoOrgBench-{label}.zip"
            digest = write_zip(out / "tree", files, target)
            summary["archives"][label] = {"file": target.name, "files": len(files),
                                          "bytes": target.stat().st_size, "sha256": digest}

    (out / "build-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("Anonymized copy: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
