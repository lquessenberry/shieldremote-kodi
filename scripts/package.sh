#!/usr/bin/env bash
# Zip each addon folder into dist/<addon_id>-<version>.zip
# Zip root must be the addon id directory (Kodi install-from-zip requirement).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
mkdir -p "$DIST"

ADDONS=(
  script.module.shieldremote.core
  script.service.shieldremote
  script.shieldremote
  script.shieldremote.mapper
)

version_of() {
  # Read version= from the <addon> opening tag (may span lines); ignore <?xml version>
  awk '
    /<addon / { in_addon=1 }
    in_addon && /version="/ {
      if (match($0, /version="[^"]+"/)) {
        v = substr($0, RSTART+9, RLENGTH-10)
        print v
        exit
      }
    }
    in_addon && />/ { in_addon=0 }
  ' "$1/addon.xml"
}

for id in "${ADDONS[@]}"; do
  dir="$ROOT/$id"
  if [[ ! -d "$dir" ]]; then
    echo "missing addon dir: $dir" >&2
    exit 1
  fi
  ver="$(version_of "$dir")"
  if [[ -z "$ver" ]]; then
    echo "could not parse version from $dir/addon.xml" >&2
    exit 1
  fi
  out="$DIST/${id}-${ver}.zip"
  rm -f "$out"
  (
    cd "$ROOT"
    zip -qr "$out" "$id" \
      -x "*/__pycache__/*" \
      -x "*.pyc" \
      -x "*/.shieldremote_data/*"
  )
  echo "created $out"
done

echo "Done. Zips in $DIST:"
ls -la "$DIST"/*.zip
