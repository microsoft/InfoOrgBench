# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Run one pinned DSH episode in a credential-isolated child process."""

import json
import os
from pathlib import Path
import sys


def main():
    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    source = Path(config["source"]).resolve()
    sys.path.insert(0, str(source / "python" / "sdk" / "src"))
    from deepseek_harness import DeepSeekHarness

    child_env = dict(os.environ)
    with DeepSeekHarness(
        provider="infoorgbench-gateway",
        model=config["model"],
        reasoning_effort=config["reasoning_effort"],
        max_tokens=config["max_tokens"],
        cwd=config["workspace"],
        runtime_cwd=config["workspace"],
        dsh_home=child_env["DSH_HOME"],
        profile="sdk-minimal",
        patches=(config["patch"],),
        env=child_env,
        initialize_timeout_seconds=120,
        request_timeout_seconds=config["request_timeout_seconds"],
        shutdown_timeout_seconds=5,
        _launch_args=tuple(config["launch_args"]),
    ) as harness:
        result = harness.run(config["prompt"], session_id="infoorgbench-task")
    Path(config["result"]).write_text(json.dumps({
        "final": getattr(result, "final_response", None) or "",
        "finish_reason": getattr(result, "finish_reason", None),
    }, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
