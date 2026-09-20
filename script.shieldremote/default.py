"""Entry point: open the ShieldRemote WindowXML UI."""

from __future__ import annotations

import os
import sys

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(ADDON_DIR, "resources", "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)


def main() -> None:
    from remote_window import RemoteWindow

    win = RemoteWindow(
        "remote.xml",
        ADDON_DIR,
        "Default",
        "720p",
    )
    win.doModal()
    del win


if __name__ == "__main__":
    main()
