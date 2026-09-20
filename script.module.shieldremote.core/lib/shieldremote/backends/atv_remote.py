"""Android TV Remote Protocol v2 client + mock backend.

CRYPTO / PACKAGING RISK (Kodi Android)
--------------------------------------
Live pairing uses TLS client certificates and protobuf framing
(ports 6467 pair / 6466 commands). The reference library is:

    https://github.com/tronikos/androidtvremote2  (PyPI: androidtvremote2)

It depends on ``cryptography`` + ``protobuf``. Native wheels for
``cryptography`` are historically painful on **Kodi Android** (arm64).

Strategy in this module:

  1. Default ``protocol=mock`` — no deps, offline unit tests / UI.
  2. ``ATVRemoteBackend`` tries a lazy import of ``androidtvremote2``.
     When present (desktop venv), pairing + keys talk to a real Shield.
  3. When absent, the pairing **state machine** still runs so the UI can
     show clear ``LiveNotAvailableError`` / status strings; certs may be
     pre-generated via ``cryptography`` or ``openssl`` when available.
  4. Desktop validation: ``scripts/validate_atv_live.py`` (optional dep).

Never import androidtvremote2 at module load time.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import LiveNotAvailableError, PairingError
from .pairing import PairingSession, PairingState, PairingStateMachine

log = logging.getLogger("shieldremote.atv")

CLIENT_NAME_DEFAULT = "ShieldRemoteKodi"
API_PORT_DEFAULT = 6466
PAIR_PORT_DEFAULT = 6467

# Inverse map built lazily from api.KEYCODE
_KEYCODE_TO_NAME: Optional[Dict[int, str]] = None


def keycode_to_name(keycode: int) -> str:
    """Map Android keycode int → name accepted by androidtvremote2."""
    global _KEYCODE_TO_NAME
    if _KEYCODE_TO_NAME is None:
        from ..api import KEYCODE

        _KEYCODE_TO_NAME = {v: k for k, v in KEYCODE.items()}
    return _KEYCODE_TO_NAME.get(keycode, str(keycode))


@dataclass
class MockATVBackend:
    """In-memory backend — no sockets, no TLS. Default for offline tests."""

    history: List[Tuple[str, Any]] = field(default_factory=list)
    connected: bool = False
    pairing: PairingStateMachine = field(default_factory=PairingStateMachine)

    def connect(self) -> bool:
        self.connected = True
        self.history.append(("connect", None))
        log.debug("MockATVBackend.connect()")
        return True

    def disconnect(self) -> None:
        self.connected = False
        self.history.append(("disconnect", None))

    def send_key(self, keycode: int) -> bool:
        if not self.connected:
            self.connect()
        self.history.append(("send_key", keycode))
        log.debug("MockATVBackend.send_key(%s)", keycode)
        return True

    def send_text(self, text: str) -> bool:
        if not self.connected:
            self.connect()
        self.history.append(("send_text", text))
        return True

    def launch_app(self, package_or_uri: str) -> bool:
        if not self.connected:
            self.connect()
        self.history.append(("launch_app", package_or_uri))
        return True

    def start_pairing(self) -> PairingState:
        self.pairing.begin(host="mock")
        self.pairing.certs_ready()
        self.pairing.waiting_for_pin("Mock: enter any 6-digit PIN")
        self.history.append(("start_pairing", None))
        return self.pairing.state

    def finish_pairing(self, pin: str) -> PairingState:
        pin = (pin or "").strip()
        if not self.pairing.can_accept_pin():
            self.pairing.fail("Not waiting for PIN")
            raise PairingError("Mock pairing not waiting for PIN")
        if not pin.isdigit() or len(pin) < 4:
            self.pairing.fail("Invalid PIN format")
            raise PairingError("PIN must be numeric (6 digits on Shield)")
        self.pairing.submit_pin()
        self.pairing.paired()
        self.history.append(("finish_pairing", pin))
        return self.pairing.state

    def pairing_status(self) -> str:
        return self.pairing.session.to_status_string()

    def clear(self) -> None:
        self.history.clear()


class _AsyncBridge:
    """Run coroutines on a dedicated background event loop (thread-safe)."""

    def __init__(self) -> None:
        self._loop: Any = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        import asyncio

        with self._lock:
            if self._loop is not None:
                return
            loop = asyncio.new_event_loop()
            self._loop = loop

            def _run() -> None:
                asyncio.set_event_loop(loop)
                loop.run_forever()

            self._thread = threading.Thread(
                target=_run, name="shieldremote-atv-loop", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            if self._loop is None:
                return
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread is not None:
                self._thread.join(timeout=5)
            self._loop = None
            self._thread = None

    def run(self, coro: Any, timeout: float = 60.0) -> Any:
        import asyncio

        self.start()
        assert self._loop is not None
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)


def generate_client_certs(cert_path: str, key_path: str, common_name: str = CLIENT_NAME_DEFAULT) -> bool:
    """Create self-signed client cert+key if missing.

    Tries ``cryptography`` first, then ``openssl`` CLI. Returns True if
    both files exist after the call. Does not raise — callers inspect return.
    """
    cert_p, key_p = Path(cert_path), Path(key_path)
    if cert_p.is_file() and key_p.is_file() and cert_p.stat().st_size > 0 and key_p.stat().st_size > 0:
        return True
    cert_p.parent.mkdir(parents=True, exist_ok=True)

    if _generate_certs_cryptography(cert_p, key_p, common_name):
        return True
    if _generate_certs_openssl(cert_p, key_p, common_name):
        return True
    return cert_p.is_file() and key_p.is_file()


def _generate_certs_cryptography(cert_p: Path, key_p: Path, common_name: str) -> bool:
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        import datetime
    except ImportError:
        log.info("cryptography not available for cert generation")
        return False
    try:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
        )
        # TODO(PIN pairing): Shield also fingerprints this cert during PIN
        # verification — keep CN stable across reinstalls when possible.
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
            .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
            .sign(key, hashes.SHA256())
        )
        key_p.write_bytes(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        cert_p.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        log.info("Generated client cert via cryptography: %s", cert_p)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("cryptography cert generation failed: %s", exc)
        return False


def _generate_certs_openssl(cert_p: Path, key_p: Path, common_name: str) -> bool:
    openssl = _which("openssl")
    if not openssl:
        return False
    try:
        subprocess.run(
            [
                openssl,
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-keyout",
                str(key_p),
                "-out",
                str(cert_p),
                "-days",
                "3650",
                "-nodes",
                "-subj",
                f"/CN={common_name}",
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        log.info("Generated client cert via openssl: %s", cert_p)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("openssl cert generation failed: %s", exc)
        return False


def _which(cmd: str) -> Optional[str]:
    for path in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(path) / cmd
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


class ATVRemoteBackend:
    """ATV Remote v2 backend with pairing state machine.

    When ``androidtvremote2`` is importable, ``start_pairing`` /
    ``finish_pairing`` / ``connect`` / ``send_*`` talk to a real device.
    Otherwise operations raise ``LiveNotAvailableError`` (unless
    ``fallback_mock=True`` for offline scaffolding).
    """

    def __init__(
        self,
        host: str,
        cert_dir: str = "",
        certfile: str = "",
        keyfile: str = "",
        api_port: int = API_PORT_DEFAULT,
        pair_port: int = PAIR_PORT_DEFAULT,
        client_name: str = CLIENT_NAME_DEFAULT,
        fallback_mock: bool = False,
        simulate_pair: bool = False,
    ) -> None:
        self.host = (host or "").strip()
        self.cert_dir = cert_dir
        self.api_port = int(api_port or API_PORT_DEFAULT)
        self.pair_port = int(pair_port or PAIR_PORT_DEFAULT)
        self.client_name = client_name or CLIENT_NAME_DEFAULT
        self.fallback_mock = fallback_mock
        self.simulate_pair = simulate_pair
        if certfile and keyfile:
            self.certfile = certfile
            self.keyfile = keyfile
        elif cert_dir:
            self.certfile = str(Path(cert_dir) / "client.crt")
            self.keyfile = str(Path(cert_dir) / "client.key")
        else:
            self.certfile = "client.crt"
            self.keyfile = "client.key"

        self._client: Any = None
        self._bridge: Optional[_AsyncBridge] = None
        self._mock: Optional[MockATVBackend] = None
        self._lib: Any = None  # androidtvremote2 module or None
        self.connected = False
        self.pairing = PairingStateMachine(PairingSession(host=self.host))

    # --- discovery / dependency probes ---------------------------------

    def probe_live_library(self) -> bool:
        """Return True if androidtvremote2 can be imported."""
        if self._lib is not None:
            return True
        try:
            import androidtvremote2 as lib  # type: ignore

            self._lib = lib
            return True
        except ImportError:
            log.info(
                "androidtvremote2 not installed — live ATV path unavailable "
                "(use mock backend or desktop validate_atv_live.py)"
            )
            self._lib = False  # type: ignore[assignment]
            return False

    def has_live_library(self) -> bool:
        if self._lib is False:
            return False
        if self._lib is not None:
            return True
        return self.probe_live_library()

    def has_certs(self) -> bool:
        return (
            Path(self.certfile).is_file()
            and Path(self.keyfile).is_file()
            and Path(self.certfile).stat().st_size > 0
        )

    def ensure_certs(self) -> bool:
        self.pairing.set_generating_certs()
        ok = generate_client_certs(self.certfile, self.keyfile, self.client_name)
        if not ok:
            self.pairing.certs_unavailable(
                "Cannot generate TLS client certs (need cryptography or openssl). "
                "On Kodi Android this is a known blocker — pair from a desktop "
                "venv and copy certs, or use protocol=mock."
            )
            return False
        return True

    # --- pairing -------------------------------------------------------

    def start_pairing(self) -> PairingState:
        """Begin pairing. Caller should prompt for PIN then ``finish_pairing``."""
        st = self.pairing.begin(self.host, self.pair_port, self.api_port)
        if st == PairingState.NEED_HOST:
            raise PairingError(self.pairing.session.message)

        if not self.ensure_certs():
            raise LiveNotAvailableError(
                self.pairing.session.last_error or "cert generation failed",
                user_message=self.pairing.session.label(),
            )

        self.pairing.certs_ready()

        if self.simulate_pair or (self.fallback_mock and not self.has_live_library()):
            # Offline state-machine path for tests / scaffold UI
            self.pairing.waiting_for_pin(
                "Simulated pairing — enter any 6-digit PIN (no Shield contact)"
            )
            self.pairing.session.meta["simulated"] = True
            return self.pairing.state

        if not self.has_live_library():
            self.pairing.live_unavailable(
                "androidtvremote2 not installed. Install in a desktop Python "
                "venv to pair a real Shield, or set protocol=mock. "
                "See scripts/validate_atv_live.py and README crypto notes."
            )
            raise LiveNotAvailableError(
                self.pairing.session.last_error,
                user_message=self.pairing.session.label(),
            )

        return self._live_start_pairing()

    def _live_start_pairing(self) -> PairingState:
        assert self._lib is not None and self._lib is not False
        try:
            self._ensure_client()
            self.pairing.session.state = PairingState.CONNECTING
            bridge = self._ensure_bridge()
            # Match tronikos demo: generate certs (already done), start pairing
            bridge.run(self._client.async_generate_cert_if_missing())
            bridge.run(self._client.async_start_pairing())
            self.pairing.waiting_for_pin("Enter the 6-digit PIN shown on the Shield")
            return self.pairing.state
        except LiveNotAvailableError:
            raise
        except Exception as exc:  # noqa: BLE001
            self.pairing.fail(str(exc))
            raise PairingError(f"start_pairing failed: {exc}") from exc

    def finish_pairing(self, pin: str) -> PairingState:
        pin = (pin or "").strip().replace(" ", "")
        if not self.pairing.can_accept_pin():
            raise PairingError(
                f"Not waiting for PIN (state={self.pairing.state.value})"
            )
        if not pin.isdigit() or not (4 <= len(pin) <= 8):
            self.pairing.fail("Invalid PIN format")
            raise PairingError("PIN must be 4–8 digits (Shield shows 6)")

        self.pairing.submit_pin()

        if self.pairing.session.meta.get("simulated") or (
            self.simulate_pair and not self.has_live_library()
        ):
            self.pairing.paired()
            return self.pairing.state

        if not self.has_live_library() or self._client is None:
            self.pairing.live_unavailable("No live client for finish_pairing")
            raise LiveNotAvailableError(
                self.pairing.session.last_error,
                user_message=self.pairing.session.label(),
            )

        try:
            bridge = self._ensure_bridge()
            bridge.run(self._client.async_finish_pairing(pin))
            self.pairing.paired()
            return self.pairing.state
        except Exception as exc:  # noqa: BLE001
            # Invalid PIN — return to WAITING_PIN when possible
            err = str(exc)
            self.pairing.fail(err)
            # Re-arm waiting so UI can retry
            if "Invalid" in type(exc).__name__ or "invalid" in err.lower():
                self.pairing.session.state = PairingState.WAITING_PIN
                self.pairing.session.message = "Invalid PIN — try again"
            raise PairingError(f"finish_pairing failed: {exc}") from exc

    def pairing_status(self) -> str:
        return self.pairing.session.to_status_string()

    # --- connect / commands --------------------------------------------

    def connect(self) -> bool:
        if self.fallback_mock and not self.has_live_library():
            log.info(
                "ATVRemoteBackend: no live client for %s — using MockATVBackend",
                self.host,
            )
            self._mock = MockATVBackend()
            self.connected = self._mock.connect()
            return self.connected

        if not self.host:
            raise LiveNotAvailableError(
                "No Shield host configured",
                user_message="Set Shield IP in service settings",
            )

        if not self.has_live_library():
            raise LiveNotAvailableError(
                "androidtvremote2 not available for live connect",
                user_message=(
                    "Live ATV client unavailable on this device. "
                    "Use protocol=mock for offline testing, or install "
                    "androidtvremote2 in a desktop venv (see README)."
                ),
            )

        if not self.has_certs():
            if not self.ensure_certs():
                raise LiveNotAvailableError(
                    "Missing client certificates",
                    user_message=self.pairing.session.label(),
                )

        try:
            self._ensure_client()
            bridge = self._ensure_bridge()
            bridge.run(self._client.async_connect())
            # Background reconnect helper (uses the same loop)
            try:
                self._client.keep_reconnecting()
            except Exception:  # noqa: BLE001
                log.debug("keep_reconnecting not available / failed", exc_info=True)
            self.connected = True
            if self.has_certs():
                self.pairing.mark_already_paired(self.host)
            return True
        except Exception as exc:  # noqa: BLE001
            self.connected = False
            # InvalidAuth → need pairing
            name = type(exc).__name__
            if name == "InvalidAuth" or "auth" in str(exc).lower():
                raise LiveNotAvailableError(
                    f"Not paired / auth failed: {exc}",
                    user_message="Pairing required — use the Pair button",
                ) from exc
            raise LiveNotAvailableError(
                f"connect failed: {exc}",
                user_message=f"Cannot connect to Shield: {exc}",
            ) from exc

    def disconnect(self) -> None:
        if self._mock is not None:
            self._mock.disconnect()
            self._mock = None
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self._client = None
        if self._bridge is not None:
            self._bridge.stop()
            self._bridge = None
        self.connected = False

    def send_key(self, keycode: int) -> bool:
        if self._mock is not None:
            return self._mock.send_key(keycode)
        if not self.connected or self._client is None:
            self.connect()
        if self._mock is not None:
            return self._mock.send_key(keycode)
        if self._client is None:
            raise LiveNotAvailableError(
                "send_key: no live connection",
                user_message="Not connected to Shield",
            )
        name = keycode_to_name(keycode)
        # androidtvremote2 accepts key names (and some aliases)
        self._client.send_key_command(name)
        return True

    def send_text(self, text: str) -> bool:
        if self._mock is not None:
            return self._mock.send_text(text)
        if not self.connected or self._client is None:
            self.connect()
        if self._mock is not None:
            return self._mock.send_text(text)
        if self._client is None:
            raise LiveNotAvailableError(
                "send_text: no live connection",
                user_message="Not connected to Shield",
            )
        self._client.send_text(text)
        return True

    def launch_app(self, package_or_uri: str) -> bool:
        if self._mock is not None:
            return self._mock.launch_app(package_or_uri)
        if not self.connected or self._client is None:
            self.connect()
        if self._mock is not None:
            return self._mock.launch_app(package_or_uri)
        if self._client is None:
            raise LiveNotAvailableError(
                "launch_app: no live connection",
                user_message="Not connected to Shield",
            )
        self._client.send_launch_app_command(package_or_uri)
        return True

    # --- internals -----------------------------------------------------

    def _ensure_bridge(self) -> _AsyncBridge:
        if self._bridge is None:
            self._bridge = _AsyncBridge()
            self._bridge.start()
        return self._bridge

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.has_live_library():
            raise LiveNotAvailableError("androidtvremote2 missing")
        AndroidTVRemote = self._lib.AndroidTVRemote  # type: ignore[union-attr]
        self._client = AndroidTVRemote(
            self.client_name,
            self.certfile,
            self.keyfile,
            self.host,
            api_port=self.api_port,
            pair_port=self.pair_port,
        )
        return self._client
