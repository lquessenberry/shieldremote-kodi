"""Mapper entry — list profiles / dump mapping (scaffold)."""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from mapping import list_profiles, load_profile  # noqa: E402


def main() -> None:
    try:
        import xbmcgui
    except ImportError:
        xbmcgui = None

    names = list_profiles()
    lines = [f"Profiles: {', '.join(names)}"]
    for name in names:
        profile = load_profile(name)
        lines.append(f"--- {name} ({profile.get('description', '')}) ---")
        for action_id, keycode_name in sorted(
            profile.get("actions", {}).items(), key=lambda x: int(x[0])
        ):
            lines.append(f"  Action {action_id} → {keycode_name}")
    text = "\n".join(lines)
    if xbmcgui:
        xbmcgui.Dialog().textviewer("ShieldRemote Mapper", text)
    else:
        print(text)


if __name__ == "__main__":
    main()
