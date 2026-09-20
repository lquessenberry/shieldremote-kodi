# ShieldRemote for Kodi (Anbernic RG ARC-D → NVIDIA Shield)

Multi-addon suite that turns an **Anbernic RG ARC-D** running **Kodi 21 Omega**
into a touch + gamepad remote for an **NVIDIA Shield TV**.

Primary control plane: **Android TV Remote Protocol v2** (stub/mock in this
scaffold; plug in `androidtvremote2` when crypto wheels are validated on
Android Kodi). Optional **Kodi JSON-RPC** when the Shield’s foreground app is
Kodi.

> **Limitation:** This is **not** a true HID gamepad. ATV Remote key injection
> is unreliable for games that expect a real controller. Target use: launcher
> nav, media keys, volume, power, app launch, and Kodi-on-Shield control.

## Addons

| Folder | Role |
|--------|------|
| `script.module.shieldremote.core` | Shared API + ATV / JSON-RPC / mock backends + cert paths |
| `script.service.shieldremote` | Startup keepalive / reconnect stub; host IP + protocol settings |
| `script.shieldremote` | Large-button WindowXML remote (640×480-friendly) + pairing stub |
| `script.shieldremote.mapper` | Action ID / joystick → Android keycode profiles |

## Install Kodi 21 Omega (arm64) on ARC-D

1. On the ARC-D Android side (stock Android 11 or GammaOS), enable **Install
   unknown apps** for your file manager / browser.
2. Download the **arm64-v8a** Kodi 21 Omega APK from
   https://mirrors.kodi.tv/releases/android/arm64-v8a/
3. Sideload and launch Kodi once. Prefer Omega for **Python 3.11** (needed if
   you later vendor `androidtvremote2`, which wants ≥3.10).
4. In Kodi: Settings → System → Add-ons → **Unknown sources** = On.

## Zip install

From a PC (or this repo):

```bash
./scripts/package.sh
```

Copy the four zips from `dist/` to the ARC-D (SD card / USB / network share).

In Kodi → Add-ons → Install from zip file, install **in this order**:

1. `script.module.shieldremote.core-*.zip`
2. `script.service.shieldremote-*.zip`
3. `script.shieldremote-*.zip`
4. `script.shieldremote.mapper-*.zip` (optional but recommended)

## Shield pairing (ATV Remote)

1. Open **ShieldRemote** (or service settings) and set **Shield IP** + protocol
   `atv` (scaffold defaults to `mock` for offline testing).
2. Ensure **Android TV Remote Service** is present/updated on the Shield.
3. Run **Pair** on the remote UI — on a real backend this starts TLS pairing on
   TCP **6467**; enter the on-TV **6-digit PIN**. Client certs are stored under
   `special://profile/addon_data/script.module.shieldremote.core/certs/`.
4. Commands use TCP **6466** after pairing.

> This scaffold ships a **mock backend** by default so imports and UI work with
> no network and no secrets. Real `androidtvremote2` plug-in points are marked
> `PLUG_IN` in `backends/atv_remote.py`. See crypto risk notes there.

## ARC-D controls

- Map the Saturn-style pad in Kodi’s **Configure attached controllers**.
- See `script.shieldremote.mapper/README.md` for a `joystick.xml` snippet.
- Touch targets on `remote.xml` are oversized for the 4.0" 640×480 panel.

## Development / tests

```bash
# from repo root
PYTHONPATH=script.module.shieldremote.core/lib:script.shieldremote.mapper \
  python -m unittest discover -s tests -v

# or
./scripts/package.sh
```

No network is required to import the core package or run unit tests.

## Design notes

- Hybrid path: ATV for system/launcher; JSON-RPC for “Kodi mode”.
- Service owns settings (`host`, `protocol`, JSON-RPC credentials).
- Module never appears in the Kodi UI.
- ADB remains a possible future tertiary backend (not scaffolded here).

## License

MIT
