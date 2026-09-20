"""ShieldRemote core package — protocol backends and helpers.

Import-safe without network. Mock backend is the default when no device
is configured or androidtvremote2 is unavailable.
"""

from .api import KEYCODE, ShieldRemoteAPI, launch_app, send_key, send_text
from .backends.base import LiveNotAvailableError, PairingError, ShieldRemoteError
from .backends.pairing import PairingState, PairingStateMachine
from .storage import StoragePaths

__all__ = [
    "KEYCODE",
    "ShieldRemoteAPI",
    "send_key",
    "send_text",
    "launch_app",
    "StoragePaths",
    "ShieldRemoteError",
    "LiveNotAvailableError",
    "PairingError",
    "PairingState",
    "PairingStateMachine",
]

__version__ = "0.2.0"
