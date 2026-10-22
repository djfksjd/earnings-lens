"""Finnhub: 미국 주식 실시간 시세(선택). 무료 키 분당 60회."""
from __future__ import annotations

from .. import config
from .http import ProviderError, get


def quote_us(ticker: str) -> dict:
    key = config.secret("FINNHUB_API_KEY")
    if not key:
        raise ProviderError("FINNHUB_API_KEY 없음")
    # 키는 쿼리 대신 헤더로 보낸다(로그·리퍼러에 덜 남는다)
    d = get("https://finnhub.io/api/v1/quote", params={"symbol": ticker}, headers={"X-Finnhub-Token": key}).json()
    if not d or not d.get("c"):
        raise ProviderError("Finnhub 시세 없음")
    return {"price": d["c"], "prev_close": d.get("pc"), "change_pct": d.get("dp"), "currency": "USD",
            "source": "Finnhub", "delay": "실시간"}
