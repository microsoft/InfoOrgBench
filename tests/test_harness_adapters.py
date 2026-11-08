# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import inspect
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

import infoorgbench_harness.adapters as adapters
from infoorgbench_harness.adapters import (PINS, _child_environment, build_codex_invocation, build_dsh_patch,
                                           codex_denied_roots, run_third_party)
from infoorgbench_harness.models.protocols import RESPONSES


class AdapterConfigurationTests(unittest.TestCase):
    def test_paper_harness_versions_are_frozen(self):
        self.assertEqual(PINS, {"codex": "0.162.1", "pi": "1.1.0",
                                "dsh": "0.2.1-alpha.1", "deepagents": "0.7.23"})

    def test_codex_invocation_disables_unrecorded_capabilities(self):
        invocation = build_codex_invocation("codex", Path("workspace"), Path("run"),
                                            "http://127.0.0.1:1234/v1", "gpt-6.1-sol", "medium")
        rendered = " ".join(invocation)
        for value in ('approval_policy="never"', 'web_search="disabled"',
                      "features.multi_agent=false", "features.memories=false",
                      'wire_api="responses"', "request_max_retries=0", "stream_max_retries=0"):
            self.assertIn(value, rendered)

    def test_codex_invocation_denies_evaluator_roots_and_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repo"
            for name in ("benchmark", "results"):
                (repository / name).mkdir(parents=True)
            workspace = Path(temporary) / "run" / "workspace"
            workspace.mkdir(parents=True)
            denied = codex_denied_roots(repository, workspace, home=Path(temporary) / "empty-home",
                                         appdata=Path(temporary) / "empty-appdata")
            invocation = build_codex_invocation("codex", workspace, Path(temporary) / "run",
                                                "http://127.0.0.1:1234/v1", "gpt-6.1-sol", "medium",
                                                windows_sandbox="mxc", read_denied_roots=denied)
        rendered = " ".join(invocation)
        self.assertEqual({path.name for path in denied}, {"benchmark", "results"})
        self.assertIn('windows.sandbox="mxc"', rendered)
        self.assertIn('default_permissions="task"', rendered)
        self.assertIn("permissions.task.network.enabled=false", rendered)
        self.assertIn('"deny"', rendered)
        self.assertNotIn("workspace-write", rendered)

    def test_codex_denied_roots_never_cover_the_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "benchmark").mkdir()
            workspace = repository / "results" / "run" / "workspace"
            workspace.mkdir(parents=True)
            denied = codex_denied_roots(repository, workspace, home=Path(temporary) / "empty-home",
                                         appdata=Path(temporary) / "empty-appdata")
        self.assertEqual([path.name for path in denied], ["benchmark"])

    def test_child_environment_is_strict_and_secret_free(self):
        source = {
            "PATH": "bin", "PATHEXT": ".EXE", "SYSTEMROOT": "system", "WINDIR": "windows",
            "COMSPEC": "cmd", "TEMP": "temp", "TMP": "tmp", "OS": "Windows_NT",
            "PROCESSOR_ARCHITECTURE": "AMD64", "NUMBER_OF_PROCESSORS": "8", "LANG": "en_US",
            "LC_ALL": "C", "HOME": "home", "USERPROFILE": "profile", "APPDATA": "appdata",
            "LOCALAPPDATA": "local", "AWS_SECRET_ACCESS_KEY": "secret", "DATABASE_URL": "secret",
            "COPILOT_GITHUB_TOKEN": "secret", "OPENAI_API_KEY": "secret", "ANTHROPIC_API_KEY": "secret",
        }
        env = _child_environment(source=source, include_user=True, extra={"CODEX_HOME": "isolated"})
        self.assertEqual(env["CODEX_HOME"], "isolated")
        self.assertEqual(env["PROCESSOR_ARCHITECTURE"], "AMD64")
        self.assertEqual(env["LC_ALL"], "C")
        for name in ("AWS_SECRET_ACCESS_KEY", "DATABASE_URL", "COPILOT_GITHUB_TOKEN",
                     "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            self.assertNotIn(name, env)

    def test_every_adapter_subprocess_uses_the_environment_wrapper(self):
        source = inspect.getsource(adapters)
        self.assertEqual(source.count("subprocess.run("), 1)
        self.assertNotIn("subprocess.Popen(", source)

    def test_codex_invocation_uses_gateway_token_environment(self):
        invocation = build_codex_invocation("codex", Path("workspace"), Path("run"),
                                            "http://127.0.0.1:1234/v1", "gpt-6.1-sol", "medium")
        rendered = " ".join(invocation)
        self.assertIn('env_key="INFOORGBENCH_GATEWAY_TOKEN"', rendered)
        self.assertIn("requires_openai_auth=true", rendered)

    def test_codex_denies_existing_credential_locations_and_extra_roots(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repo"
            workspace = root / "run" / "workspace"
            home = root / "home"
            appdata = root / "appdata"
            extra = root / "extra-secrets"
            for path in (repository / "benchmark", repository / "results", workspace,
                         home / ".ssh", home / ".aws", home / ".azure", home / ".config" / "gh",
                         home / ".copilot", home / ".docker", home / ".kube",
                         home / ".git-credentials", home / ".npmrc", home / ".netrc",
                         appdata / "GitHub CLI", extra):
                path.mkdir(parents=True) if path.suffix == "" else (path.parent.mkdir(parents=True, exist_ok=True), path.touch())
            denied = codex_denied_roots(repository, workspace, extra_roots=[extra], home=home, appdata=appdata)
        rendered = {path.name for path in denied}
        self.assertTrue({"benchmark", "results", ".ssh", ".aws", ".azure", "gh", ".copilot",
                         ".docker", ".kube", ".git-credentials", ".npmrc", ".netrc",
                         "GitHub CLI", "extra-secrets"} <= rendered)
        self.assertNotIn("npm-cache", rendered)

    def test_dsh_runs_in_a_worker_subprocess(self):
        source = inspect.getsource(adapters._run_dsh)
        self.assertIn("dsh_worker.py", source)
        self.assertNotIn("from deepseek_harness import", source)

    def test_native_workers_send_gateway_token_but_do_not_persist_it_in_config(self):
        package = ROOT / "harness" / "infoorgbench_harness"
        pi = (package / "pi_worker.mjs").read_text(encoding="utf-8")
        deep = (package / "deepagents_worker.py").read_text(encoding="utf-8")
        dsh = (package / "dsh_worker.py").read_text(encoding="utf-8")
        self.assertIn("process.env.INFOORGBENCH_GATEWAY_TOKEN", pi)
        self.assertIn('os.environ["INFOORGBENCH_GATEWAY_TOKEN"]', deep)
        self.assertIn("dict(os.environ)", dsh)
        self.assertNotIn("gateway.token", inspect.getsource(adapters._worker_config))

    def test_dsh_patch_disables_memory_telemetry_and_subagents(self):
        patch = build_dsh_patch(Path("workspace").resolve(), "http://127.0.0.1:1234/v1",
                                "gpt-6.1-sol", 128000, "medium")
        self.assertIn("agents: []", patch)
        self.assertIn("mode: workspace-write", patch)
        self.assertIn("telemetry", patch)
        self.assertIn("memory", patch)
        self.assertIn("maxRetries: 0", patch)

    def test_native_failure_still_returns_independent_capture(self):
        class UnusedBackend:
            protocol = RESPONSES

        packet = {"task_id": "synthetic", "records": [{"id": "F001", "format": "text", "text": "one"}]}
        settings = {"max_output_tokens": 100, "reasoning_effort": None}
        with tempfile.TemporaryDirectory() as temporary, patch(
                "infoorgbench_harness.adapters._run_codex", side_effect=RuntimeError("failed")):
            result = run_third_party(packet, harness="codex", family="Recap", model="m",
                                     backend=UnusedBackend(), settings=settings,
                                     run_root=Path(temporary) / "run")
        self.assertEqual(result["status"], "failed:RuntimeError")
        self.assertTrue(result["inventory_preserved"])
        self.assertEqual(result["assignments"], [{"id": "F001", "path": ["inbox"]}])


if __name__ == "__main__":
    unittest.main()
