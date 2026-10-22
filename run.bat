@echo off
REM Windows 실행 스크립트: 가상환경 생성 -> 패키지 설치 -> 앱 실행
cd /d "%~dp0"
if not exist .venv (
  echo [1/3] 가상환경 만드는 중...
  py -3 -m venv .venv || python -m venv .venv
)
call .venv\Scripts\activate.bat
if not exist .venv\.installed (
  echo [2/3] 패키지 설치 중... 처음 한 번은 1~3분 걸려요
  python -m pip install --upgrade pip >nul
  python -m pip install -r requirements.txt || exit /b 1
  type nul > .venv\.installed
)
if not exist .env (
  copy .env.example .env >nul
  echo .env 파일을 만들었어요. 필요한 키를 나중에 채워 넣으세요.
)
echo [3/3] Earnings Lens 실행: http://127.0.0.1:8765  (종료: Ctrl+C)
streamlit run app.py
