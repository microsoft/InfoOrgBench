# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Render the versioned, harness-neutral organization prompt."""

from hashlib import sha256
import json
from pathlib import Path
import re
from string import Template


ROOT = Path(__file__).resolve().parents[1]
PROMPT_ROOT = Path(__file__).with_name("prompts") / "v2"
PROTOCOL = PROMPT_ROOT / "protocol.v2.md"
PROTOCOL_FILES = {
    "v2": PROTOCOL,
    "v2.1": PROMPT_ROOT / "protocol.v2.1.md",
    "v2.2": PROMPT_ROOT / "protocol.v2.2.md",
}
FAMILY_FILES = {
    "design": PROMPT_ROOT / "family-design.v1.md",
    "design-sections": PROMPT_ROOT / "family-design-sections.v1.md",
    "issue": PROMPT_ROOT / "family-issue.v1.md",
    "meeting": PROMPT_ROOT / "family-meeting.v1.md",
    "meeting-unanchored": PROMPT_ROOT / "family-meeting-unanchored.v1.md",
    "summary": PROMPT_ROOT / "family-summary.v1.md",
}
FAMILY_FOR_TRACK = {"native": "design", "meeting": "meeting"}
PLACEHOLDER_WORKSPACE = "{WS}"
PLACEHOLDER_CHECKER = "{CHECKER}"
FORBIDDEN = [
    r"(?i)benchmark",
    r"(?i)orgbench",
    r"(?i)\bscor(?:e|es|ed|ing)\b",
    r"(?i)evaluat",
    r"(?i)grader",
    r"(?i)\breference\b",
    r"(?i)ground[- ]truth",
    r"(?i)\bgold\b",
    r"(?i)answer key",
    r"\bAMI\b",
    r"(?i)kubernetes",
    r"\bKEPs?\b",
    r"\bSIGs?\b",
    r"(?i)\bcodex\b",
    r"(?i)deepseek",
    r"(?i)\bdsh\b",
    r"(?i)openai",
    r"(?i)\bgpt\b",
    r"(?i)claude",
    r"(?i)gemini",
    r"(?i)\b(?:dev|test)-\d+\b",
]


def _text(path):
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")


def family_for_track(track):
    try:
        return FAMILY_FOR_TRACK[track]
    except KeyError as error:
        raise ValueError("No prompt family is defined for track: " + str(track)) from error


def _sha(text):
    return sha256(text.encode("utf-8")).hexdigest()


def _canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _natural_key(text):
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", text)]


def _load_family(name):
    try:
        path = FAMILY_FILES[name]
    except KeyError as error:
        raise ValueError("Unknown prompt family: " + str(name)) from error
    raw = _text(path)
    header, block = raw.split("\n---\n", 1)
    metadata = dict(line.split(": ", 1) for line in header.strip().splitlines())
    metadata["levels"] = [level.strip() for level in metadata["levels"].split("|")]
    if (metadata.get("family") != name or metadata.get("anchors") not in {"none", "required"}
            or not 1 <= len(metadata["levels"]) <= 4):
        raise ValueError("Prompt family metadata is invalid: " + name)
    return metadata, block.strip(), raw


def _load_protocol(version):
    try:
        path = PROTOCOL_FILES[version]
    except KeyError as error:
        raise ValueError("Unknown prompt protocol version: " + str(version)) from error
    return _text(path)


def _folder_segment(value):
    return (isinstance(value, str) and bool(value.strip()) and value not in {".", ".."}
            and "/" not in value and "\\" not in value and not value.endswith(".txt")
            and re.fullmatch(r"[A-Z]\d+", value) is None)


def _instance(packet, family):
    records = packet.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("A rendered prompt needs at least one public record")
    if family == "meeting":
        transcripts = [row for row in records if row.get("format") == "transcript"]
        if not transcripts:
            raise ValueError("Meeting prompts require transcript anchors")
        folders = []
        seen = set()
        for row in transcripts:
            anchor = row.get("anchor")
            if (not isinstance(anchor, dict) or set(anchor) != {"project", "meeting"}
                    or not _folder_segment(anchor["project"]) or not _folder_segment(anchor["meeting"])
                    or not isinstance(row.get("id"), str)):
                raise ValueError("Meeting transcript anchor is invalid")
            label = anchor["project"] + "/" + anchor["meeting"]
            if label.casefold() in seen:
                raise ValueError("Meeting prompt has a duplicate supplied folder")
            seen.add(label.casefold())
            folders.append((label, row["id"]))
        folders.sort(key=lambda row: _natural_key(row[0]))
        instance = ["Meeting folders (the only supplied project and meeting information):"]
        instance.extend(f"- `{label}`: transcript {record_id}" for label, record_id in folders)
        instance.append(
            f"There are {len(records)} records: {len(records) - len(transcripts)} notes "
            f"and {len(transcripts)} transcripts."
        )
    else:
        if any(row.get("anchor") is not None for row in records):
            raise ValueError("Only meeting prompts accept public folder anchors")
        instance = [f"There are {len(records)} records. No folder names are supplied."]
    return f"- All {len(records)} records start as `inbox/<ID>.txt`.", "\n".join(instance)


def _render(packet, family, workspace, checker, protocol_version):
    metadata, family_block, family_raw = _load_family(family)
    protocol_raw = _load_protocol(protocol_version)
    inventory_lines, instance_block = _instance(packet, family)
    levels = metadata["levels"]
    values = {
        "workspace": workspace,
        "checker_command": checker,
        "inventory_lines": inventory_lines,
        "path_pattern": "/".join(f"<{level}>" for level in levels) + "/<ID>.txt",
        "leaf_level": levels[-1],
        "path_json": json.dumps([f"<{level}>" for level in levels]),
        "family_block": family_block,
        "instance_block": instance_block,
    }
    prompt = Template(protocol_raw).substitute(values)
    problems = []
    if "${" in prompt:
        problems.append("unfilled slot")
    for pattern in FORBIDDEN:
        match = re.search(pattern, prompt)
        if match:
            problems.append("forbidden term " + repr(match.group(0)))
    return prompt, metadata, protocol_raw, family_raw, problems


def render_packet(packet, family, workspace, checker, *, protocol_version="v2"):
    """Render one main-condition prompt and its provenance manifest."""
    prompt, metadata, protocol_raw, family_raw, problems = _render(
        packet, family, workspace, checker, protocol_version
    )
    canonical, _, _, _, canonical_problems = _render(
        packet, family, PLACEHOLDER_WORKSPACE, PLACEHOLDER_CHECKER, protocol_version
    )
    problems.extend(problem for problem in canonical_problems if problem not in problems)
    if problems:
        raise ValueError("Prompt lint failed: " + "; ".join(problems))
    return prompt, {
        "prompt_version": protocol_version,
        "family": family,
        "family_version": metadata["version"],
        "family_status": metadata["status"],
        "condition": {
            "evidence": "full",
            "anchor_mode": "inbox",
            "arrival_batches": 1,
        },
        "hashes": {
            "packet_content_sha256": sha256(_canonical_bytes(packet)).hexdigest(),
            "protocol_sha256": _sha(protocol_raw),
            "family_sha256": _sha(family_raw),
            "rendered_sha256": _sha(prompt),
            "canonical_sha256": _sha(canonical),
        },
        "size": {
            "prompt_chars": len(prompt),
            "prompt_tokens_estimate": len(prompt) // 4,
            "records": len(packet["records"]),
        },
        "lint": "clean",
    }
