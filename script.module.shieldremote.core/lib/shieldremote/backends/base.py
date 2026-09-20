"""Backend interface and shared errors for Shield control."""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


class ShieldRemoteError(Exception):
    """Base error for Shield remote backends."""


class LiveNotAvailableError(ShieldRemoteError):
    """Raised when a live ATV connection is required but unavailable.

    Typical causes: ``androidtvremote2`` / ``cryptography`` missing on the
    device (common on Kodi Android), or pairing not completed yet.
    The UI should surface ``str(exc)`` (or ``user_message``) to the user.
    """

    def __init__(self, message: str, *, user_message: Optional[str] = None) -> None:
        super().__init__(message)
        self.user_message = user_message or message


class PairingError(ShieldRemoteError):
    """Pairing flow failed (bad PIN, TLS, host unreachable, etc.)."""


@runtime_checkable
class Backend(Protocol):
    """Minimal backend contract used by ``ShieldRemoteAPI``."""

    connected: bool

    def connect(self) -> bool: ...

    def disconnect(self) -> None: ...

    def send_key(self, keycode: int) -> bool: ...

    def send_text(self, text: str) -> bool: ...

    def launch_app(self, package_or_uri: str) -> bool: ...
