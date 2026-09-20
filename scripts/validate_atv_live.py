#!/usr/bin/env python3
"""Desktop validation against a real Shield using androidtvremote2.

This script is **not** for Kodi Android. Run it in a normal Python ≥3.10
venv on a PC on the same LAN as the Shield to:

  1. Generate / reuse TLS client certs
  2. Pair (PIN shown on the TV)
  3. Send a few navigation keys

Install deps first::

    python3 -m venv .venv-atv
    source .venv-atv/bin/activate
    pip install 'androidtvremote2'

Usage::

    python scripts/validate_atv_live.py --host 192.168.1.50
    python scripts/validate_atv_live.py --host 192.168.1.50 --cert-dir ./certs

Copy the resulting cert/key into the Kodi profile path::

    special://profile/addon_data/script.module.shieldremote.core/certs/
    (files: client.crt + client.key)

Crypto caveat: ``androidtvremote2`` pulls ``cryptography`` + ``protobuf``.
Those native wheels often fail on Kodi Android — hence mock default on device
and this desktop validator for live Shield tests.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


async def _pair(remote) -> None:
    print(f"Starting pairing with {remote.host} — check the Shield for a PIN…")
    await remote.async_start_pairing()
    while True:
        pin = input("Enter 6-digit PIN: ").strip()
        try:
            await remote.async_finish_pairing(pin)
            print("Paired OK")
            return
        except Exception as exc:  # noqa: BLE001
            name = type(exc).__name__
            if name == "InvalidAuth" or "invalid" in str(exc).lower():
                print(f"Invalid PIN ({exc}); try again")
                continue
            if name == "ConnectionClosed":
                print("Connection closed; restarting pairing…")
                return await _pair(remote)
            print(f"PIN failed ({exc}); try again or Ctrl-C")


async def _run(host: str, cert_dir: Path, client_name: str) -> int:
    try:
        from androidtvremote2 import AndroidTVRemote  # type: ignore
    except ImportError:
        print(
            "ERROR: androidtvremote2 is not installed.\n"
            "  python3 -m venv .venv-atv && source .venv-atv/bin/activate\n"
            "  pip install androidtvremote2",
            file=sys.stderr,
        )
        return 2

    cert_dir.mkdir(parents=True, exist_ok=True)
    certfile = cert_dir / "client.crt"
    keyfile = cert_dir / "client.key"

    # tronikos/androidtvremote2 API (see upstream demo.py)
    remote = AndroidTVRemote(
        client_name,
        str(certfile),
        str(keyfile),
        host,
        api_port=6466,
        pair_port=6467,
    )

    if await remote.async_generate_cert_if_missing():
        print(f"Generated certs under {cert_dir}")

    while True:
        try:
            await remote.async_connect()
            print("Connected on :6466")
            break
        except Exception as exc:  # noqa: BLE001
            name = type(exc).__name__
            if name == "InvalidAuth" or "auth" in str(exc).lower():
                await _pair(remote)
                continue
            print(f"Cannot connect: {exc}", file=sys.stderr)
            return 1

    try:
        remote.keep_reconnecting()
    except Exception:
        pass

    print("Sending DPAD_CENTER, HOME, BACK…")
    for key in ("DPAD_CENTER", "HOME", "BACK"):
        remote.send_key_command(key)
        print(f"  sent {key}")
        await asyncio.sleep(0.4)

    try:
        remote.disconnect()
    except Exception:
        pass
    print("Done. Certs at:", certfile, keyfile)
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", required=True, help="Shield IP address")
    p.add_argument(
        "--cert-dir",
        default=str(Path.cwd() / "atv-certs"),
        help="Directory for client.crt / client.key",
    )
    p.add_argument("--client-name", default="ShieldRemoteKodi")
    args = p.parse_args()
    raise SystemExit(
        asyncio.run(_run(args.host, Path(args.cert_dir), args.client_name))
    )


if __name__ == "__main__":
    main()
