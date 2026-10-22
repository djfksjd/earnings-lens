"""네이버 증권 룰베이스 수집 (옵트인).

네이버 증권은 robots.txt로 자동 수집을 막고 있고, 이용약관도 무단 수집을 제한할 수 있다.
그래서 `.env`에 NAVER_SCRAPING_ENABLED=true를 직접 넣었을 때만 동작한다.
개인 학습 용도로 종목당 몇 번만 호출하고, 결과는 캐시한다.
"""
from __future__ import annotations

import pandas as pd

from .. import config
from .http import ProviderError, get

_UA = {"User-Agent": "Mozilla/5.0 (personal research; gaddong)", "Referer": "https://m.stock.naver.com/"}
UNIT = 1e8  # 재무 수치 단위: 억원


def _code(ticker: str) -> str:
    return ticker.split(".")[0]


def _require():
    if not config.NAVER_ENABLED:
        raise ProviderError("네이버 수집이 꺼져 있습니다(.env의 NAVER_SCRAPING_ENABLED).")


def _f(v):
    if v in (None, "", "-", "N/A"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def quote_kr(ticker: str) -> dict:
    _require()
    r = get(f"https://polling.finance.naver.com/api/realtime/domestic/stock/{_code(ticker)}", headers=_UA)
    d = (r.json().get("datas") or [{}])[0]
    price = _f(d.get("closePrice"))
    chg = _f(d.get("compareToPreviousClosePrice"))
    return {
        "price": price,
        "prev_close": price - chg if price is not None and chg is not None else None,
        "change_pct": _f(d.get("fluctuationsRatio")),
        "currency": "KRW",
        "source": "네이버 증권",
        "delay": "실시간",
        "market_status": d.get("marketStatus", ""),
    }


def quarterly_with_consensus(ticker: str) -> tuple[pd.DataFrame, set[str]]:
    """분기 매출·영업이익·순이익·EPS(원 단위로 환산). 두 번째 값은 컨센서스(E) 분기 키 목록."""
    _require()
    r = get(f"https://m.stock.naver.com/api/stock/{_code(ticker)}/finance/quarter", headers=_UA)
    info = r.json().get("financeInfo") or {}
    cols = info.get("trTitleList") or []
    keys = {c["key"]: f'{c["key"][:4]}-{c["key"][4:6]}' for c in cols}
    consensus = {keys[c["key"]] for c in cols if c.get("isConsensus") == "Y"}
    want = {"매출액": "revenue", "영업이익": "operating_income", "당기순이익": "net_income", "EPS": "eps"}
    rows: dict[str, dict] = {p: {} for p in keys.values()}
    for row in info.get("rowList") or []:
        k = want.get(row.get("title"))
        if not k:
            continue
        for raw_key, cell in (row.get("columns") or {}).items():
            v = _f((cell or {}).get("value"))
            if raw_key in keys and v is not None:
                rows[keys[raw_key]][k] = v if k == "eps" else v * UNIT
    df = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    return df, consensus


def integration(ticker: str) -> dict:
    """목표주가 평균·투자의견, IR 일정, 최근 리서치 제목."""
    _require()
    d = get(f"https://m.stock.naver.com/api/stock/{_code(ticker)}/integration", headers=_UA).json()
    ci = d.get("consensusInfo") or {}
    researches = [{"title": x.get("tit") or x.get("title", ""), "broker": x.get("bnm") or x.get("brokerName", ""),
                   "date": x.get("wdt") or x.get("writeDate", "")} for x in (d.get("researches") or [])[:6]]
    ir = d.get("irScheduleInfo") or {}
    return {
        "target_price": _f(ci.get("priceTargetMean")),
        "recomm_mean": _f(ci.get("recommMean")),
        "consensus_date": ci.get("createDate"),
        "researches": researches,
        "ir_schedule": ir if isinstance(ir, (dict, list)) else {},
    }
