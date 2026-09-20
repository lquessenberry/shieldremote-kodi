"""WindowXML remote: onAction + onClick → core API.

Designed for 640×480 touch + ARC-D gamepad actions.
Short Back sends BACK to the Shield; Close button dismisses the window.
Pairing wizard prompts for PIN via xbmcgui Dialog.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger("shieldremote.ui")

try:
    import xbmc
    import xbmcaddon
    import xbmcgui
except ImportError:
    xbmc = None
    xbmcaddon = None
    xbmcgui = None


SERVICE_ID = "script.service.shieldremote"

# Control IDs must match remote.xml
CTRL = {
    "UP": 1001,
    "DOWN": 1002,
    "LEFT": 1003,
    "RIGHT": 1004,
    "OK": 1005,
    "BACK": 1006,
    "HOME": 1007,
    "VOL_UP": 1008,
    "VOL_DOWN": 1009,
    "POWER": 1010,
    "PLAY_PAUSE": 1011,
    "PAIR": 1012,
    "SETTINGS": 1013,
    "CLOSE": 1014,
    "PROFILE": 1015,
}

# Fallback Action ID → key names when mapper profile unavailable
ACTION_MAP = {
    1: "DPAD_LEFT",
    2: "DPAD_RIGHT",
    3: "DPAD_UP",
    4: "DPAD_DOWN",
    7: "DPAD_CENTER",
    10: "BACK",
    92: "BACK",
    12: "VOLUME_UP",
    13: "VOLUME_DOWN",
    15: "HOME",
}

CLICK_MAP = {
    CTRL["UP"]: "DPAD_UP",
    CTRL["DOWN"]: "DPAD_DOWN",
    CTRL["LEFT"]: "DPAD_LEFT",
    CTRL["RIGHT"]: "DPAD_RIGHT",
    CTRL["OK"]: "DPAD_CENTER",
    CTRL["BACK"]: "BACK",
    CTRL["HOME"]: "HOME",
    CTRL["VOL_UP"]: "VOLUME_UP",
    CTRL["VOL_DOWN"]: "VOLUME_DOWN",
    CTRL["POWER"]: "POWER",
    CTRL["PLAY_PAUSE"]: "MEDIA_PLAY_PAUSE",
}

PROFILES = ("shield_ui", "media", "kodi_mode")


def _service_addon():
    if not xbmcaddon:
        return None
    try:
        return xbmcaddon.Addon(SERVICE_ID)
    except Exception:
        return None


def _service_settings() -> dict:
    a = _service_addon()
    if not a:
        return {
            "host": "",
            "protocol": "mock",
            "port": "6466",
            "pair_port": "6467",
            "client_name": "ShieldRemoteKodi",
            "mapper_profile": "shield_ui",
            "jsonrpc_url": "",
            "jsonrpc_user": "",
            "jsonrpc_password": "",
        }
    return {
        "host": a.getSetting("host"),
        "protocol": a.getSetting("protocol") or "mock",
        "port": a.getSetting("port") or "6466",
        "pair_port": a.getSetting("pair_port") or "6467",
        "client_name": a.getSetting("client_name") or "ShieldRemoteKodi",
        "mapper_profile": a.getSetting("mapper_profile") or "shield_ui",
        "jsonrpc_url": a.getSetting("jsonrpc_url"),
        "jsonrpc_user": a.getSetting("jsonrpc_user"),
        "jsonrpc_password": a.getSetting("jsonrpc_password"),
    }


def _set_service_setting(key: str, value: str) -> None:
    a = _service_addon()
    if a:
        try:
            a.setSetting(key, value)
        except Exception:
            pass


def _notify(title: str, msg: str) -> None:
    if xbmcgui:
        xbmcgui.Dialog().notification(title, msg, time=4000)
    else:
        print(f"{title}: {msg}")


def _ok(title: str, msg: str) -> None:
    if xbmcgui:
        xbmcgui.Dialog().ok(title, msg)
    else:
        print(f"{title}: {msg}")


def _prompt_pin() -> Optional[str]:
    """Ask for the on-TV pairing PIN (numeric preferred)."""
    if not xbmcgui:
        return "123456"  # offline harness
    dlg = xbmcgui.Dialog()
    # numeric() returns int; empty cancel → None behaviour varies by platform
    try:
        pin = dlg.numeric(0, "Enter Shield pairing PIN")
        if pin is None or pin == "":
            return None
        return str(pin).strip()
    except Exception:
        pin = dlg.input("Enter Shield pairing PIN", type=xbmcgui.INPUT_NUMERIC)
        if not pin:
            return None
        return str(pin).strip()


def _load_mapper_actions(profile_name: str) -> Dict[int, str]:
    """Load action_id → key map from mapper addon profiles."""
    try:
        import mapping  # type: ignore

        profile = mapping.load_profile(profile_name)
        out: Dict[int, str] = {}
        for aid, key in profile.get("actions", {}).items():
            out[int(aid)] = key
        return out
    except Exception:
        # Mapper addon may not be on sys.path — use built-in fallback
        return dict(ACTION_MAP)


class _Base:
    """Fallback base when xbmcgui missing (import-safe for tests)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def close(self) -> None:
        pass


