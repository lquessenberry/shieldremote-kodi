# Releases & Install Order

Installable ZIP assets for this suite are published on **GitHub Releases** (not committed in the repo tree). Download the matching `0.1.0` (or newer) release assets from:

https://github.com/lquessenberry/shieldremote-kodi/releases

## Install order (Kodi)

Install the four addon ZIPs from a release **in this order** (Dependencies first):

1. `script.module.shieldremote.core-0.1.0.zip` — shared Python library module
2. `script.service.shieldremote-0.1.0.zip` — background service / pairing
3. `script.shieldremote-0.1.0.zip` — on-screen remote UI
4. `script.shieldremote.mapper-0.1.0.zip` — button mapping / profiles

In Kodi: **Settings → Add-ons → Install from zip file**, then pick each ZIP in the order above.

## Building ZIPs locally

From the repo root:

```bash
./scripts/package.sh
```

Artifacts land in `dist/` (gitignored). Parent maintainers upload those four files to a GitHub Release tagged `v0.1.0` (or the matching version).

## Note for maintainers

If a release was created without assets attached, upload the four ZIPs from `dist/` with `gh release upload` (or the GitHub UI). Binary release assets are not pushed via the source-tree MCP commit.
