"""Certificate and addon_data path helpers.

On device, certs live under::

    special://profile/addon_data/script.module.shieldremote.core/

When xbmc is unavailable (unit tests / desktop packaging), falls back to
a local ``.shieldremote_data`` directory under the cwd or an explicit path.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


ADDON_ID = "script.module.shieldremote.core"


def _translate_path(special: str) -> Optional[str]:
    try:
        import xbmc  # type: ignore

        return xbmc.translatePath(special)  # Kodi <=18
    except Exception:
        pass
    try:
        import xbmcvfs  # type: ignore

        return xbmcvfs.translatePath(special)
    except Exception:
        return None


class StoragePaths:
    """Resolve cert / profile directories without requiring network."""

    def __init__(self, root: Optional[str] = None) -> None:
        if root:
            self.root = Path(root)
        else:
            translated = _translate_path(f"special://profile/addon_data/{ADDON_ID}/")
            if translated:
                self.root = Path(translated)
            else:
                env = os.environ.get("SHIELDREMOTE_DATA")
                self.root = Path(env) if env else Path.cwd() / ".shieldremote_data"
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def cert_dir(self) -> str:
        d = self.root / "certs"
        d.mkdir(parents=True, exist_ok=True)
        return str(d)

    @property
    def client_cert(self) -> str:
        return str(Path(self.cert_dir) / "client.crt")

    @property
    def client_key(self) -> str:
        return str(Path(self.cert_dir) / "client.key")

    @property
    def state_file(self) -> str:
        return str(self.root / "state.json")

    def load_state(self) -> Dict[str, Any]:
        path = Path(self.state_file)
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_state(self, data: Dict[str, Any]) -> None:
        path = Path(self.state_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        merged = self.load_state()
        merged.update(data)
        path.write_text(json.dumps(merged, indent=2), encoding="utf-8")

    def set_pairing_status(self, status: str) -> None:
        self.save_state({"pairing_status": status})

    def get_pairing_status(self) -> str:
        return str(self.load_state().get("pairing_status", "unpaired"))
