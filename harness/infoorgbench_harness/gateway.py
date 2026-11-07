# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Loopback gateway for Responses, Chat Completions, and Anthropic Messages."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import threading

from .models.protocols import ANTHROPIC, CHAT, RESPONSES, decode_response, encode_response, merge_usage

_PATHS = {"/v1/responses": RESPONSES, "/responses": RESPONSES,
          "/v1/chat/completions": CHAT, "/chat/completions": CHAT,
          "/v1/messages": ANTHROPIC, "/messages": ANTHROPIC}


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format, *_args):
        return

    def do_POST(self):
        gateway = self.server.gateway
        protocol = _PATHS.get(self.path.rstrip("/") or "/")
        tool = re.fullmatch(r"(?:/v1)?/tools/([A-Za-z][A-Za-z0-9_-]*)", self.path)
        if protocol is None and not tool:
            self._send(404, "application/json", b'{"error":{"message":"not found"}}')
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > gateway.max_request_bytes:
                raise ValueError("request exceeds gateway bound")
            body = json.loads(self.rfile.read(length))
            if protocol is not None and gateway.expected_model is not None and body.get("model") != gateway.expected_model:
                self._send(400, "application/json", b'{"error":{"message":"model differs from sealed run"}}')
                return
            if tool:
                if gateway.tool_handler is None:
                    self._send(404, "application/json", b'{"error":{"message":"tools disabled"}}')
                    return
                result = gateway.tool_handler(tool.group(1), body)
                payload = json.dumps({"text": json.dumps(result, ensure_ascii=False, separators=(",", ":"))},
                                     separators=(",", ":")).encode()
                self._send(200, "application/json", payload)
                return
            raw, content_type = gateway.backend.request(protocol, body)
            response = decode_response(raw, gateway.backend.protocol, content_type)
            gateway.record_usage(response.get("usage", {}))
            if protocol != gateway.backend.protocol:
                raw, content_type = encode_response(response, protocol, stream=body.get("stream", False))
            self._send(200, content_type, raw)
        except Exception as error:
            status = getattr(error, "http_status", 502)
            payload = json.dumps({"error": {"message": "gateway request failed", "type": type(error).__name__}},
                                 separators=(",", ":")).encode()
            self._send(status if isinstance(status, int) else 502, "application/json", payload)

    def _send(self, status, content_type, payload):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)


class Gateway:
    """A per-run server bound only to 127.0.0.1."""

    def __init__(self, backend, *, tool_handler=None, expected_model=None, max_request_bytes=32_000_000):
        self.backend = backend
        self.tool_handler = tool_handler
        self.expected_model = expected_model
        self.max_request_bytes = max_request_bytes
        self.server = None
        self.thread = None
        self.requests = 0
        self.usage = {}
        self._usage_lock = threading.Lock()

    def record_usage(self, usage):
        with self._usage_lock:
            self.requests += 1
            merge_usage(self.usage, usage)

    @property
    def base_url(self):
        if self.server is None:
            raise RuntimeError("gateway is not running")
        return f"http://127.0.0.1:{self.server.server_port}/v1"

    def start(self):
        if self.server is not None:
            return self
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.gateway = self
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def close(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=5)
            self.server = None
            self.thread = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *_args):
        self.close()
