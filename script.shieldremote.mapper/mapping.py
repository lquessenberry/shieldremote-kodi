"""Kodi Action ID / joystick button → Android keycode profiles.

Pure data + helpers; no network. Profiles live under ./profiles/*.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Well-known Kodi action IDs (see guilib Key.h / ActionIDs)
KODI_ACTIONS = {
    1: "ACTION_MOVE_LEFT",
    2: "ACTION_MOVE_RIGHT",
    3: "ACTION_MOVE_UP",
    4: "ACTION_MOVE_DOWN",
    7: "ACTION_SELECT_ITEM",
    10: "ACTION_PREVIOUS_MENU",
    12: "ACTION_VOLUME_UP",
    13: "ACTION_VOLUME_DOWN",
    14: "ACTION_MUTE",
    15: "ACTION_PARENT_DIR",
    79: "ACTION_PLAYER_PLAYPAUSE",
    92: "ACTION_NAV_BACK",
    18: "ACTION_SHOW_INFO",
}

# Android keycode names (match core KEYCODE keys)
ANDROID_KEYS = {
    "DPAD_UP",
    "DPAD_DOWN",
    "DPAD_LEFT",
    "DPAD_RIGHT",
    "DPAD_CENTER",
    "BACK",
    "HOME",
    "MENU",
    "VOLUME_UP",
    "VOLUME_DOWN",
    "VOLUME_MUTE",
    "POWER",
    "MEDIA_PLAY_PAUSE",
    "MEDIA_PLAY",
    "MEDIA_PAUSE",
    "MEDIA_STOP",
    "MEDIA_NEXT",
    "MEDIA_PREVIOUS",
}


def profiles_dir() -> Path:
    return Path(os.path.dirname(os.path.abspath(__file__))) / "profiles"


def list_profiles() -> List[str]:
    d = profiles_dir()
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.json"))


def load_profile(name: str) -> Dict[str, Any]:
    path = profiles_dir() / f"{name}.json"
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    # Normalize action keys to str for JSON round-trip consistency
    actions = {str(k): v for k, v in data.get("actions", {}).items()}
    data["actions"] = actions
    return data


def map_action(profile: Dict[str, Any], action_id: int) -> Optional[str]:
    """Return Android keycode name for a Kodi action id, or None."""
    return profile.get("actions", {}).get(str(action_id))


def map_joystick_button(profile: Dict[str, Any], button: str) -> Optional[str]:
    """Return Android keycode name for a joystick button label, or None."""
    return profile.get("joystick", {}).get(button)


def validate_profile(profile: Dict[str, Any]) -> List[str]:
    """Return list of validation errors (empty = OK)."""
    errors: List[str] = []
    for aid, key in profile.get("actions", {}).items():
        try:
            int(aid)
        except (TypeError, ValueError):
            errors.append(f"invalid action id: {aid!r}")
        if key not in ANDROID_KEYS:
            errors.append(f"unknown android key for action {aid}: {key!r}")
    for btn, key in profile.get("joystick", {}).items():
        if key not in ANDROID_KEYS:
            errors.append(f"unknown android key for joystick {btn}: {key!r}")
    return errors
