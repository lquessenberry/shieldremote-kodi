"""High-level Shield remote API facade.

Public API: send_key, send_text, launch_app, start_pairing, finish_pairing.
Selects backend from settings (or mock when offline / no host).
Does not require network to import.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .backends.atv_remote import ATVRemoteBackend, MockATVBackend
from .backends.base import LiveNotAvailableError, PairingError, ShieldRemoteError
from .backends.jsonrpc import JSONRPCBackend
from .backends.pairing import PairingState
from .storage import StoragePaths

log = logging.getLogger("shieldremote.api")

# Common Android / ATV keycodes used by the remote UI
KEYCODE = {
    "DPAD_UP": 19,
    "DPAD_DOWN": 20,
    "DPAD_LEFT": 21,
    "DPAD_RIGHT": 22,
    "DPAD_CENTER": 23,  # OK / Select
    "BACK": 4,
    "HOME": 3,
    "MENU": 82,
    "VOLUME_UP": 24,
    "VOLUME_DOWN": 25,
    "VOLUME_MUTE": 164,
    "POWER": 26,
    "MEDIA_PLAY_PAUSE": 85,
    "MEDIA_PLAY": 126,
    "MEDIA_PAUSE": 127,
    "MEDIA_STOP": 86,
    "MEDIA_NEXT": 87,
    "MEDIA_PREVIOUS": 88,
}


class ShieldRemoteAPI:
    """Facade over ATV Remote / JSON-RPC / mock backends."""

    def __init__(
        self,
        host: str = "",
        protocol: str = "mock",
        jsonrpc_url: str = "",
        jsonrpc_user: str = "",
        jsonrpc_password: str = "",
        storage: Optional[StoragePaths] = None,
        api_port: int = 6466,
        pair_port: int = 6467,
        client_name: str = "ShieldRemoteKodi",
        mapper_profile: str = "shield_ui",
    ) -> None:
        self.host = (host or "").strip()
        self.protocol = (protocol or "mock").lower()
        self.jsonrpc_url = jsonrpc_url
        self.jsonrpc_user = jsonrpc_user
        self.jsonrpc_password = jsonrpc_password
        self.storage = storage or StoragePaths()
        self.api_port = int(api_port or 6466)
        self.pair_port = int(pair_port or 6467)
        self.client_name = client_name or "ShieldRemoteKodi"
        self.mapper_profile = mapper_profile or "shield_ui"
        self._backend: Any = None

    def _make_backend(self) -> Any:
        proto = self.protocol
        if proto in ("mock", ""):
            log.info("Using MockATVBackend (host=%r protocol=%r)", self.host, proto)
            return MockATVBackend()
        if proto in ("atv", "atv_remote", "androidtvremote2"):
            if not self.host:
                log.info("ATV selected but no host — MockATVBackend")
                return MockATVBackend()
            return ATVRemoteBackend(
                host=self.host,
                cert_dir=self.storage.cert_dir,
                certfile=self.storage.client_cert,
                keyfile=self.storage.client_key,
                api_port=self.api_port,
                pair_port=self.pair_port,
                client_name=self.client_name,
                fallback_mock=False,
            )
        if proto in ("jsonrpc", "kodi"):
            return JSONRPCBackend(
                base_url=self.jsonrpc_url or f"http://{self.host}:8080/jsonrpc",
                username=self.jsonrpc_user,
                password=self.jsonrpc_password,
            )
        log.warning("Unknown protocol %r — falling back to mock", proto)
        return MockATVBackend()

    @property
    def backend(self) -> Any:
        if self._backend is None:
            self._backend = self._make_backend()
        return self._backend

    def connect(self) -> bool:
        return bool(self.backend.connect())

    def disconnect(self) -> None:
        if self._backend is not None:
            self._backend.disconnect()
            self._backend = None

    def send_key(self, key: str | int) -> bool:
        """Send a named key (KEYCODE map) or raw Android keycode int."""
        code: int
        if isinstance(key, int):
            code = key
        else:
            name = key.upper().replace(" ", "_")
            if name not in KEYCODE:
                raise KeyError(f"Unknown key name: {key}")
            code = KEYCODE[name]
        return bool(self.backend.send_key(code))

    def send_text(self, text: str) -> bool:
        return bool(self.backend.send_text(text))

    def launch_app(self, package_or_uri: str) -> bool:
        return bool(self.backend.launch_app(package_or_uri))

    def start_pairing(self) -> PairingState:
        """Start pairing on the active backend (mock or ATV).

        The UI pairing wizard should construct the API with ``protocol=atv``
        (and a host) before calling this. Mock backend accepts any PIN for
        offline UI tests.
        """
        backend = self.backend
        if not hasattr(backend, "start_pairing"):
            raise PairingError("Active backend does not support pairing")
        state = backend.start_pairing()
        self._persist_pairing_status()
        return state

    def finish_pairing(self, pin: str) -> PairingState:
        backend = self.backend
        if not hasattr(backend, "finish_pairing"):
            raise PairingError("Active backend does not support pairing")
        state = backend.finish_pairing(pin)
        self._persist_pairing_status()
        return state

    def pairing_status(self) -> str:
        backend = self.backend
        if hasattr(backend, "pairing_status"):
            return str(backend.pairing_status())
        return self.storage.get_pairing_status()

    def _persist_pairing_status(self) -> None:
        try:
            status = self.pairing_status()
            self.storage.set_pairing_status(status)
        except Exception:  # noqa: BLE001
            log.debug("Could not persist pairing status", exc_info=True)


# Module-level convenience (lazy singleton for scripts/services)
_default: Optional[ShieldRemoteAPI] = None


def get_api(**kwargs: Any) -> ShieldRemoteAPI:
    global _default
    if kwargs or _default is None:
        _default = ShieldRemoteAPI(**kwargs) if kwargs else ShieldRemoteAPI()
    return _default


def send_key(key: str | int, **kwargs: Any) -> bool:
    return get_api(**kwargs).send_key(key)


def send_text(text: str, **kwargs: Any) -> bool:
    return get_api(**kwargs).send_text(text)


def launch_app(package_or_uri: str, **kwargs: Any) -> bool:
    return get_api(**kwargs).launch_app(package_or_uri)
