"""Pairing state machine for Android TV Remote Protocol v2.

Ports: pair TLS on :6467, commands on :6466 (after certs are trusted).

This module is pure logic — no sockets. Backends drive transitions and
persist status via ``storage.StoragePaths``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class PairingState(str, Enum):
    IDLE = "idle"
    NEED_HOST = "need_host"
    GENERATING_CERTS = "generating_certs"
    NEED_CERTS = "need_certs"
    CONNECTING = "connecting"
    WAITING_PIN = "waiting_pin"
    FINISHING = "finishing"
    PAIRED = "paired"
    ERROR = "error"
    LIVE_UNAVAILABLE = "live_unavailable"


# Human-readable labels for settings / UI
STATE_LABELS = {
    PairingState.IDLE: "Not paired",
    PairingState.NEED_HOST: "Set Shield IP first",
    PairingState.GENERATING_CERTS: "Generating client certificates…",
    PairingState.NEED_CERTS: "Cert generation unavailable (crypto)",
    PairingState.CONNECTING: "Connecting to pairing port…",
    PairingState.WAITING_PIN: "Enter PIN shown on TV",
    PairingState.FINISHING: "Finishing pairing…",
    PairingState.PAIRED: "Paired",
    PairingState.ERROR: "Pairing error",
    PairingState.LIVE_UNAVAILABLE: "Live ATV client unavailable",
}


@dataclass
class PairingSession:
    """Tracks one pairing attempt end-to-end."""

    state: PairingState = PairingState.IDLE
    host: str = ""
    pair_port: int = 6467
    api_port: int = 6466
    message: str = ""
    last_error: str = ""
    # Extra bag for backends (e.g. whether live lib is loaded)
    meta: Dict[str, Any] = field(default_factory=dict)

    def label(self) -> str:
        base = STATE_LABELS.get(self.state, self.state.value)
        if self.message:
            return f"{base}: {self.message}"
        if self.state == PairingState.ERROR and self.last_error:
            return f"{base}: {self.last_error}"
        return base

    def to_status_string(self) -> str:
        """Compact status for addon settings (pairing_status)."""
        if self.state == PairingState.PAIRED:
            return f"paired@{self.host}" if self.host else "paired"
        if self.state == PairingState.WAITING_PIN:
            return "waiting_pin"
        if self.state == PairingState.LIVE_UNAVAILABLE:
            return "live_unavailable"
        if self.state == PairingState.ERROR:
            return f"error:{self.last_error[:80]}" if self.last_error else "error"
        return self.state.value

    def reset(self) -> None:
        self.state = PairingState.IDLE
        self.message = ""
        self.last_error = ""
        self.meta.clear()


class PairingStateMachine:
    """Validates and applies pairing transitions.

    Expected happy path::

        IDLE → (host ok) → GENERATING_CERTS → CONNECTING → WAITING_PIN
             → FINISHING → PAIRED

    Offline / missing-deps paths may end in NEED_CERTS or LIVE_UNAVAILABLE.
    """

    def __init__(self, session: Optional[PairingSession] = None) -> None:
        self.session = session or PairingSession()

    @property
    def state(self) -> PairingState:
        return self.session.state

    def begin(self, host: str, pair_port: int = 6467, api_port: int = 6466) -> PairingState:
        host = (host or "").strip()
        self.session.host = host
        self.session.pair_port = pair_port
        self.session.api_port = api_port
        self.session.last_error = ""
        self.session.message = ""
        if not host:
            self.session.state = PairingState.NEED_HOST
            self.session.message = "Configure Shield IP in service settings"
            return self.session.state
        self.session.state = PairingState.GENERATING_CERTS
        return self.session.state

    def set_generating_certs(self) -> PairingState:
        self._require_in(PairingState.GENERATING_CERTS, PairingState.IDLE, PairingState.NEED_HOST)
        self.session.state = PairingState.GENERATING_CERTS
        return self.session.state

    def certs_ready(self) -> PairingState:
        self._require_in(PairingState.GENERATING_CERTS, PairingState.NEED_CERTS)
        self.session.state = PairingState.CONNECTING
        return self.session.state

    def certs_unavailable(self, reason: str) -> PairingState:
        self.session.state = PairingState.NEED_CERTS
        self.session.last_error = reason
        self.session.message = reason
        return self.session.state

    def live_unavailable(self, reason: str) -> PairingState:
        self.session.state = PairingState.LIVE_UNAVAILABLE
        self.session.last_error = reason
        self.session.message = reason
        return self.session.state

    def waiting_for_pin(self, message: str = "") -> PairingState:
        self._require_in(PairingState.CONNECTING, PairingState.GENERATING_CERTS)
        self.session.state = PairingState.WAITING_PIN
        self.session.message = message or "Check the TV for a 6-digit PIN"
        return self.session.state

    def submit_pin(self) -> PairingState:
        self._require_in(PairingState.WAITING_PIN)
        self.session.state = PairingState.FINISHING
        return self.session.state

    def paired(self) -> PairingState:
        self._require_in(PairingState.FINISHING, PairingState.WAITING_PIN, PairingState.CONNECTING)
        self.session.state = PairingState.PAIRED
        self.session.message = ""
        self.session.last_error = ""
        return self.session.state

    def fail(self, error: str) -> PairingState:
        self.session.state = PairingState.ERROR
        self.session.last_error = error
        self.session.message = error
        return self.session.state

    def mark_already_paired(self, host: str = "") -> PairingState:
        if host:
            self.session.host = host
        self.session.state = PairingState.PAIRED
        self.session.last_error = ""
        self.session.message = ""
        return self.session.state

    def can_accept_pin(self) -> bool:
        return self.session.state == PairingState.WAITING_PIN

    def is_paired(self) -> bool:
        return self.session.state == PairingState.PAIRED

    def _require_in(self, *allowed: PairingState) -> None:
        if self.session.state not in allowed:
            # Soft: allow ERROR/IDLE recovery into flow without raising
            if self.session.state in (PairingState.ERROR, PairingState.IDLE, PairingState.LIVE_UNAVAILABLE):
                return
            # Still allow — state machine is advisory for UI; backends may skip
            return
