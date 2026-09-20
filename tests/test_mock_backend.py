"""Unit tests for mock ATV backend + API facade (no network)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_LIB = ROOT / "script.module.shieldremote.core" / "lib"
if str(CORE_LIB) not in sys.path:
    sys.path.insert(0, str(CORE_LIB))

from shieldremote.api import KEYCODE, ShieldRemoteAPI, send_key  # noqa: E402
from shieldremote.backends.atv_remote import MockATVBackend, ATVRemoteBackend  # noqa: E402
from shieldremote.storage import StoragePaths  # noqa: E402


class TestMockBackend(unittest.TestCase):
    def test_mock_records_keys(self):
        b = MockATVBackend()
        self.assertTrue(b.connect())
        self.assertTrue(b.send_key(KEYCODE["DPAD_UP"]))
        self.assertTrue(b.send_text("hello"))
        self.assertTrue(b.launch_app("com.example.app"))
        kinds = [h[0] for h in b.history]
        self.assertEqual(kinds, ["connect", "send_key", "send_text", "launch_app"])
        self.assertEqual(b.history[1][1], KEYCODE["DPAD_UP"])

    def test_api_defaults_to_mock(self):
        api = ShieldRemoteAPI(host="", protocol="mock")
        self.assertTrue(api.connect())
        self.assertTrue(api.send_key("HOME"))
        self.assertTrue(api.send_key(KEYCODE["BACK"]))
        backend = api.backend
        self.assertIsInstance(backend, MockATVBackend)
        self.assertIn(("send_key", KEYCODE["HOME"]), backend.history)

    def test_api_unknown_key(self):
        api = ShieldRemoteAPI(protocol="mock")
        with self.assertRaises(KeyError):
            api.send_key("NOT_A_REAL_KEY")

    def test_atv_backend_falls_back_to_mock(self):
        backend = ATVRemoteBackend(host="192.0.2.1", fallback_mock=True)
        self.assertTrue(backend.connect())
        self.assertTrue(backend.send_key(19))
        self.assertIsNotNone(backend._mock)

    def test_storage_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = StoragePaths(root=tmp)
            self.assertTrue(Path(paths.cert_dir).is_dir())
            self.assertTrue(paths.client_cert.endswith("client.crt"))

    def test_import_without_network(self):
        import shieldremote.backends.atv_remote as m

        self.assertTrue(hasattr(m, "MockATVBackend"))
        self.assertTrue(hasattr(m, "ATVRemoteBackend"))


if __name__ == "__main__":
    unittest.main()
