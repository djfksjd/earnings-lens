"""Alpha Vantage: 미국 컨콜 트랜스크립트(발언자별 감성 점수 포함). 무료 키 하루 25회.

받은 트랜스크립트는 data/cache/transcripts에 영구 저장해 같은 분기를 다시 호출하지 않는다.
"""
from __future__ import annotations

import json

from .. import config
from ..security import clean_quarter, safe_filename
from .http import ProviderError, get


def fiscal_quarter(period: str, fy_end_month: int) -> str:
    """분기말(YYYY-MM)과 회계연도 종료월로 회계분기(2027Q2)를 계산한다.

    NVDA(1월 결산) 2026-07 → 2027Q2, AAPL(9월 결산) 2026-06 → 2026Q3, 12월 결산 2026-06 → 2026Q2.
    """
    year, month = int(period[:4]), int(period[5:7])
    q = ((month - fy_end_month - 1) % 12) // 3 + 1
    fy = year if month <= fy_end_month else year + 1
    return f"{fy}Q{q}"


def transcript(ticker: str, fiscal_q: str, *, force: bool = False) -> list[dict]:
    fiscal_q = clean_quarter(fiscal_q)
    path = config.CACHE_DIR / "transcripts" / f"{safe_filename(ticker)}_{fiscal_q}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return json.loads(path.read_text(encoding="utf-8"))
    key = config.secret("ALPHAVANTAGE_API_KEY")
    if not key:
        raise ProviderError("ALPHAVANTAGE_API_KEY가 .env에 없습니다.")
    data = get("https://www.alphavantage.co/query",
               params={"function": "EARNINGS_CALL_TRANSCRIPT", "symbol": ticker, "quarter": fiscal_q, "apikey": key},
               timeout=30).json()
    if "Information" in data or "Note" in data:
        raise ProviderError("Alpha Vantage 무료 호출 한도(하루 25회)에 도달했거나 키가 올바르지 않습니다.")
    turns = data.get("transcript") or []
    if not turns:
        raise ProviderError(f"{ticker} {fiscal_q} 트랜스크립트가 없습니다. 분기 표기를 확인하세요.")
    clean = [{"speaker": t.get("speaker", ""), "title": t.get("title", ""), "content": t.get("content", ""),
              "sentiment": _f(t.get("sentiment"))} for t in turns]
    path.write_text(json.dumps(clean, ensure_ascii=False), encoding="utf-8")
    return clean


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def estimates(ticker: str) -> dict[str, dict]:
    """분기별 매출·EPS 컨센서스(과거 분기 포함, 평균·상단·하단). 하루 1회만 호출하고 캐시한다.

    반환: {"2026-06": {"revenue": .., "revenue_low": .., "revenue_high": .., "eps": .., "eps_low": .., "eps_high": ..}}
    """
    import time

    path = config.CACHE_DIR / "av_estimates" / f"{safe_filename(ticker)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and time.time() - path.stat().st_mtime < 86400:
        return json.loads(path.read_text(encoding="utf-8"))
    key = config.secret("ALPHAVANTAGE_API_KEY")
    if not key:
        raise ProviderError("ALPHAVANTAGE_API_KEY가 .env에 없습니다.")
    data = get("https://www.alphavantage.co/query",
               params={"function": "EARNINGS_ESTIMATES", "symbol": ticker, "apikey": key}).json()
    if "Information" in data or "Note" in data:
        raise ProviderError("Alpha Vantage 무료 호출 한도(하루 25회)에 도달했습니다.")
    out: dict[str, dict] = {}
    for e in data.get("estimates") or []:
        if e.get("horizon") != "fiscal quarter" or not e.get("date"):
            continue
        out[e["date"][:7]] = {
            "revenue": _f(e.get("revenue_estimate_average")), "revenue_low": _f(e.get("revenue_estimate_low")),
            "revenue_high": _f(e.get("revenue_estimate_high")), "eps": _f(e.get("eps_estimate_average")),
            "eps_low": _f(e.get("eps_estimate_low")), "eps_high": _f(e.get("eps_estimate_high")),
        }
    path.write_text(json.dumps(out), encoding="utf-8")
    return out
