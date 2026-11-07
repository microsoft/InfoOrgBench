# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Release gate for the InfoOrgBench repository.

Default (staging) mode fails when a file is not owned by a manifest
component, when required policy files are missing, or when text looks
internal or secret. Components whose approvals are pending are listed but
allowed, because the staging repository is private.

``--channel public_github`` or ``--channel anonymous_review`` additionally
requires the channel decision and every approval of every present component,
each with a reference, before content leaves Microsoft.

Private terms such as personal aliases belong in an untracked
``.release-denylist`` file (one term per line) so they never enter Git.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    "NOTICE.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "SUPPORT.md",
    "release/manifest.json",
)
README_REQUIRED_PHRASES = (
    "cla.opensource.microsoft.com",
    "Microsoft Open Source Code of Conduct",
    "## Trademarks",
)
KNOWN_LICENSES = {"MIT", "CC-BY-4.0", "Apache-2.0", "PENDING-CELA"}
PENDING_LICENSE = "PENDING-CELA"
SATISFIED = {"approved", "not_applicable"}
ARCHIVE_SUFFIXES = (".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar")
MAX_FILE_BYTES = 25 * 1024 * 1024
ALLOWED_EMAILS = {"opencode@microsoft.com"}
# Upstream source text is distributed unchanged, so only secret-like patterns and
# private terms are checked there; internal-path rules apply to our own files.
UPSTREAM_TEXT = ("benchmark/inputs/*",)
SECRET_LABELS = {"GitHub token", "API key", "AWS access key", "private key"}

