# Copyright (c) The InfoOrgBench authors.
# Licensed under the MIT License.
"""Five capability-scoped record tools used by Pi and Deep Agents."""

from copy import deepcopy

from .workspace import TOOLS

RECORD_NAMES = dict(zip(
    ("record_list", "record_read", "record_search", "record_move", "record_inventory"),
    (row["name"] for row in TOOLS),
))

ADAPTER_INSTRUCTIONS = (
    "Operate only the five bounded record tools. They expose public records, not other host files. "
    "record_read returns complete 8000-character pages with a next_offset; follow all pages. "
    "record_move performs actual byte-preserving moves. record_inventory is the requested checker. "
    "No shell, arbitrary filesystem, network, hidden reference or quality feedback is available. "
    "Do not ask questions. Finish with the requested JSON after checking the actual inventory."
)


def record_tool_schemas():
    rows = deepcopy(TOOLS)
    for row, name in zip(rows, RECORD_NAMES):
        row["name"] = name
        for public, react_name in RECORD_NAMES.items():
            row["description"] = row["description"].replace(react_name, public)
    rows[1]["parameters"]["properties"]["length"]["maximum"] = 8000
    rows[1]["parameters"]["properties"]["file_id"]["description"] = (
        "Exact opaque record ID, such as F001, without .txt or a path.")
    return rows


def operate_record_tool(workspace, name, arguments):
    if name not in RECORD_NAMES:
        raise ValueError("Tool is outside the record capability allowlist")
    if name == "record_read" and not 1 <= arguments.get("length", 0) <= 8000:
        raise ValueError("Read pages must contain 1 to 8000 characters")
    return workspace.operate(RECORD_NAMES[name], arguments)
