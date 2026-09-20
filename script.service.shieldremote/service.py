"""ShieldRemote keepalive service.

Reconnect stub: polls settings, attempts connect, sleeps, repeats.
Runs until Kodi abortRequested. Safe when host empty / mock protocol.
"""

from __future__ import annotations

import time

# Ensure core module is importable when installed as sibling addon
try:
    import xbmc
    import xbmcaddon
except ImportError:
    # Offline / unit-test harness
    xbmc = None
    xbmcaddon = None


ADDON_ID = "script.service.shieldremote"
POLL_SECONDS = 30
RECONNECT_SECONDS = 10


def _log(msg: str) -> None:
    if xbmc:
        xbmc.log(f"[ShieldRemoteService] {msg}", xbmc.LOGINFO)
    else:
        print(f"[ShieldRemoteService] {msg}")


def _settings():
    if not xbmcaddon:
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
            "enabled": True,
        }
    addon = xbmcaddon.Addon(ADDON_ID)
    return {
        "host": addon.getSetting("host"),
        "protocol": addon.getSetting("protocol") or "mock",
        "port": addon.getSetting("port") or "6466",
        "pair_port": addon.getSetting("pair_port") or "6467",
        "client_name": addon.getSetting("client_name") or "ShieldRemoteKodi",
        "mapper_profile": addon.getSetting("mapper_profile") or "shield_ui",
        "jsonrpc_url": addon.getSetting("jsonrpc_url"),
        "jsonrpc_user": addon.getSetting("jsonrpc_user"),
        "jsonrpc_password": addon.getSetting("jsonrpc_password"),
        "enabled": addon.getSetting("enabled") != "false",
    }


def _set_pairing_status(status: str) -> None:
    if not xbmcaddon:
        return
    try:
        xbmcaddon.Addon(ADDON_ID).setSetting("pairing_status", status)
    except Exception:
        pass


def _build_api(cfg):
    from shieldremote.api import ShieldRemoteAPI

    try:
        api_port = int(cfg.get("port") or 6466)
    except ValueError:
        api_port = 6466
    try:
        pair_port = int(cfg.get("pair_port") or 6467)
    except ValueError:
        pair_port = 6467
    return ShieldRemoteAPI(
        host=cfg["host"],
        protocol=cfg["protocol"],
        jsonrpc_url=cfg["jsonrpc_url"],
        jsonrpc_user=cfg["jsonrpc_user"],
        jsonrpc_password=cfg["jsonrpc_password"],
        api_port=api_port,
        pair_port=pair_port,
        client_name=cfg.get("client_name") or "ShieldRemoteKodi",
        mapper_profile=cfg.get("mapper_profile") or "shield_ui",
    )


def run() -> None:
    _log("starting keepalive loop")
    api = None
    last_cfg_key = None
    while True:
        if xbmc and xbmc.Monitor().abortRequested():
            break
        cfg = _settings()
        if not cfg.get("enabled", True):
            _log("disabled in settings — sleeping")
            if xbmc:
                if xbmc.Monitor().waitForAbort(POLL_SECONDS):
                    break
            else:
                time.sleep(min(POLL_SECONDS, 1))
                break  # exit quickly in non-kodi harness
            continue
        cfg_key = (cfg["host"], cfg["protocol"], cfg.get("port"), cfg.get("pair_port"))
        try:
            if api is None or cfg_key != last_cfg_key:
                if api is not None:
                    try:
                        api.disconnect()
                    except Exception:
                        pass
                api = _build_api(cfg)
                last_cfg_key = cfg_key
            ok = api.connect()
            status = ""
            try:
                status = api.pairing_status()
                _set_pairing_status(status)
            except Exception:
                pass
            _log(
                f"connect host={cfg['host']!r} protocol={cfg['protocol']!r} "
                f"ok={ok} pairing={status!r}"
            )
        except Exception as exc:  # noqa: BLE001
            _log(f"reconnect stub error: {exc}")
            api = None
            last_cfg_key = None
            _set_pairing_status(f"error:{exc}")
        # Keepalive wait
        wait = RECONNECT_SECONDS if api is None else POLL_SECONDS
        if xbmc:
            if xbmc.Monitor().waitForAbort(wait):
                break
        else:
            time.sleep(min(wait, 0.1))
            break
    if api is not None:
        try:
            api.disconnect()
        except Exception:
            pass
    _log("stopped")


if __name__ == "__main__":
    run()