WindowBase = xbmcgui.WindowXML if xbmcgui else _Base


class RemoteWindow(WindowBase):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if xbmcgui:
            super().__init__(*args)
        self._api: Optional[Any] = None
        self._action_map: Dict[int, str] = dict(ACTION_MAP)
        self._profile = "shield_ui"

    def onInit(self) -> None:  # noqa: N802 — Kodi API
        cfg = _service_settings()
        self._profile = cfg.get("mapper_profile") or "shield_ui"
        self._action_map = _load_mapper_actions(self._profile)
        self._ensure_api()

    def _api_kwargs(self) -> dict:
        cfg = _service_settings()
        try:
            api_port = int(cfg.get("port") or 6466)
        except ValueError:
            api_port = 6466
        try:
            pair_port = int(cfg.get("pair_port") or 6467)
        except ValueError:
            pair_port = 6467
        return {
            "host": cfg["host"],
            "protocol": cfg["protocol"],
            "jsonrpc_url": cfg.get("jsonrpc_url") or "",
            "jsonrpc_user": cfg.get("jsonrpc_user") or "",
            "jsonrpc_password": cfg.get("jsonrpc_password") or "",
            "api_port": api_port,
            "pair_port": pair_port,
            "client_name": cfg.get("client_name") or "ShieldRemoteKodi",
            "mapper_profile": cfg.get("mapper_profile") or "shield_ui",
        }

    def _ensure_api(self, *, force_protocol: Optional[str] = None) -> Any:
        from shieldremote.api import ShieldRemoteAPI

        kwargs = self._api_kwargs()
        if force_protocol:
            kwargs["protocol"] = force_protocol
        # Rebuild when forcing protocol or first init
        if self._api is None or force_protocol:
            if self._api is not None:
                try:
                    self._api.disconnect()
                except Exception:
                    pass
            self._api = ShieldRemoteAPI(**kwargs)
            try:
                self._api.connect()
            except Exception as exc:  # noqa: BLE001
                log.warning("connect failed: %s", exc)
                # Surface live-unavailable once; keep UI usable for Pair
                msg = getattr(exc, "user_message", None) or str(exc)
                if force_protocol or kwargs.get("protocol") != "mock":
                    _notify("ShieldRemote", msg[:100])
        return self._api

    def _send(self, key: str) -> None:
        try:
            api = self._ensure_api()
            api.send_key(key)
        except Exception as exc:  # noqa: BLE001
            msg = getattr(exc, "user_message", None) or str(exc)
            _notify("ShieldRemote", f"Send failed: {msg}"[:120])

    def onAction(self, action: Any) -> None:  # noqa: N802
        aid = action.getId() if hasattr(action, "getId") else int(action)
        # Short Back / nav-back → send BACK to Shield (do NOT close window)
        key = self._action_map.get(aid) or ACTION_MAP.get(aid)
        if key:
            self._send(key)
            return

    def onClick(self, control_id: int) -> None:  # noqa: N802
        if control_id == CTRL["CLOSE"]:
            self.close()
            return
        if control_id == CTRL["PAIR"]:
            run_pairing_wizard(self)
            return
        if control_id == CTRL["SETTINGS"]:
            open_settings()
            return
        if control_id == CTRL["PROFILE"]:
            cycle_mapper_profile(self)
            return
        key = CLICK_MAP.get(control_id)
        if key:
            self._send(key)

    def onFocus(self, control_id: int) -> None:  # noqa: N802
        pass


