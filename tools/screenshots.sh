#!/usr/bin/env bash
# Render the demo dashboard at phone and desktop sizes with headless Chrome.
# Usage: tools/screenshots.sh [site-dir] [out-dir]
set -euo pipefail
SITE="$(cd "${1:-site-demo}" && pwd)"; OUT="${2:-docs/img}"; mkdir -p "$OUT"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
shot() { "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
  --virtual-time-budget=4000 --window-size="$2" --screenshot="$3" "$1" >/dev/null 2>&1; }
# Phones: 390px iframes side by side (headless windows can't be narrower than ~500px).
phones() { # $1=theme $2=out $3..=views
  local theme=$1 out=$2; shift 2; local frames=""
  for v in "$@"; do frames+="<iframe src=\"file://$SITE/index.html?theme=$theme#$v\"></iframe>"; done
  cat > "$TMP/p.html" <<HTML
<html><body style="margin:0;padding:24px;display:flex;gap:24px;background:${BG:-#e9e8e3}">
<style>iframe{width:390px;height:844px;border:0;border-radius:36px;box-shadow:0 10px 40px rgba(0,0,0,.25);background:#fff}</style>
$frames</body></html>
HTML
  shot "file://$TMP/p.html" "$(( 24 + 414 * $# )),892" "$out"
}
phones light "$OUT/phones-light.png" overview trends milestones
BG=#111 phones dark "$OUT/phones-dark.png" overview "session/syn-11" trends
shot "file://$SITE/index.html?theme=light#trends" "1280,1500" "$OUT/desktop-trends.png"
shot "file://$SITE/index.html?theme=light#overview" "1280,1300" "$OUT/desktop-overview.png"
echo "screenshots in $OUT"
