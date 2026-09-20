"""Optional Kodi JSON-RPC HTTP client (stdlib urllib only).

Useful when the Shield is running Kodi in the foreground ("Kodi mode").
Import-safe without network; connect()/call open sockets only when used.
"""

from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

log = logging.getLogger("shieldremote.jsonrpc")

# Map common remote names → Kodi Input.* methods
INPUT_METHODS = {
    "DPAD_UP": "Input.Up",
    "DPAD_DOWN": "Input.Down",
    "DPAD_LEFT": "Input.Left",
    "DPAD_RIGHT": "Input.Right",
    "DPAD_CENTER": "Input.Select",
    "BACK": "Input.Back",
    "HOME": "Input.Home",
    "MENU": "Input.ContextMenu",
}


class JSONRPCBackend:
    """Minimal JSON-RPC 2.0 HTTP client for Kodi on the Shield."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080/jsonrpc",
        username: str = "",
        password: str = "",
        timeout: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("jsonrpc"):
            # allow host:port or full path
            if "://" not in self.base_url:
                self.base_url = f"http://{self.base_url}/jsonrpc"
            elif not self.base_url.endswith("/jsonrpc"):
                self.base_url = self.base_url.rstrip("/") + "/jsonrpc"
        self.username = username
        self.password = password
        self.timeout = timeout
        self.connected = False
        self._req_id = 0

    def connect(self) -> bool:
        # Lightweight probe — JSONRPC.Ping
        try:
            result = self.call("JSONRPC.Ping")
            self.connected = result == "pong" or result is not None
        except Exception as exc:  # noqa: BLE001 — surface as disconnected
            log.warning("JSON-RPC connect failed: %s", exc)
            self.connected = False
        return self.connected

    def disconnect(self) -> None:
        self.connected = False

    def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        self._req_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self._req_id,
        }
        if params is not None:
            payload["params"] = params
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if self.username:
            token = base64.b64encode(
                f"{self.username}:{self.password}".encode("utf-8")
            ).decode("ascii")
            req.add_header("Authorization", f"Basic {token}")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        if "error" in body:
            raise RuntimeError(body["error"])
        return body.get("result")

    def send_key(self, keycode: int) -> bool:
        """Best-effort: map a few Android keycodes to Input.*; else Input.ExecuteAction."""
        # Inverse of a small set — UI usually sends named keys via API facade
        from ..api import KEYCODE

        name = None
        for k, v in KEYCODE.items():
            if v == keycode:
                name = k
                break
        if name and name in INPUT_METHODS:
            self.call(INPUT_METHODS[name])
            return True
        # Fallback: try Player.PlayPause for media play/pause keycode
        if keycode == 85:
            self.call("Player.PlayPause", {"playerid": 1})
            return True
        log.warning("No JSON-RPC mapping for keycode %s", keycode)
        return False

    def send_text(self, text: str) -> bool:
        self.call("Input.SendText", {"text": text, "done": True})
        return True

    def launch_app(self, package_or_uri: str) -> bool:
        # Kodi cannot launch arbitrary Android packages via JSON-RPC.
        log.info("JSONRPCBackend.launch_app ignored (%s) — use ATV backend", package_or_uri)
        return False
