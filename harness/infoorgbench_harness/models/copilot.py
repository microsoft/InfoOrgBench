# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""GitHub Copilot provider-endpoint backend with in-memory endpoint metadata."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request

from .http import (TransportError, _join_url, _open_no_redirect, _read_bounded,
                   _upstream_request_body, _validate_model_base_url)
from .protocols import ANTHROPIC, CHAT, RESPONSES


def _helper_environment(token_env, source=None):
    source = os.environ if source is None else source
    exact = {"PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
             "TEMP", "TMP", "OS", "NUMBER_OF_PROCESSORS", "HOME", "USERPROFILE",
             "APPDATA", "LOCALAPPDATA", "INFOORGBENCH_COPILOT_RUNTIME",
             "INFOORGBENCH_COPILOT_ALLOW_UNVERIFIED", "NPM_CONFIG_PREFIX"}
    return {key: value for key, value in source.items()
            if key != token_env and (key.upper() in exact or key.upper().startswith("PROCESSOR_")
            or key.upper() == "LANG" or key.upper().startswith("LC_"))}


class _EndpointPipe:
    def __init__(self, command, *, token_env, working_directory):
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", token_env):
            raise ValueError("Copilot token environment name is invalid")
        token = os.environ.get(token_env)
        self.process = subprocess.Popen([str(part) for part in command], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
                                        env=_helper_environment(token_env))
        try:
            self.rpc({"command": "init", "gitHubToken": token,
                      "workingDirectory": str(Path(working_directory).resolve())})
        except Exception:
            self.process.kill()
            self.process.wait(timeout=5)
            raise

    def rpc(self, command):
        if self.process.poll() is not None or self.process.stdin is None or self.process.stdout is None:
            raise TransportError("copilot_endpoint_helper_stopped")
        try:
            self.process.stdin.write(json.dumps(command, separators=(",", ":")) + "\n")
            self.process.stdin.flush()
            line = self.process.stdout.readline()
            value = json.loads(line)
        except (BrokenPipeError, OSError, json.JSONDecodeError):
            raise TransportError("copilot_endpoint_helper_failed") from None
        if not isinstance(value, dict) or value.get("ok") is not True:
            code = value.get("code") if isinstance(value, dict) else None
            known = {"runtime_missing", "runtime_version_mismatch", "authentication_required",
                     "already_initialized", "invalid_command", "sdk_operation_failed"}
            raise TransportError("copilot_endpoint_helper_failed" + (f":{code}" if code in known else ""))
        return value

    def close(self):
        if self.process.poll() is None:
            try:
                self.rpc({"command": "close"})
            except TransportError:
                pass
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        if self.process.stdin is not None:
            self.process.stdin.close()
        if self.process.stdout is not None:
            self.process.stdout.close()


def _set_header(headers, key, value):
    for present in list(headers):
        if present.lower() == key.lower():
            del headers[present]
    headers[key] = value


def _protocol(endpoint):
    if endpoint.get("type") == "anthropic":
        return ANTHROPIC
    if endpoint.get("type") in {"openai", "azure"} and endpoint.get("wireApi") == "responses":
        return RESPONSES
    if endpoint.get("type") in {"openai", "azure"} and endpoint.get("wireApi") in {"completions", "chat"}:
        return CHAT
    raise TransportError("copilot_unsupported_endpoint")


def _expired(endpoint):
    value = endpoint.get("sessionToken", {}).get("expiresAt")
    if not value:
        return False
    try:
        expiry = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        raise TransportError("copilot_invalid_expiry") from None
    return (expiry - datetime.now(timezone.utc)).total_seconds() <= 30