def run_pairing_wizard(window: Optional[RemoteWindow] = None) -> bool:
    """Pairing wizard: start pairing → PIN dialog → finish.

    Returns True on success (paired).
    """
    cfg = _service_settings()
    host = (cfg.get("host") or "").strip()
    if not host:
        _ok(
            "ShieldRemote Pairing",
            "Set the Shield IP in Settings first, then tap Pair again.",
        )
        open_settings()
        return False

    protocol = (cfg.get("protocol") or "mock").lower()
    # Prefer ATV for real pairing; mock allows offline PIN demo
    use_protocol = protocol if protocol in ("atv", "mock") else "atv"

    from shieldremote.backends.base import LiveNotAvailableError, PairingError
    from shieldremote.backends.pairing import PairingState

    try:
        if window is not None:
            api = window._ensure_api(force_protocol=use_protocol)
        else:
            from shieldremote.api import ShieldRemoteAPI

            kwargs = {
                "host": host,
                "protocol": use_protocol,
                "api_port": int(cfg.get("port") or 6466),
                "pair_port": int(cfg.get("pair_port") or 6467),
                "client_name": cfg.get("client_name") or "ShieldRemoteKodi",
            }
            api = ShieldRemoteAPI(**kwargs)

        _notify("ShieldRemote", "Starting pairing… watch the Shield for a PIN")
        state = api.start_pairing()
        _set_service_setting("pairing_status", api.pairing_status())

        if state == PairingState.WAITING_PIN:
            pin = _prompt_pin()
            if not pin:
                _notify("ShieldRemote", "Pairing cancelled")
                return False
            state = api.finish_pairing(pin)
            _set_service_setting("pairing_status", api.pairing_status())
            if state == PairingState.PAIRED:
                if use_protocol != "atv":
                    _set_service_setting("protocol", "atv")
                _ok("ShieldRemote", f"Paired with {host}")
                return True
            _ok("ShieldRemote", f"Pairing ended: {api.pairing_status()}")
            return False

        if state == PairingState.PAIRED:
            _ok("ShieldRemote", "Already paired")
            return True

        _ok("ShieldRemote", f"Unexpected pairing state: {state}")
        return False

    except LiveNotAvailableError as exc:
        msg = exc.user_message or str(exc)
        _set_service_setting("pairing_status", "live_unavailable")
        _ok(
            "Live ATV unavailable",
            msg
            + "\n\nOn Kodi Android, cryptography/androidtvremote2 often fail. "
            "Use protocol=mock offline, or pair from a desktop venv "
            "(scripts/validate_atv_live.py) and copy certs.",
        )
        return False
    except PairingError as exc:
        _set_service_setting("pairing_status", f"error:{exc}")
        _ok("Pairing failed", str(exc))
        return False
    except Exception as exc:  # noqa: BLE001
        _set_service_setting("pairing_status", f"error:{exc}")
        _ok("Pairing failed", str(exc))
        return False


def cycle_mapper_profile(window: RemoteWindow) -> None:
    cfg = _service_settings()
    current = cfg.get("mapper_profile") or "shield_ui"
    try:
        idx = PROFILES.index(current)
    except ValueError:
        idx = 0
    nxt = PROFILES[(idx + 1) % len(PROFILES)]
    _set_service_setting("mapper_profile", nxt)
    window._profile = nxt
    window._action_map = _load_mapper_actions(nxt)
    _notify("Mapper profile", nxt)


def open_settings() -> None:
    if xbmcaddon:
        try:
            xbmcaddon.Addon(SERVICE_ID).openSettings()
            return
        except Exception:
            pass
    _notify("ShieldRemote", "Configure host IP / protocol in service settings.")


# Back-compat aliases used by older entry points / docs
pairing_wizard_stub = run_pairing_wizard
open_settings_stub = open_settings
