# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Content-free public run receipts."""

from __future__ import annotations

from datetime import datetime, timezone

_ALLOWED_USAGE = frozenset({
    "input_tokens", "output_tokens", "total_tokens", "prompt_tokens", "completion_tokens",
    "cache_creation_input_tokens", "cache_read_input_tokens", "cached_tokens", "reasoning_tokens",
    "input_tokens_details", "output_tokens_details", "prompt_tokens_details", "completion_tokens_details",
})


def _usage_value(value):
    if isinstance(value, dict):
        return {key: filtered for key, item in value.items()
                if (filtered := _usage_value(item)) is not None}
    return value if type(value) in (int, float) and value >= 0 else None


def make_receipt(*, harness, model, backend, family, task_id, status, settings, hashes, usage, versions):
    """Build a receipt containing settings and provider counts, never task or transport content."""
    return {
        "schema_version": 1,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "harness": harness,
        "model": model,
        "backend": backend,
        "family": family,
        "task_id": task_id,
        "status": status,
        "settings": dict(settings),
        "hashes": dict(hashes),
        "versions": dict(versions),
        "provider_reported_usage": {key: filtered for key, value in (usage or {}).items()
                                    if key in _ALLOWED_USAGE and (filtered := _usage_value(value)) is not None},
    }
