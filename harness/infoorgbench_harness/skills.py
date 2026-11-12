# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Optional Agent Skills for the Deep Agents harness and pinned community-skill retrieval."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

SKILL_MODES = ("available", "pinned")
SKILLS_SOURCE = "/skills/"
MAX_SKILL_FILE_BYTES = 10 * 1024 * 1024
_FRONTMATTER = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|\Z)", re.DOTALL)
_DIRECTORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def skill_name(text):
    """Return the frontmatter `name` of a SKILL.md, as Deep Agents reads it."""
    match = _FRONTMATTER.match(text)
    if not match:
        raise ValueError("SKILL.md has no YAML frontmatter")
    for line in match.group(1).splitlines():
        found = re.match(r"name:\s*(.+?)\s*$", line)
        if found:
            value = found.group(1)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            if value.strip():
                return value.strip()
    raise ValueError("SKILL.md frontmatter has no name")


def load_skills(paths, mode):
    """Load skill directories, each containing a SKILL.md, for one run condition."""
    if mode not in SKILL_MODES:
        raise ValueError("Unknown skill mode: " + str(mode))
    rows = []
    for value in paths:
        directory = Path(value).resolve()
        if not (directory / "SKILL.md").is_file():
            raise FileNotFoundError("Skill directory has no SKILL.md: " + str(value))
        if not _DIRECTORY.fullmatch(directory.name):
            raise ValueError("Skill directory name must be a plain name: " + directory.name)
        files = {}
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            data = path.read_bytes()
            if len(data) > MAX_SKILL_FILE_BYTES:
                raise ValueError("Skill file exceeds 10 MB: " + path.name)
            files[path.relative_to(directory).as_posix()] = data.decode("utf-8")
        rows.append({"directory": directory.name, "name": skill_name(files["SKILL.md"]),
                     "sha256": hashlib.sha256((directory / "SKILL.md").read_bytes()).hexdigest(),
                     "files": files})
    directories = [row["directory"] for row in rows]
    if len(set(directories)) != len(directories):
        raise ValueError("Skill directory names must be distinct within one run")
    return {"mode": mode, "skills": rows}


def worker_config(bundle):
    """Files and pinned names that the Deep Agents worker seeds into graph state."""
    return {"mode": bundle["mode"], "names": [row["name"] for row in bundle["skills"]],
            "files": {SKILLS_SOURCE + row["directory"] + "/" + relative: text
                      for row in bundle["skills"] for relative, text in row["files"].items()}}


def receipt_block(bundle):
    """Content-free description of the skill condition."""
    return {"mode": bundle["mode"],
            "skills": [{"directory": row["directory"], "name": row["name"], "sha256": row["sha256"]}
                       for row in bundle["skills"]]}


def install_codex_skills(bundle, codex_home):
    """Install skills where Codex lists them and return the text pinned mode appends to the prompt.

    Codex reads user skills from ``$CODEX_HOME/skills``. Its ``$name`` mention cannot invoke a skill
    whose name is not a plain identifier, so pinned mode appends each SKILL.md body in the same
    ``<skill>`` block that Deep Agents uses for a pinned skill.
    """
    blocks = []
    for row in bundle["skills"]:
        directory = Path(codex_home) / "skills" / row["directory"]
        for relative, text in row["files"].items():
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode("utf-8"))
        if bundle["mode"] == "pinned":
            match = _FRONTMATTER.match(row["files"]["SKILL.md"])
            body = (row["files"]["SKILL.md"][match.end():] if match else row["files"]["SKILL.md"]).rstrip()
            blocks.append('<skill name="{}" path="{}">\n{}\n</skill>'.format(
                html.escape(row["name"], quote=True), html.escape(str(directory / "SKILL.md"), quote=True), body))
    return "\n\n".join(blocks)


def fetch_skills(manifest_path, destination, *, opener=urlopen):
    """Download each manifest skill at its pinned commit and verify its SHA-256."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    destination = Path(destination)
    written = []
    for row in manifest["skills"] + manifest.get("controls", []):
        if not re.fullmatch(r"[0-9a-f]{40}", row["commit"]):
            raise ValueError("Skill commits must be full SHA-1 hashes: " + row["id"])
        url = "https://raw.githubusercontent.com/{}/{}/{}".format(row["repository"], row["commit"], row["path"])
        with opener(Request(url, headers={"User-Agent": "infoorgbench-harness"}), timeout=60) as response:
            data = response.read()
        digest = hashlib.sha256(data).hexdigest()
        if digest != row["sha256"]:
            raise ValueError("SHA-256 mismatch for skill {}: {}".format(row["id"], digest))
        target = destination / row["id"] / row["directory"] / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written.append(str(target.parent))
    return written
