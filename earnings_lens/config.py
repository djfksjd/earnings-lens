"""환경 설정과 비밀값 관리.

규칙
- 비밀값은 `.env`(또는 OS 환경변수)에서만 읽는다. 코드·YAML·화면에 하드코딩하지 않는다.
- 화면에는 "등록됨/미등록" 상태만 보여준다. 값 자체는 어디에도 출력하지 않는다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
AI_DIR = DATA_DIR / "ai"
MY_INPUTS = ROOT / "my_inputs"
EXAMPLES = MY_INPUTS / "_examples"

# override=False: 이미 셸에 설정된 환경변수가 .env보다 우선한다.
load_dotenv(ROOT / ".env", override=False)


def _get(name: str) -> str:
    return (os.getenv(name) or "").strip()


@dataclass(frozen=True)
class KeySpec:
    env: str
    label: str
    required: bool
    purpose: str
    signup: str


KEY_SPECS: tuple[KeySpec, ...] = (
    KeySpec("SEC_USER_AGENT", "SEC EDGAR 연락처", False,
            "미국 8-K 실적 보도자료(가이던스·세그먼트 원문). 키는 아니고 '이름 이메일' 형식 문자열",
            "https://www.sec.gov/os/accessing-edgar-data"),
    KeySpec("ALPHAVANTAGE_API_KEY", "Alpha Vantage", False,
            "미국 컨콜 트랜스크립트(무료 하루 25회, 받은 내용은 영구 캐시)",
            "https://www.alphavantage.co/support/#api-key"),
    KeySpec("DART_API_KEY", "OpenDART", False,
            "한국 공식 분기 재무제표·잠정실적 공시",
            "https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do"),
    KeySpec("FINNHUB_API_KEY", "Finnhub", False,
            "미국 주식 실시간 시세(무료 분당 60회). 없으면 yfinance 시세 사용",
            "https://finnhub.io/register"),
    KeySpec("KRX_OPEN_API_KEY", "KRX Open API", False,
            "한국 공식 일별 시세. yfinance가 빠뜨린 종가(장 마감 동시호가)·지수 일봉을 채움. 서비스별 이용신청 승인 필요",
            "https://openapi.krx.co.kr"),
)


def has(name: str) -> bool:
    return bool(_get(name))


def secret(name: str) -> str:
    """비밀값을 돌려준다. 호출한 쪽에서 로그·화면에 절대 출력하지 않는다."""
    return _get(name)


def all_secret_values() -> list[str]:
    return [v for v in (_get(k.env) for k in KEY_SPECS) if len(v) >= 6]


SEC_USER_AGENT = _get("SEC_USER_AGENT")
CLAUDE_BIN = _get("CLAUDE_BIN") or "claude"
CLAUDE_MODEL = _get("CLAUDE_MODEL") or "sonnet"
AI_ENABLED = _get("AI_ENABLED").lower() not in {"0", "false", "no", "off"}
PRICE_REFRESH_SECONDS = max(10, int(_get("PRICE_REFRESH_SECONDS") or 30))
# 네이버 증권은 robots.txt로 자동 수집을 막고 있다. 사용자가 직접 켠 경우에만 쓴다.
NAVER_ENABLED = _get("NAVER_SCRAPING_ENABLED").lower() in {"1", "true", "yes", "on"}
# 아래 두 사이트도 robots.txt는 허용하지만 이용약관이 자동 수집을 금지한다. 사용자가 직접 켠 경우에만 쓴다.
MARKETBEAT_ENABLED = _get("MARKETBEAT_SCRAPING_ENABLED").lower() in {"1", "true", "yes", "on"}
FOOL_ENABLED = _get("FOOL_SCRAPING_ENABLED").lower() in {"1", "true", "yes", "on"}

for _d in (CACHE_DIR, SNAPSHOT_DIR, AI_DIR):
    _d.mkdir(parents=True, exist_ok=True)
