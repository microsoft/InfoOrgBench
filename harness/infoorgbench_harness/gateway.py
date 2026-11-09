# Copyright (c) The InfoOrgBench authors.
# Licensed under the MIT License.
"""Authenticated loopback gateway for three provider protocols."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import secrets
import socket
import sys
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
        if not gateway.request_slots.acquire(blocking=False):
            self._send(503, "application/json", b'{"error":{"message":"gateway concurrency limit"}}', close=True)
            return
        try:
            self.connection.settimeout(gateway.read_timeout_seconds)
            self._handle_authenticated(gateway)
        except (socket.timeout, TimeoutError):
            self._send(408, "application/json", b'{"error":{"message":"request body timeout"}}', close=True)
        finally:
            gateway.request_slots.release()

    def _handle_authenticated(self, gateway):
        authorization = self.headers.get("Authorization", "")
        api_key = self.headers.get("x-api-key", "")
        authorized = ((authorization.startswith("Bearer ")
                       and secrets.compare_digest(authorization[7:], gateway.token))
                      or secrets.compare_digest(api_key, gateway.token))
        if not authorized:
            self._send(401, "application/json", b'{"error":{"message":"authentication required"}}', close=True)
            return
        if self.headers.get_content_type().lower() != "application/json":
            self._send(415, "application/json", b'{"error":{"message":"application/json required"}}', close=True)
            return
        protocol = _PATHS.get(self.path.rstrip("/") or "/")
        tool = re.fullmatch(r"(?:/v1)?/tools/([A-Za-z][A-Za-z0-9_-]*)", self.path)
        if protocol is None and not tool:
            self._send(404, "application/json", b'{"error":{"message":"not found"}}', close=True)
            return
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            self._send(411, "application/json", b'{"error":{"message":"content length required"}}', close=True)
            return
        try:
            length = int(raw_length)
        except ValueError:
            self._send(400, "application/json", b'{"error":{"message":"invalid content length"}}', close=True)
            return
        if length < 0 or length > gateway.max_request_bytes:
            self._send(413, "application/json", b'{"error":{"message":"request exceeds gateway bound"}}', close=True)
            return
        try:
            body = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(400, "application/json", b'{"error":{"message":"invalid JSON"}}')
            return
        if protocol is not None and gateway.expected_model is not None and body.get("model") != gateway.expected_model:
            self._send(400, "application/json", b'{"error":{"message":"model differs from sealed run"}}')
            return
        if tool:
            if gateway.tool_handler is None:
                self._send(404, "application/json", b'{"error":{"message":"tools disabled"}}')
                return
            try:
                with gateway.tool_lock:
                    result = gateway.tool_handler(tool.group(1), body)
            except (ValueError, KeyError, TypeError, OSError) as error:
                result = {"error": str(error) or type(error).__name__}
            payload = json.dumps({"text": json.dumps(result, ensure_ascii=False, separators=(",", ":"))},
                                 separators=(",", ":")).encode()
            self._send(200, "application/json", payload)
            return
        try:
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

    def _send(self, status, content_type, payload, *, close=False):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        if close:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(payload)


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


class Gateway:
    """A per-run authenticated server bound only to 127.0.0.1."""

    def __init__(self, backend, *, tool_handler=None, expected_model=None, max_request_bytes=32_000_000,
                 read_timeout_seconds=30, max_concurrent_requests=16):
        if type(max_concurrent_requests) is not int or max_concurrent_requests < 1:
            raise ValueError("Gateway concurrency must be a positive integer")
        if type(read_timeout_seconds) not in (int, float) or read_timeout_seconds <= 0:
            raise ValueError("Gateway read timeout must be positive")
        self.backend = backend
        self.tool_handler = tool_handler
        self.expected_model = expected_model
        self.max_request_bytes = max_request_bytes
        self.read_timeout_seconds = read_timeout_seconds
        self.max_concurrent_requests = max_concurrent_requests
        self.token = secrets.token_urlsafe(32)
        self.server = None
        self.thread = None
        self.requests = 0
        self.usage = {}
        self._usage_lock = threading.Lock()
        self.tool_lock = threading.Lock()
        self.request_slots = threading.BoundedSemaphore(max_concurrent_requests)

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
        self.server = _Server(("127.0.0.1", 0), _Handler)
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
        self.token = ""

    def __enter__(self):
        return self.start()

    def __exit__(self, *_args):
        self.close()
