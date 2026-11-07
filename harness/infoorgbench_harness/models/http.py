# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Environment-key HTTP provider backends."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .protocols import ANTHROPIC, CHAT, RESPONSES, from_responses_request, to_responses_request


MAX_RESPONSE_BYTES = 64_000_000


class TransportError(RuntimeError):
    def __init__(self, code, *, http_status=None):
        self.code = code
        self.http_status = http_status
        super().__init__(code)


def _join_url(base_url, suffix):
    parsed = urlsplit(base_url)
    path = parsed.path.rstrip("/")
    if path.endswith(suffix) or (suffix.startswith("/v1/") and path.endswith(suffix[3:])):
        return base_url
    if suffix.startswith("/v1/") and path.endswith("/v1"):
        suffix = suffix[3:]
    return urlunsplit((parsed.scheme, parsed.netloc, path + suffix, parsed.query, parsed.fragment))


def _read_bounded(response, maximum=MAX_RESPONSE_BYTES):
    value = response.read(maximum + 1)
    if len(value) > maximum:
        raise TransportError("provider_response_too_large")
    return value


def _retry_after(value, now=None):
    if not value:
        return 0.0
    try:
        return min(3600.0, max(0.0, float(value)))
    except ValueError:
        try:
            moment = parsedate_to_datetime(value)
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            return min(3600.0, max(0.0, (moment - (now or datetime.now(timezone.utc))).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return 0.0


class ProviderBackend:
    """One direct provider transport. Credentials are read only from its named environment variable."""

    DEFAULTS = {
        "openai": (RESPONSES, "https://api.openai.com/v1", "OPENAI_API_KEY"),
        "openai-chat": (CHAT, "https://api.openai.com/v1", "OPENAI_API_KEY"),
        "anthropic": (ANTHROPIC, "https://api.anthropic.com", "ANTHROPIC_API_KEY"),
    }
    SUFFIXES = {RESPONSES: "/responses", CHAT: "/chat/completions", ANTHROPIC: "/v1/messages"}

    def __init__(self, name, *, base_url=None, key_env=None, timeout_seconds=2400,
                 transport_retries=0, key_header=None, sleep=time.sleep):
        if name not in self.DEFAULTS:
            raise ValueError("Unknown API-key backend")
        protocol, default_url, default_env = self.DEFAULTS[name]
        if type(transport_retries) is not int or not 0 <= transport_retries <= 3:
            raise ValueError("Transport retries must be between zero and three")
        self.name = name
        self.protocol = protocol
        self.base_url = base_url or default_url
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Provider base URL must be HTTP(S) without URL credentials")
        self.key_env = key_env or default_env
        self.timeout_seconds = timeout_seconds
        self.transport_retries = transport_retries
        self.key_header = key_header
        self.sleep = sleep

    def public_metadata(self):
        return {"backend": self.name, "protocol": self.protocol, "key_environment": self.key_env,
                "transport_retries": self.transport_retries,
                "key_header": self.key_header or ("x-api-key" if self.protocol == ANTHROPIC else "authorization")}

    def _headers(self):
        key = os.environ.get(self.key_env)
        if not key:
            raise TransportError("missing_api_key")
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream, application/json"}
        if self.protocol == ANTHROPIC:
            headers.update({"X-Api-Key": key, "Anthropic-Version": "2023-06-01"})
        elif self.key_header:
            headers[self.key_header] = key
        else:
            headers["Authorization"] = "Bearer " + key
        return headers

    def request(self, source_protocol, body):
        canonical = to_responses_request(body, source_protocol)
        canonical["store"] = False
        upstream = from_responses_request(canonical, self.protocol)
        payload = json.dumps(upstream, ensure_ascii=False, separators=(",", ":")).encode()
        url = _join_url(self.base_url, self.SUFFIXES[self.protocol])
        for attempt in range(self.transport_retries + 1):
            try:
                request = Request(url, data=payload, method="POST", headers=self._headers())
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    content_type = response.headers.get("Content-Type", "application/json").split(";", 1)[0]
                    return _read_bounded(response), content_type
            except HTTPError as error:
                error.close()
                if attempt < self.transport_retries and error.code in {408, 429, 502, 503, 504}:
                    self.sleep(_retry_after(error.headers.get("Retry-After")))
                    continue
                raise TransportError("provider_http_error", http_status=error.code) from None
            except (URLError, TimeoutError, OSError):
                if attempt < self.transport_retries:
                    continue
                raise TransportError("provider_transport_error") from None
        raise AssertionError("unreachable")
