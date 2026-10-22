"""데이터 조립 계층: 여러 소스를 우선순위대로 합치고 Streamlit 캐시를 건다.

화면(views)은 이 모듈만 부른다. 각 함수는 (값, 출처/경고)를 함께 돌려줘 화면이 출처를 표시할 수 있게 한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

import pandas as pd
import streamlit as st

from . import config, manual
from .analysis import metrics, reaction, snapshots
from .providers import alphavantage, dart, finnhub, naver, sec, yf
from .providers.http import ProviderError


def is_kr(ticker: str) -> bool:
    return ticker.endswith((".KS", ".KQ"))


def benchmark(ticker: str) -> str:
    if ticker.endswith(".KQ"):
        return "^KQ11"
    return "^KS11" if is_kr(ticker) else "SPY"


def period_label(period: str, fy_end_month: int = 12) -> str:
    y, m = int(period[:4]), int(period[5:7])
    if fy_end_month == 12:
        return f"{(m - 1) // 3 + 1}Q{str(y)[2:]}"
    fq = alphavantage.fiscal_quarter(period, fy_end_month)
    return f"FY{fq[2:4]} Q{fq[-1]}"


# ---------------- 캐시된 원천 호출 ----------------

@st.cache_data(ttl=timedelta(hours=12), show_spinner=False)
def get_profile(ticker: str) -> yf.Profile:
    try:
        return yf.profile(ticker)
    except ProviderError:
        return yf.Profile(ticker, ticker, "KRW" if is_kr(ticker) else "USD", "", 12)


@st.cache_data(ttl=timedelta(seconds=config.PRICE_REFRESH_SECONDS), show_spinner=False)
def get_quote(ticker: str) -> dict:
    errors = []
    chain = []
    if is_kr(ticker) and config.NAVER_ENABLED:
        chain.append(naver.quote_kr)
    if not is_kr(ticker) and config.has("FINNHUB_API_KEY"):
        chain.append(finnhub.quote_us)
    chain.append(yf.quote)
    for fn in chain:
        try:
            q = fn(ticker)
            if q.get("price"):
                q["errors"] = errors
                return q
        except ProviderError as e:
            errors.append(str(e))
    return {"price": None, "errors": errors, "source": "", "delay": ""}


@st.cache_data(ttl=timedelta(hours=6), show_spinner=False)
def get_financials(ticker: str) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    """분기 실적 표, 지표별 출처, 경고."""
    warns: list[str] = []
    src: dict[str, str] = {}
    try:
        base = yf.quarterly_financials(ticker)
        src = {m: "yfinance" for m in base.columns}
    except ProviderError as e:
        base, src = pd.DataFrame(columns=yf.METRICS), {}
        warns.append(str(e))

    if is_kr(ticker):
        kr = None
        if config.has("DART_API_KEY"):
            try:
                kr, label = dart.quarterly_financials(ticker), "DART"
            except ProviderError as e:
                warns.append(f"DART: {e}")
        if (kr is None or kr.empty) and config.NAVER_ENABLED:
            try:
                df, cons = naver.quarterly_with_consensus(ticker)
                kr, label = df.drop(index=list(cons), errors="ignore"), "네이버"
            except ProviderError as e:
                warns.append(f"네이버: {e}")
        if kr is not None and not kr.empty:
            # 공식 값으로 덮어쓰되, 공식 소스에 없는 지표(EBITDA 등)는 yfinance 값을 유지
            merged = kr.combine_first(base) if not base.empty else kr
            for m in kr.columns:
                src[m] = label
            base = merged.reindex(columns=yf.METRICS)
    return base.sort_index(), src, warns


@st.cache_data(ttl=timedelta(hours=6), show_spinner=False)
def get_eps_history(ticker: str) -> pd.DataFrame:
    try:
        return yf.eps_history(ticker)
    except ProviderError:
        return pd.DataFrame()


@st.cache_data(ttl=timedelta(hours=6), show_spinner=False)
def get_earnings_dates(ticker: str) -> pd.DataFrame:
    try:
        return yf.earnings_dates(ticker, limit=16)
    except ProviderError:
        return pd.DataFrame()


@st.cache_data(ttl=timedelta(hours=3), show_spinner=False)
def get_forward(ticker: str) -> dict:
    try:
        return yf.forward_estimates(ticker)
    except ProviderError:
        return {}


@st.cache_data(ttl=timedelta(hours=6), show_spinner=False)
def get_av_estimates(ticker: str) -> dict:
    if is_kr(ticker) or not config.has("ALPHAVANTAGE_API_KEY"):
        return {}
    try:
        return alphavantage.estimates(ticker)
    except ProviderError:
        return {}


@st.cache_data(ttl=timedelta(hours=6), show_spinner=False)
def get_naver_consensus(ticker: str) -> tuple[pd.DataFrame, set]:
    if not (is_kr(ticker) and config.NAVER_ENABLED):
        return pd.DataFrame(), set()
    try:
        return naver.quarterly_with_consensus(ticker)
    except ProviderError:
        return pd.DataFrame(), set()


@st.cache_data(ttl=timedelta(hours=6), show_spinner=False)
def get_naver_integration(ticker: str) -> dict:
    if not (is_kr(ticker) and config.NAVER_ENABLED):
        return {}
    try:
        return naver.integration(ticker)
    except ProviderError:
        return {}


@st.cache_data(ttl=timedelta(minutes=30), show_spinner=False)
def get_history(ticker: str, start: str) -> pd.DataFrame:
    try:
        return yf.history(ticker, start=start)
    except ProviderError:
        return pd.DataFrame()


@st.cache_data(ttl=timedelta(hours=6), show_spinner=False)
def get_disclosures(ticker: str) -> tuple[list[dict], str]:
    if is_kr(ticker):
        if not config.has("DART_API_KEY"):
            return [], "DART_API_KEY를 등록하면 공시 목록이 보입니다."
        try:
            return dart.disclosures(ticker), ""
        except ProviderError as e:
            return [], str(e)
    try:
        out = []
        for f in sec.earnings_filings(ticker, limit=4):
            for ex in sec.exhibits(f):
                desc = ex["description"] if ex["description"].upper() != ex["type"] else ""
                label = {"EX-99.1": "실적 보도자료", "EX-99.2": "추가 자료(CFO 코멘터리 등)"}.get(ex["type"], ex["type"])
                out.append({"date": f["date"], "title": f"{label} · {ex['type']}{(' ' + desc) if desc else ''}", "url": ex["url"]})
        return out, ""
    except ProviderError as e:
        return [], str(e)


@st.cache_data(ttl=timedelta(hours=12), show_spinner=False)
def get_news(ticker: str) -> list[dict]:
    try:
        return yf.recent_news(ticker)
    except ProviderError:
        return []


# ---------------- 조립 ----------------

def event_for(ticker: str, period: str) -> pd.Timestamp | None:
    """분기말 이후 첫 실적 발표 일시."""
    ed = get_earnings_dates(ticker)
    if ed.empty:
        return None
    end = pd.Timestamp(period + "-01") + pd.offsets.MonthEnd(0)
    cands = [ts for ts in ed.index if end.date() <= ts.date() <= (end + pd.Timedelta(days=110)).date()]
    return min(cands) if cands else None


def record_snapshots(ticker: str, last_period: str | None) -> None:
    """다음 분기 컨센서스를 오늘 날짜로 저장(하루 1회)."""
    fwd = get_forward(ticker)
    if last_period and fwd.get("0q"):
        nxt = metrics.prev_period(last_period, -3)
        d = fwd["0q"]
        snapshots.record(ticker, nxt, {
            "revenue": d.get("rev_avg"), "revenue_low": d.get("rev_low"), "revenue_high": d.get("rev_high"),
            "eps": d.get("eps_avg"), "eps_low": d.get("eps_low"), "eps_high": d.get("eps_high")}, "yfinance")
    df, cons = get_naver_consensus(ticker)
    for p in cons:
        if p in df.index:
            snapshots.record(ticker, p, {k: df.at[p, k] for k in df.columns if pd.notna(df.at[p, k])}, "네이버")


@dataclass
class Consensus:
    value: float | None = None
    low: float | None = None
    high: float | None = None
    source: str = ""


@dataclass
class Report:
    ticker: str
    period: str
    profile: yf.Profile
    fin: pd.DataFrame
    fin_src: dict
    changes: pd.DataFrame
    consensus: dict[str, Consensus] = field(default_factory=dict)
    verdicts: dict[str, metrics.Verdict] = field(default_factory=dict)
    event: pd.Timestamp | None = None
    inputs: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    actuals: dict = field(default_factory=dict)  # 컨센서스 판정에 쓴 실제값(추정치와 같은 기준)


def consensus_for(ticker: str, period: str, event: pd.Timestamp | None, inputs: dict) -> dict[str, Consensus]:
    out: dict[str, Consensus] = {m: Consensus() for m in ("revenue", "operating_income", "ebitda", "eps")}
    snap = snapshots.latest_before(ticker, period, event.date().isoformat() if event is not None else None)
    for m in out:
        if m in snap:
            out[m] = Consensus(snap[m]["value"], snap.get(f"{m}_low", {}).get("value"),
                               snap.get(f"{m}_high", {}).get("value"), f"스냅샷 {snap[m]['date']} · {snap[m]['source']}")
    av = get_av_estimates(ticker).get(period) or {}
    for m in ("revenue", "eps"):
        if out[m].value is None and av.get(m) is not None:
            out[m] = Consensus(av[m], av.get(f"{m}_low"), av.get(f"{m}_high"), "Alpha Vantage")
    eh = get_eps_history(ticker)
    if out["eps"].value is None and not eh.empty and period in eh.index and pd.notna(eh.at[period, "eps_estimate"]):
        out["eps"] = Consensus(float(eh.at[period, "eps_estimate"]), source="yfinance")
    mine = inputs.get("consensus") or {}
    src_label = inputs.get("_source", {}).get("consensus", "내 입력")
    for m in out:
        v = manual.parse_amount(mine.get(m))
        if v is not None:
            out[m] = Consensus(v, manual.parse_amount(mine.get(f"{m}_low")), manual.parse_amount(mine.get(f"{m}_high")),
                               f"{src_label}" + (f" · {mine['source']}" if mine.get("source") else ""))
    return out


def build_report(ticker: str, period: str | None = None) -> Report:
    prof = get_profile(ticker)
    fin, src, warns = get_financials(ticker)
    periods = list(fin.index)
    if not periods:
        return Report(ticker, period or "", prof, fin, src, pd.DataFrame(), warnings=warns + ["분기 실적 데이터를 찾지 못했습니다."])
    period = period if period in periods else periods[-1]
    record_snapshots(ticker, periods[-1])
    inputs = manual.merged(ticker, period)
    fin = fin.copy()
    for m, v in (inputs.get("actual_override") or {}).items():
        val = manual.parse_amount(v)
        if m in fin.columns and val is not None:
            fin.at[period, m] = val
            src[m] = inputs["_source"]["actual_override"]
    eh = get_eps_history(ticker)
    if period in eh.index and pd.notna(eh.at[period, "eps_actual"]) and src.get("eps") == "yfinance":
        # 컨센서스와 같은 기준(조정 EPS)으로 비교한다. QoQ/YoY도 같은 기준이어야 하므로
        # 조정 EPS가 있는 모든 분기를 바꾸고, 없는 분기는 비워 GAAP과 섞이지 않게 한다.
        adj = eh["eps_actual"].reindex(fin.index).astype(float)
        # earnings_history는 최근 4개 분기뿐이라 발표일 표(최대 수년치)로 빈 분기를 채운다
        ed = get_earnings_dates(ticker)
        for ts, row in ed[ed["eps_actual"].notna()].iterrows() if not ed.empty else []:
            day = ts.tz_localize(None) if ts.tzinfo else ts
            for p in fin.index:
                end = pd.Timestamp(p + "-01") + pd.offsets.MonthEnd(0)
                if pd.isna(adj.get(p)) and pd.Timedelta(days=0) < day - end <= pd.Timedelta(days=100):
                    adj[p] = float(row["eps_actual"])
        fin["eps"] = adj
        src["eps"] = "yfinance(조정 EPS)"
    changes = metrics.change_table(fin, period)
    event = event_for(ticker, period)
    cons = consensus_for(ticker, period, event, inputs)
    actual = {m: changes.at[m, "value"] if m in changes.index else None for m in cons}
    if cons["eps"].source == "yfinance" and period in eh.index and pd.notna(eh.at[period, "eps_actual"]):
        actual["eps"] = float(eh.at[period, "eps_actual"])  # 추정치와 같은 소스의 실제 EPS로 판정
    verdicts = {m: metrics.verdict(actual[m], c.value) for m, c in cons.items()}
    return Report(ticker, period, prof, fin, src, changes, cons, verdicts, event, inputs, warns, actual)


def price_reaction(rep: Report) -> tuple[dict | None, pd.DataFrame, pd.DataFrame]:
    start = (pd.Timestamp(rep.period + "-01") - pd.Timedelta(days=45)).date().isoformat()
    h = get_history(rep.ticker, start)
    b = get_history(benchmark(rep.ticker), start)
    if rep.event is None or h.empty:
        return None, h, b
    return reaction.compute(h, rep.event, b), h, b


def reaction_history(ticker: str) -> pd.DataFrame:
    """과거 8개 분기 발표 반응(D+1)과 EPS 서프라이즈."""
    ed = get_earnings_dates(ticker)
    if ed.empty:
        return pd.DataFrame()
    past = ed[ed["eps_actual"].notna()].sort_index().tail(8)
    if past.empty:
        return pd.DataFrame()
    start = (past.index.min() - pd.Timedelta(days=10)).date().isoformat()
    h = get_history(ticker, start)
    b = get_history(benchmark(ticker), start)
    rows = []
    for ts, row in past.iterrows():
        r = reaction.compute(h, ts, b)
        if r:
            rows.append({"발표일": ts.date().isoformat(), "EPS 서프라이즈(%)": row["surprise_pct"],
                         "D+1(%)": r["d1_pct"], "갭(%)": r["gap_pct"], "D+5(%)": r.get("d5_pct"),
                         "시장 대비 D+1(%p)": r.get("excess_d1_pct")})
    return pd.DataFrame(rows)


def transcript_for(rep: Report) -> tuple[str | None, str, list[dict]]:
    """(원문 텍스트, 출처, 발언 목록[감성 포함]) — 직접 붙여넣은 원문 > Alpha Vantage 캐시."""
    text = manual.transcript_text(rep.ticker, rep.period)
    if text:
        return text, "직접 입력", []
    if is_kr(rep.ticker):
        return None, "", []
    fq = alphavantage.fiscal_quarter(rep.period, rep.profile.fy_end_month)
    path = config.CACHE_DIR / "transcripts" / f"{rep.ticker.replace('.', '_')}_{fq}.json"
    if path.exists():
        turns = alphavantage.transcript(rep.ticker, fq)
        return turns_to_text(turns), "Alpha Vantage", turns
    return None, "", []


def turns_to_text(turns: list[dict]) -> str:
    return "\n\n".join(f"[{t['speaker']} — {t['title']}]\n{t['content']}" for t in turns)
