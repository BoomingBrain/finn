#!/usr/bin/env bash
# Builds the web app and pushes ONLY the built site + snapshot data to the Hugging Face Static Space.
# The Space holds a build artifact, so its history is replaced on every deploy.
# Usage: scripts/deploy_space.sh [--dry-run]   (--dry-run builds and checks, but does not push)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/build/space"

env_get() {  # $1 from the environment, else from .env (tolerates spaces around '=' and quotes)
  if [ -n "${!1:-}" ]; then printf '%s' "${!1}"; return; fi
  [ -f "$ROOT/.env" ] && sed -n -E "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*['\"]?([^'\"]*)['\"]?[[:space:]]*\$/\1/p" "$ROOT/.env" | tail -1
}
HF_TOKEN="$(env_get HF_TOKEN)"
HF_SPACE="$(env_get HF_SPACE)"
RENDER_URL="$(env_get RENDER_URL)"
if [ -z "$HF_TOKEN" ] || [ -z "$HF_SPACE" ]; then echo "HF_TOKEN and HF_SPACE must be set in .env" >&2; exit 1; fi

# 1. Build the web app; the Render URL (if any) is baked in for live research.
(cd "$ROOT/web" && npm ci --silent && VITE_API_BASE="$RENDER_URL" npm run build)

# 2. Assemble the site: built files + snapshot data + Space config.
rm -rf "$OUT" && mkdir -p "$OUT"
cp -R "$ROOT/web/dist/." "$OUT/"
if [ -d "$ROOT/data/snapshot" ]; then mkdir -p "$OUT/data" && cp -R "$ROOT/data/snapshot/." "$OUT/data/"; fi
cat > "$OUT/README.md" <<EOF
---
title: FINN
emoji: 📈
colorFrom: blue
colorTo: yellow
sdk: static
app_file: index.html
pinned: false
short_description: Portfolio filings, filtered to what matters
---

Built site for FINN. This Space is a build artifact and is overwritten on every deploy.
EOF

# 3. Never ship source, secrets or documents.
if find "$OUT" \( -name '.env*' -o -name '*.pdf' -o -name '*.py' -o -name 'backend' \) | grep -q .; then
  echo "Refusing to deploy: build/space contains source, secrets or PDFs" >&2; exit 1
fi
echo "Assembled $(find "$OUT" -type f | wc -l | tr -d ' ') files ($(du -sh "$OUT" | cut -f1)) in build/space"
if [ "${1:-}" = "--dry-run" ]; then echo "Dry run: not pushing."; exit 0; fi

# 4. Push. The token reaches git only through a one-shot credential helper reading an env var:
#    it is never written to disk, a URL or .git/config.
cd "$OUT"
git init -q -b main
git add -A
git -c user.name="FINN deploy" -c user.email="deploy@finn.invalid" commit -q -m "Deploy $(git -C "$ROOT" rev-parse --short HEAD)"
GIT_HF_TOKEN="$HF_TOKEN" git -c credential.helper= \
  -c credential.helper="!f() { echo username=${HF_SPACE%%/*}; echo \"password=\$GIT_HF_TOKEN\"; }; f" \
  push --force "https://huggingface.co/spaces/$HF_SPACE" main
echo "Deployed: https://huggingface.co/spaces/$HF_SPACE"
