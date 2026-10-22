#!/usr/bin/env bash
# macOS / Linux 실행 스크립트: 가상환경 생성 → 패키지 설치 → 앱 실행
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
if [ ! -d .venv ]; then
  echo "▶ 가상환경(.venv) 만드는 중…"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
if [ ! -f .venv/.installed ] || [ requirements.txt -nt .venv/.installed ]; then
  echo "▶ 패키지 설치 중… (처음 한 번은 1~3분 걸려요)"
  python -m pip install --upgrade pip >/dev/null
  python -m pip install -r requirements.txt
  touch .venv/.installed
fi
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo "▶ .env 파일을 만들었어요. 필요한 키를 나중에 채워 넣으세요."
fi
echo "▶ Earnings Lens 실행: http://127.0.0.1:8765  (종료: Ctrl+C)"
exec streamlit run app.py
