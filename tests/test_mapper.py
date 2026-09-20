"""Unit tests for script.shieldremote.mapper profiles."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPPER = ROOT / "script.shieldremote.mapper"
if str(MAPPER) not in sys.path:
    sys.path.insert(0, str(MAPPER))

import mapping  # noqa: E402


class TestMapper(unittest.TestCase):
    def test_list_profiles(self):
        names = mapping.list_profiles()
        self.assertIn("shield_ui", names)
        self.assertIn("kodi_mode", names)
        self.assertIn("media", names)

    def test_shield_ui_dpad(self):
        p = mapping.load_profile("shield_ui")
        self.assertEqual(mapping.map_action(p, 3), "DPAD_UP")
        self.assertEqual(mapping.map_action(p, 7), "DPAD_CENTER")
        self.assertEqual(mapping.map_joystick_button(p, "a"), "DPAD_CENTER")
        self.assertEqual(mapping.map_joystick_button(p, "b"), "BACK")

    def test_profiles_validate(self):
        for name in mapping.list_profiles():
            profile = mapping.load_profile(name)
            errors = mapping.validate_profile(profile)
            self.assertEqual(errors, [], msg=f"{name}: {errors}")

    def test_unknown_action(self):
        p = mapping.load_profile("shield_ui")
        self.assertIsNone(mapping.map_action(p, 9999))


if __name__ == "__main__":
    unittest.main()