LEAK_PATTERNS = (
    ("Windows user path", re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+", re.I)),
    ("macOS or Linux home path", re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/")),
    ("OneDrive path", re.compile(r"OneDrive[ ]-[ ]", re.I)),
    ("Microsoft email address", re.compile(r"[\w.+-]+@microsoft\.com", re.I)),
    ("internal host", re.compile(r"\b(?:eng\.ms|[\w-]+\.sharepoint\.com|dev\.azure\.com|[\w-]+\.visualstudio\.com|corp\.microsoft\.com)\b", re.I)),
    ("internal research ID", re.compile(r"\b[A-Z]{3,}-\d{3}-\d{8}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("internal marker", re.compile(r"\b(?:INTERNAL[ _-]ONLY|CONFIDENTIA[L])\b")),
)


@dataclass(frozen=True)
class Component:
    id: str
    patterns: tuple[str, ...]
    license: str
    requires: tuple[str, ...]


def load_manifest(root: Path) -> dict:
    return json.loads((root / "release" / "manifest.json").read_text(encoding="utf-8"))


def components_from(manifest: dict) -> list[Component]:
    return [
        Component(c["id"], tuple(c["patterns"]), c["license"], tuple(c.get("requires", ())))
        for c in manifest["components"]
    ]


def list_files(root: Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            check=True, capture_output=True,
        ).stdout.decode("utf-8")
        files = [f for f in out.split("\0") if f]
        if files:
            return sorted(f for f in files if (root / f).is_file())
    except (OSError, subprocess.CalledProcessError):
        pass
    return sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts and "__pycache__" not in p.parts
    )


def owner_of(path: str, components: list[Component]) -> Component | None:
    for comp in components:
        if any(fnmatch.fnmatchcase(path, pattern) for pattern in comp.patterns):
            return comp
    return None


def pending(comp: Component, approvals: dict) -> list[str]:
    return [a for a in comp.requires if approvals.get(a, {}).get("status") not in SATISFIED]


def load_denylist(root: Path) -> list[str]:
    path = root / ".release-denylist"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    return [t.strip() for t in lines if t.strip() and not t.startswith("#")]


def scan_text(path: str, text: str, denylist: list[str], upstream: bool = False) -> list[str]:
    problems = []
    patterns = [(l, p) for l, p in LEAK_PATTERNS if not upstream or l in SECRET_LABELS]
    for lineno, line in enumerate(text.splitlines(), 1):
        for label, pattern in patterns:
            for match in pattern.finditer(line):
                if label == "Microsoft email address" and match.group(0).lower() in ALLOWED_EMAILS:
                    continue
                problems.append(f"{path}:{lineno}: {label}: {match.group(0)!r}")
        lowered = line.lower()
        for term in denylist:
            if term.lower() in lowered:
                problems.append(f"{path}:{lineno}: denylisted term")
    return problems


def check(root: Path, channel: str | None = None, report: dict | None = None) -> list[str]:
    problems: list[str] = []
    for required in REQUIRED_FILES:
        if not (root / required).is_file():
            problems.append(f"missing required file: {required}")
    if problems:
        return problems

    manifest = load_manifest(root)
    approvals = manifest.get("approvals", {})
    proposed = root / "harness" / "MANIFEST-COMPONENTS.json"
    proposed_present = proposed.is_file()
    if proposed_present:
        additions = json.loads(proposed.read_text(encoding="utf-8")).get("proposed_component_entries", [])
        manifest = {**manifest, "components": [*manifest["components"], *additions]}
    components = components_from(manifest)
    for comp in components:
        if comp.license not in KNOWN_LICENSES:
            problems.append(f"component {comp.id}: unknown licence {comp.license!r}")
        for name in comp.requires:
            if name not in approvals:
                problems.append(f"component {comp.id}: undefined approval {name!r}")

    readme = (root / "README.md").read_text(encoding="utf-8")
    for phrase in README_REQUIRED_PHRASES:
        if phrase not in readme:
            problems.append(f"README.md lacks required text: {phrase!r}")

    denylist = load_denylist(root)
    counts: dict[str, int] = {}
    for path in list_files(root):
        if path == ".release-denylist":
            continue
        full = root / path
        banned = next((f for f in manifest.get("forbidden", []) if any(fnmatch.fnmatchcase(path, pat) for pat in f["patterns"])), None)
        if banned:
            problems.append(f"{path}: must not be committed: {banned['reason']}")
            continue
        comp = owner_of(path, components)
        if comp is None:
            problems.append(f"{path}: not covered by any manifest component")
            continue
        counts[comp.id] = counts.get(comp.id, 0) + 1
        if path.lower().endswith(ARCHIVE_SUFFIXES):
            problems.append(f"{path}: archives are not allowed")
        if full.stat().st_size > MAX_FILE_BYTES:
            problems.append(f"{path}: larger than {MAX_FILE_BYTES} bytes")
        try:
            text = full.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        upstream = any(fnmatch.fnmatchcase(path, p) for p in UPSTREAM_TEXT)
        problems.extend(scan_text(path, text, denylist, upstream))

    if report is not None:
        report.update({c.id: {"files": counts.get(c.id, 0), "pending": pending(c, approvals)} for c in components})

    if channel:
        if proposed_present:
            problems.append("proposed component entries must be merged into release/manifest.json before channel release")
        info = manifest.get("channels", {}).get(channel)
        if info is None:
            problems.append(f"unknown channel {channel!r}")
        elif info.get("approved") is not True:
            problems.append(f"channel {channel} is not approved")
        for comp in components:
            if not counts.get(comp.id):
                continue
            if comp.license == PENDING_LICENSE:
                problems.append(f"component {comp.id}: licence not yet decided in the dataset review")
            for name in comp.requires:
                info = approvals.get(name, {})
                if info.get("status") not in SATISFIED:
                    problems.append(f"component {comp.id}: approval {name} is {info.get('status')!r}")
                elif info.get("status") == "approved" and not info.get("reference"):
                    problems.append(f"component {comp.id}: approval {name} has no reference")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--channel", choices=["public_github", "anonymous_review"],
                        help="also require every approval for this release channel")
    args = parser.parse_args(argv)
    report: dict = {}
    problems = check(args.root.resolve(), channel=args.channel, report=report)
    mode = args.channel or "staging"
    for cid, info in report.items():
        state = "pending: " + ", ".join(info["pending"]) if info["pending"] else "approved"
        print(f"  {cid:<28} {info['files']:>5} files  {state}")
    if problems:
        print(f"Release gate ({mode}): FAIL, {len(problems)} problem(s)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"Release gate ({mode}): PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())