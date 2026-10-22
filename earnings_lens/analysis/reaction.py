"""실적 발표 후 주가 반응."""
from __future__ import annotations

import pandas as pd


def reaction_session(event_ts: pd.Timestamp, index: pd.DatetimeIndex) -> int | None:
    """발표를 처음 반영한 거래일의 위치.

    장 마감 후(현지 16시 이후) 발표 → 다음 거래일, 장 전·장중 발표 → 당일.
    yfinance 일봉 인덱스는 거래소 현지 자정 기준이다.
    """
    if len(index) == 0:
        return None
    ts = pd.Timestamp(event_ts)
    tz = index.tz
    local = ts.tz_convert(tz) if ts.tzinfo and tz else ts.tz_localize(tz) if tz else ts
    day = local.normalize()
    after_close = local.hour >= 16 or (local.hour == 15 and local.minute >= 30 and str(tz).startswith("Asia/Seoul"))
    pos = index.searchsorted(day, side="right" if after_close else "left")
    return int(pos) if pos < len(index) else None


def compute(history: pd.DataFrame, event_ts, bench: pd.DataFrame | None = None) -> dict | None:
    """D(반응일) 종가/갭, D+5·D+20 누적, 벤치마크 대비 초과수익."""
    if history.empty:
        return None
    idx = history.index
    pos = reaction_session(pd.Timestamp(event_ts), idx)
    if pos is None or pos == 0:
        return None
    base = history["Close"].iloc[pos - 1]
    if pd.isna(base) or pd.isna(history["Close"].iloc[pos]):
        return None  # 빈 일봉(한국 yfinance는 당일 종가가 다음 날 채워진다)으로 계산하면 틀린 값이 나온다
    out = {
        "reaction_date": idx[pos].date().isoformat(),
        "base_close": float(base),
        "gap_pct": float(history["Open"].iloc[pos] / base - 1) * 100,
        "d1_pct": float(history["Close"].iloc[pos] / base - 1) * 100,
        "range_pct": float((history["High"].iloc[pos] - history["Low"].iloc[pos]) / base) * 100,
        "vol_x": float(history["Volume"].iloc[pos] / history["Volume"].iloc[max(0, pos - 20):pos].mean())
        if history["Volume"].iloc[max(0, pos - 20):pos].mean() else None,
    }
    for n in (5, 20):
        j = pos + n - 1
        out[f"d{n}_pct"] = float(history["Close"].iloc[j] / base - 1) * 100 if j < len(idx) and pd.notna(history["Close"].iloc[j]) else None
    if bench is not None and not bench.empty:
        b = bench["Close"].dropna()
        b_base = b[b.index < idx[pos]]
        b_day = b[b.index <= idx[pos]]
        # 지수 일봉이 빠진 날(yfinance ^KS11 실측)이면 기준일이 어긋나 초과수익이 틀린다. 날짜가 맞을 때만 계산
        same_day = lambda s, ts: len(s) and s.index[-1].date() == ts.date()  # noqa: E731
        if same_day(b_base, idx[pos - 1]) and same_day(b_day, idx[pos]):
            out["bench_d1_pct"] = float(b_day.iloc[-1] / b_base.iloc[-1] - 1) * 100
            out["excess_d1_pct"] = out["d1_pct"] - out["bench_d1_pct"]
    return out
