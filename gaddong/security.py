"""보안 유틸: 비밀값 마스킹, 입력 검증, HTML 이스케이프."""
from __future__ import annotations

import html
import re

from . import config

# 미국: AAPL, BRK-B, BRK.B / 한국: 005930.KS, 035720.KQ
_TICKER_RE = re.compile(r"^[A-Z0-9]{1,10}([.\-][A-Z0-9]{1,4})?$")
_QUARTER_RE = re.compile(r"^(20\d{2})Q([1-4])$")
_PERIOD_RE = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")
_URL_SECRET_RE = re.compile(r"(?i)(apikey|api_key|token|crtfc_key|appkey|appsecret|secret)=([^&\s\"']+)")


def clean_ticker(raw: str) -> str:
    """티커를 정규화하고 검증한다. 6자리 숫자만 넣으면 코스피(.KS)로 본다."""
    t = (raw or "").strip().upper().replace(" ", "")
    if re.fullmatch(r"\d{6}", t):
        t += ".KS"
    if not _TICKER_RE.fullmatch(t):
        raise ValueError("티커 형식이 올바르지 않습니다. 예: NVDA, 005930.KS")
    return t


def clean_quarter(raw: str) -> str:
    """Alpha Vantage용 회계분기 표기(2027Q2)."""
    q = (raw or "").strip().upper()
    if not _QUARTER_RE.fullmatch(q):
        raise ValueError("분기 형식은 2026Q2 처럼 입력하세요.")
    return q


def clean_period(raw: str) -> str:
    """분기 키는 분기말 연-월(2026-06)로 통일한다."""
    p = (raw or "").strip()
    if not _PERIOD_RE.fullmatch(p):
        raise ValueError("분기 키는 2026-06 처럼 분기말 연-월로 입력하세요.")
    return p


def safe_filename(ticker: str) -> str:
    """경로 조작(../)이 불가능한 파일명 조각으로 바꾼다."""
    return clean_ticker(ticker).replace(".", "_")


def redact(text: object) -> str:
    """에러 메시지·로그에서 URL 쿼리의 키와 .env 비밀값을 지운다."""
    s = str(text)
    s = _URL_SECRET_RE.sub(lambda m: f"{m.group(1)}=***", s)
    for v in config.all_secret_values():
        s = s.replace(v, "***")
    return s


def esc(value: object) -> str:
    """외부 데이터(API·트랜스크립트·사용자 입력)를 HTML에 넣기 전에 반드시 거친다."""
    return html.escape("" if value is None else str(value), quote=True)


def mask(value: str) -> str:
    """키 값은 일부도 보여주지 않는다."""
    return "등록됨" if value else "미등록"
