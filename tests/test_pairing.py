"""Unit tests for pairing state machine + ATV key mapping (no Shield needed)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_LIB = ROOT / "script.module.shieldremote.core" / "lib"
if str(CORE_LIB) not in sys.path:
    sys.path.insert(0, str(CORE_LIB))

from shieldremote.api import KEYCODE, ShieldRemoteAPI  # noqa: E402
from shieldremote.backends.atv_remote import (  # noqa: E402
    ATVRemoteBackend,
    MockATVBackend,
    generate_client_certs,
    keycode_to_name,
)
from shieldremote.backends.base import LiveNotAvailableError, PairingError  # noqa: E402
from shieldremote.backends.pairing import (  # noqa: E402
    PairingState,
    PairingStateMachine,
)
from shieldremote.storage import StoragePaths  # noqa: E402


class TestPairingStateMachine(unittest.TestCase):
    def test_happy_path(self):
        sm = PairingStateMachine()
        self.assertEqual(sm.begin("192.0.2.10"), PairingState.GENERATING_CERTS)
        self.assertEqual(sm.certs_ready(), PairingState.CONNECTING)
        self.assertEqual(sm.waiting_for_pin(), PairingState.WAITING_PIN)
        self.assertTrue(sm.can_accept_pin())
        self.assertEqual(sm.submit_pin(), PairingState.FINISHING)
        self.assertEqual(sm.paired(), PairingState.PAIRED)
        self.assertTrue(sm.is_paired())
        self.assertIn("paired@", sm.session.to_status_string())

    def test_need_host(self):
        sm = PairingStateMachine()
        self.assertEqual(sm.begin(""), PairingState.NEED_HOST)
        self.assertEqual(sm.session.to_status_string(), "need_host")

    def test_live_unavailable_status(self):
        sm = PairingStateMachine()
        sm.begin("192.0.2.1")
        sm.live_unavailable("no lib")
        self.assertEqual(sm.state, PairingState.LIVE_UNAVAILABLE)
        self.assertEqual(sm.session.to_status_string(), "live_unavailable")

    def test_fail_status(self):
        sm = PairingStateMachine()
        sm.begin("192.0.2.1")
        sm.fail("boom")
        self.assertTrue(sm.session.to_status_string().startswith("error:"))


class TestKeyMapping(unittest.TestCase):
    def test_keycode_roundtrip(self):
        for name, code in KEYCODE.items():
            self.assertEqual(keycode_to_name(code), name)

    def test_unknown_keycode_falls_back_to_str(self):
        self.assertEqual(keycode_to_name(99999), "99999")


class TestMockPairing(unittest.TestCase):
    def test_mock_pair_any_pin(self):
        b = MockATVBackend()
        self.assertEqual(b.start_pairing(), PairingState.WAITING_PIN)
        self.assertEqual(b.finish_pairing("654321"), PairingState.PAIRED)
        self.assertEqual(b.pairing_status(), "paired@mock")

    def test_mock_pair_bad_pin(self):
        b = MockATVBackend()
        b.start_pairing()
        with self.assertRaises(PairingError):
            b.finish_pairing("abc")

    def test_api_mock_pairing(self):
        api = ShieldRemoteAPI(protocol="mock")
        self.assertEqual(api.start_pairing(), PairingState.WAITING_PIN)
        self.assertEqual(api.finish_pairing("111111"), PairingState.PAIRED)


class TestATVSimulatedPairing(unittest.TestCase):
    def test_simulate_pair_without_live_lib(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = StoragePaths(root=tmp)
            backend = ATVRemoteBackend(
                host="192.0.2.50",
                cert_dir=paths.cert_dir,
                certfile=paths.client_cert,
                keyfile=paths.client_key,
                simulate_pair=True,
                fallback_mock=False,
            )
            state = backend.start_pairing()
            self.assertEqual(state, PairingState.WAITING_PIN)
            state = backend.finish_pairing("123456")
            self.assertEqual(state, PairingState.PAIRED)
            self.assertTrue(backend.has_certs())

    def test_live_connect_raises_without_lib(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = StoragePaths(root=tmp)
            backend = ATVRemoteBackend(
                host="192.0.2.50",
                cert_dir=paths.cert_dir,
                fallback_mock=False,
                simulate_pair=False,
            )
            with self.assertRaises(LiveNotAvailableError):
                backend.connect()

    def test_generate_certs(self):
        with tempfile.TemporaryDirectory() as tmp:
            cert = Path(tmp) / "client.crt"
            key = Path(tmp) / "client.key"
            self.assertTrue(generate_client_certs(str(cert), str(key)))
            self.assertTrue(cert.is_file() and cert.stat().st_size > 0)
            self.assertTrue(key.is_file() and key.stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
