#!/usr/bin/env bash
# Lens 마스코트 번들 재빌드 (평소엔 필요 없음 — 빌드 결과 static/mascot/mascot.bundle.js가 저장소에 있다).
# 필요: Node.js, three@0.179.1이 든 node_modules 경로(THREE_NODE_MODULES).
#   THREE_NODE_MODULES=/path/to/node_modules scripts/build_mascot.sh
set -euo pipefail
cd "$(dirname "$0")/.."
: "${THREE_NODE_MODULES:?three가 설치된 node_modules 경로를 THREE_NODE_MODULES로 지정하세요 (예: npm i three@0.179.1 esbuild 후 ./node_modules)}"
ESBUILD="${ESBUILD:-$THREE_NODE_MODULES/.bin/esbuild}"
NODE_PATH="$THREE_NODE_MODULES" "$ESBUILD" static/mascot/src/mascot.js \
  --bundle --format=iife --global-name=LensMascot --minify --target=es2020 \
  --legal-comments=eof --outfile=static/mascot/mascot.bundle.js
cp "$THREE_NODE_MODULES/three/LICENSE" static/mascot/LICENSE-three.txt
echo "built static/mascot/mascot.bundle.js"
