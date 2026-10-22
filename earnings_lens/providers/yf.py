"""yfinance: 키 없이 쓰는 기본 데이터 소스 (미국·한국 공통)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from ..security import redact
from .http import ProviderError

METRICS = ("revenue", "operating_income", "ebitda", "eps", "net_income")

# yfinance 손익계산서 행 이름 → 내부 키 (앞쪽이 우선)
_ROWS = {
    "revenue": ("Total Revenue", "Operating Revenue"),
    "operating_income": ("Operating Income", "Total Operating Income As Reported"),
    "ebitda": ("EBITDA", "Normalized EBITDA"),
    "eps": ("Diluted EPS", "Basic EPS"),
    "net_income": ("Net Income Common Stockholders", "Net Income"),
}


def period_key(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m")


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def _wrap(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:  # yfinance는 다양한 예외를 던진다
        raise ProviderError(redact(f"yfinance: {type(e).__name__}: {e}")) from None


@dataclass
class Profile:
    ticker: str
    name: str
    currency: str
    exchange: str
    fy_end_month: int
    sector: str = ""
    industry: str = ""
    website: str = ""


def profile(ticker: str) -> Profile:
    t = yf.Ticker(ticker)
    info = _wrap(lambda: t.info) or {}
    fy_end = info.get("lastFiscalYearEnd")
    month = datetime.fromtimestamp(fy_end, tz=timezone.utc).month if fy_end else 12
    return Profile(
        ticker=ticker,
        name=info.get("longName") or info.get("shortName") or ticker,
        currency=info.get("financialCurrency") or info.get("currency") or "",
        exchange=info.get("exchange") or "",
        fy_end_month=month,
        sector=info.get("sector") or "",
        industry=info.get("industry") or "",
        website=info.get("website") or "",
    )


def _quote_kr(ticker: str) -> dict | None:
    """한국: fast_info는 전일 종가·현재가가 하루 이상 밀려 있을 때가 있다(실측 2026-10-22).
    1분봉 마지막 체결가와, 그 날짜 이전의 마지막 확정 일봉 종가로 다시 계산한다."""
    t = yf.Ticker(ticker)
    m = _wrap(lambda: t.history(period="5d", interval="1m", auto_adjust=False))
    if m is None or m.empty or m["Close"].dropna().empty:
        return None
    m = m[m["Close"].notna()]
    ts, last = m.index[-1], _num(m["Close"].iloc[-1])
    d = _wrap(lambda: t.history(period="15d", interval="1d", auto_adjust=False))
    closes = d["Close"].dropna() if d is not None and not d.empty else pd.Series(dtype=float)
    closes = closes[[i.date() < ts.date() for i in closes.index]]
    prev = _num(closes.iloc[-1]) if len(closes) else None
    return {
        "price": last,
        "prev_close": prev,
        "change_pct": (last / prev - 1) * 100 if last and prev else None,
        "currency": "KRW",
        "source": "yfinance",
        "delay": "최대 15~20분 지연 · 장 마감 동시호가 미반영",
        "asof": ts.isoformat(),
    }


def quote(ticker: str) -> dict:
    if ticker.endswith((".KS", ".KQ")):
        q = _quote_kr(ticker)
        if q:
            return q
    fi = _wrap(lambda: yf.Ticker(ticker).fast_info)
    last = _num(_wrap(lambda: fi.last_price))
    prev = _num(_wrap(lambda: fi.previous_close))
    return {
        "price": last,
        "prev_close": prev,
        "change_pct": (last / prev - 1) * 100 if last and prev else None,
        "currency": _wrap(lambda: fi.currency),
        "source": "yfinance",
        "delay": "최대 15~20분 지연" if ticker.endswith((".KS", ".KQ")) else "준실시간(장중 수 초~분)",
        "asof": datetime.now(timezone.utc).isoformat(),
    }


def quarterly_financials(ticker: str) -> pd.DataFrame:
    """분기 손익. index=분기말(YYYY-MM), 오름차순. 최근 약 5~6개 분기만 제공된다."""
    q = _wrap(lambda: yf.Ticker(ticker).quarterly_income_stmt)
    if q is None or q.empty:
        return pd.DataFrame(columns=METRICS)
    out = {}
    for col in q.columns:
        row = {}
        for key, names in _ROWS.items():
            row[key] = next((_num(q.at[n, col]) for n in names if n in q.index and _num(q.at[n, col]) is not None), None)
        out[period_key(col)] = row
    df = pd.DataFrame.from_dict(out, orient="index").reindex(columns=METRICS).sort_index()
    return df.dropna(how="all")


def eps_history(ticker: str) -> pd.DataFrame:
    """과거 분기 EPS 실제 vs 추정. index=분기말(YYYY-MM)."""
    eh = _wrap(lambda: yf.Ticker(ticker).earnings_history)
    if eh is None or eh.empty:
        return pd.DataFrame(columns=["eps_actual", "eps_estimate", "surprise_pct"])
    df = pd.DataFrame({
        "eps_actual": eh["epsActual"].map(_num),
        "eps_estimate": eh["epsEstimate"].map(_num),
        "surprise_pct": eh["surprisePercent"].map(lambda v: _num(v) * 100 if _num(v) is not None else None),
    })
    df.index = [period_key(i) for i in eh.index]
    return df.sort_index()


def earnings_dates(ticker: str, limit: int = 16) -> pd.DataFrame:
    """발표 일시(타임존 포함)와 EPS 추정/실적. 최신순."""
    ed = _wrap(lambda: yf.Ticker(ticker).get_earnings_dates(limit=limit))
    if ed is None or ed.empty:
        return pd.DataFrame(columns=["eps_estimate", "eps_actual", "surprise_pct"])
    ed = ed.rename(columns={"EPS Estimate": "eps_estimate", "Reported EPS": "eps_actual", "Surprise(%)": "surprise_pct"})
    return ed[["eps_estimate", "eps_actual", "surprise_pct"]]


def forward_estimates(ticker: str) -> dict:
    """다음 발표 분기(0q)·다음다음 분기(+1q) 컨센서스."""
    t = yf.Ticker(ticker)
    out: dict = {}
    ee = _wrap(lambda: t.earnings_estimate)
    re_ = _wrap(lambda: t.revenue_estimate)
    for per in ("0q", "+1q"):
        d = {}
        if ee is not None and per in ee.index:
            d.update(eps_avg=_num(ee.at[per, "avg"]), eps_low=_num(ee.at[per, "low"]),
                     eps_high=_num(ee.at[per, "high"]), eps_n=_num(ee.at[per, "numberOfAnalysts"]))
        if re_ is not None and per in re_.index:
            d.update(rev_avg=_num(re_.at[per, "avg"]), rev_low=_num(re_.at[per, "low"]),
                     rev_high=_num(re_.at[per, "high"]), rev_n=_num(re_.at[per, "numberOfAnalysts"]))
        out[per] = d
    cal = _wrap(lambda: t.calendar) or {}
    dates = cal.get("Earnings Date") or []
    out["next_date"] = str(dates[0]) if dates else None
    return out


def history(ticker: str, start: str, end: str | None = None, interval: str = "1d") -> pd.DataFrame:
    h = _wrap(lambda: yf.Ticker(ticker).history(start=start, end=end, interval=interval, auto_adjust=False))
    if h is None or h.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    return h[["Open", "High", "Low", "Close", "Volume"]]


def recent_news(ticker: str, n: int = 8) -> list[dict]:
    items = _wrap(lambda: yf.Ticker(ticker).news) or []
    out = []
    for it in items[:n]:
        c = it.get("content", it)
        url = (c.get("canonicalUrl") or {}).get("url") or c.get("link") or ""
        out.append({"title": c.get("title", ""), "publisher": (c.get("provider") or {}).get("displayName", ""),
                    "date": c.get("pubDate", ""), "url": url if url.startswith("https://") else ""})
    return out