class CopilotBackend:
    """Direct model HTTP using metadata supplied by the opt-in Copilot SDK endpoint API."""

    def __init__(self, *, helper_command=None, token_env="COPILOT_GITHUB_TOKEN", working_directory=".",
                 timeout_seconds=2400):
        if helper_command is None:
            candidates = [Path(__file__).resolve().parents[2] / "copilot" / "endpoint.mjs",
                          Path(__file__).resolve().parents[1] / "copilot" / "endpoint.mjs",
                          Path(sys.prefix) / "infoorgbench_harness" / "copilot" / "endpoint.mjs"]
            helper = next((path for path in candidates if path.is_file()), None)
            if helper is None:
                raise TransportError("copilot_endpoint_helper_missing")
            helper_command = [os.environ.get("INFOORGBENCH_NODE", "node"), str(helper)]
        Path(working_directory).mkdir(parents=True, exist_ok=True)
        self.name = "copilot"
        self.protocol = RESPONSES
        self.timeout_seconds = timeout_seconds
        self.pipe = _EndpointPipe(helper_command, token_env=token_env, working_directory=working_directory)
        self.endpoint = None
        self.model = None
        self.refreshes = 0
        self.token_env = token_env

    def public_metadata(self):
        return {"backend": "copilot", "protocol": self.protocol,
                "token_environment": self.token_env, "credential_refreshes": self.refreshes}

    def _endpoint(self, model, force=False):
        if force or self.endpoint is None or self.model != model or _expired(self.endpoint):
            value = self.pipe.rpc({"command": "endpoint", "model": model})
            endpoint = value.get("endpoint")
            if not isinstance(endpoint, dict) or not isinstance(endpoint.get("baseUrl"), str):
                raise TransportError("copilot_endpoint_helper_failed")
            try:
                _validate_model_base_url(endpoint["baseUrl"])
            except ValueError:
                raise TransportError("copilot_unsafe_endpoint") from None
            self.endpoint, self.model = endpoint, model
            self.protocol = _protocol(endpoint)
            self.refreshes += 1
        return self.endpoint

    def _headers(self, endpoint):
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream, application/json"}
        api_key = endpoint.get("apiKey")
        if api_key:
            if self.protocol == ANTHROPIC:
                _set_header(headers, "X-Api-Key", api_key)
                _set_header(headers, "Anthropic-Version", "2023-06-01")
            else:
                _set_header(headers, "Authorization", "Bearer " + api_key)
        for key, value in (endpoint.get("headers") or {}).items():
            if value is not None:
                _set_header(headers, key, str(value))
        token = endpoint.get("sessionToken")
        if token:
            if not isinstance(token.get("header"), str) or not isinstance(token.get("token"), str):
                raise TransportError("copilot_endpoint_helper_failed")
            _set_header(headers, token["header"], token["token"])
        return headers

    def _send(self, source_protocol, body, endpoint):
        protocol = _protocol(endpoint)
        self.protocol = protocol
        upstream = _upstream_request_body(source_protocol, body, protocol)
        suffix = {RESPONSES: "/responses", CHAT: "/chat/completions", ANTHROPIC: "/v1/messages"}[protocol]
        payload = json.dumps(upstream, ensure_ascii=False, separators=(",", ":")).encode()
        try:
            request = Request(_join_url(endpoint["baseUrl"], suffix), data=payload, method="POST",
                              headers=self._headers(endpoint))
            with _open_no_redirect(request, self.timeout_seconds) as response:
                return _read_bounded(response), response.headers.get("Content-Type", "application/json").split(";", 1)[0]
        except HTTPError as error:
            status = error.code
            error.close()
            raise TransportError("provider_http_error", http_status=status) from None
        except (URLError, TimeoutError, OSError):
            raise TransportError("provider_transport_error") from None

    def request(self, source_protocol, body):
        model = body.get("model")
        if not isinstance(model, str) or not model:
            raise ValueError("A model ID is required")
        endpoint = self._endpoint(model)
        try:
            return self._send(source_protocol, body, endpoint)
        except TransportError as error:
            if error.http_status not in {401, 403}:
                raise
        return self._send(source_protocol, body, self._endpoint(model, force=True))

    def close(self):
        self.endpoint = None
        self.model = None
        self.pipe.close()
