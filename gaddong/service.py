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
from .providers import alphavantage, dart, finnhub, fool, krx, marketbeat, naver, sec, yf
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

    if not is_kr(ticker) and config.SEC_USER_AGENT and not base.empty:
        _fill_from_sec(ticker, base, src, warns)
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
            if label == "DART":
                kr = _with_dart_ebitda(ticker, kr, base, src, warns)
            # 공식 값으로 덮어쓰되, 공식 소스에 없는 지표는 yfinance 값을 유지
            merged = kr.combine_first(base) if not base.empty else kr
            for m in kr.columns:
                if m != "ebitda":
                    src[m] = label
            base = merged.reindex(columns=yf.METRICS)
    return base.sort_index(), src, warns


def _fill_from_sec(ticker: str, base: pd.DataFrame, src: dict, warns: list) -> None:
    """yfinance가 최근 분기 매출·영업이익·순이익을 비워 줄 때가 있다(AMZN 2026-06 실측). 그 칸만 10-Q/10-K 원본으로 채운다."""
    keys = ("revenue", "operating_income", "net_income")
    gaps = [p for p in list(base.index)[-3:] if base.loc[p, list(keys)].isna().any()]
    if not gaps:
        return
    try:
        totals = sec.quarterly_totals(ticker, gaps)
    except (ProviderError, ValueError, KeyError) as e:
        warns.append(f"SEC 보완: {e}")
        return
    for p, vals in totals.items():
        for k, v in vals.items():
            if pd.isna(base.at[p, k]):
                base.at[p, k] = v
                src[k] = f"{src.get(k, 'yfinance')} + SEC(빈 분기)" if "SEC" not in src.get(k, "") else src[k]


def _with_dart_ebitda(ticker: str, kr: pd.DataFrame, base: pd.DataFrame, src: dict, warns: list) -> pd.DataFrame:
    """EBITDA = DART 영업이익 + 감가상각비·무형자산상각비(XBRL 주석).

    yfinance의 한국 EBITDA는 영업이익과 같은 값이 들어오는 등 믿기 어렵다. 공시로 계산되면 그 값만 쓰고,
    전혀 계산되지 않을 때만 yfinance 값을 쓰되 영업이익보다 크지 않은 값(감가상각 0)은 버린다."""
    kr = kr.copy()
    try:
        da = dart.quarterly_da(ticker, list(kr.index)[-8:])
    except (ProviderError, ValueError) as e:
        warns.append(f"DART 감가상각비: {e}")
        da = {}
    if da:
        kr["ebitda"] = [kr.at[p, "operating_income"] + da[p] if p in da and pd.notna(kr.at[p, "operating_income"]) else None
                        for p in kr.index]
        src["ebitda"] = "DART(영업이익+상각비)"
        if "ebitda" in base.columns:
            base["ebitda"] = None  # 계산 못 한 분기에 기준이 다른 yfinance 값이 섞이지 않게
        return kr
    if "ebitda" in base.columns and "operating_income" in kr.columns:
        oi = kr["operating_income"].reindex(base.index)
        bad = base["ebitda"].notna() & oi.notna() & (base["ebitda"] <= oi)
        if bad.any():
            base.loc[bad, "ebitda"] = None
            warns.append("yfinance EBITDA 중 영업이익 이하인 값(감가상각 누락)을 지웠습니다.")
    return kr


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
    """일봉. 한국은 yfinance의 빈 날(당일 종가 NaN, 지수 일봉 누락)을 KRX 공식 값으로 채운다.
    KRX를 못 쓰면 빈 날을 그대로 두고, 반응 계산이 그 날을 건너뛰지 않고 '—'로 표시한다."""
    try:
        h = yf.history(ticker, start=start)
    except ProviderError:
        h = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    if (is_kr(ticker) or ticker in ("^KS11", "^KQ11")) and krx.available():
        try:
            h, _ = krx.fill_gaps(h, ticker, pd.Timestamp(start).date())
        except ProviderError:
            pass  # 승인 전(401)·장애: yfinance 값만 쓴다
    return h


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
def get_segments(ticker: str, period: str) -> tuple[list[dict], str, str]:
    """공시 XBRL의 사업부문 표. (행, 출처 라벨, 안내/오류)."""
    try:
        if is_kr(ticker):
            if not config.has("DART_API_KEY"):
                return [], "", "DART_API_KEY를 등록하면 사업부문이 자동으로 채워져요."
            rows, axes = dart.segments(ticker, period)
            label = "DART XBRL"
        else:
            rows, axes = sec.segments(ticker, period)
            label = "SEC XBRL"
    except (ProviderError, ValueError, KeyError) as e:
        return [], "", str(e)
    return rows, f"{label} · {axes}" if rows else "", ""


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
    mb = _marketbeat_row(ticker, period, event)  # 옵트인. 위 소스가 비었을 때만
    for m, key in (("revenue", "revenue_est"), ("eps", "eps_est")):
        if out[m].value is None and mb.get(key) is not None:
            out[m] = Consensus(mb[key], source="MarketBeat")
    mine = inputs.get("consensus") or {}
    src_label = inputs.get("_source", {}).get("consensus", "내 입력")
    for m in out:
        v = manual.parse_amount(mine.get(m))
        if v is not None:
            out[m] = Consensus(v, manual.parse_amount(mine.get(f"{m}_low")), manual.parse_amount(mine.get(f"{m}_high")),
                               f"{src_label}" + (f" · {mine['source']}" if mine.get("source") else ""))
    return out


@st.cache_data(ttl=timedelta(hours=12), show_spinner=False)
def get_marketbeat(ticker: str) -> list[dict]:
    if is_kr(ticker) or not config.MARKETBEAT_ENABLED:
        return []
    try:
        return marketbeat.history(ticker)
    except ProviderError:
        return []


def _marketbeat_row(ticker: str, period: str, event: pd.Timestamp | None) -> dict:
    """분기말 이후 100일 안에 발표된 행. 발표일을 알면 ±3일로 더 좁힌다."""
    end = pd.Timestamp(period + "-01") + pd.offsets.MonthEnd(0)
    rows = [r for r in get_marketbeat(ticker) if pd.Timedelta(0) < pd.Timestamp(r["date"]) - end <= pd.Timedelta(days=100)]
    if event is not None:
        ev = event.tz_convert(None) if event.tzinfo else event
        near = [r for r in rows if abs((pd.Timestamp(r["date"]) - ev.normalize()).days) <= 3]
        rows = near or rows
    return rows[0] if rows else {}


def build_report(ticker: str, period: str | None = None) -> Report:
    prof = get_profile(ticker)
    fin, src, warns = get_financials(ticker)
    periods = list(fin.index)
    if not periods:
        return Report(ticker, period or "", prof, fin, src, pd.DataFrame(), warnings=warns + ["분기 실적 데이터를 찾지 못했습니다."])
    period = period if period in periods else periods[-1]
    record_snapshots(ticker, periods[-1])
    inputs = manual.merged(ticker, period)
    _apply_xbrl_segments(ticker, period, fin, inputs, warns)
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


def _apply_xbrl_segments(ticker: str, period: str, fin: pd.DataFrame, inputs: dict, warns: list) -> None:
    """내 입력이 없으면 공시 XBRL 부문으로 채운다. AI 추출보다 우선(공식 숫자). AI가 단 부문 코멘트는 살린다."""
    if inputs.get("_source", {}).get("segments") == "내 입력":
        return
    rows, label, err = get_segments(ticker, period)
    if not rows:
        if err and "SEC_USER_AGENT" in err:
            warns.append(err)
        return
    total = fin.at[period, "revenue"] if period in fin.index and "revenue" in fin.columns else None
    seg_sum = sum(r["revenue"] or 0 for r in rows)
    if total and pd.notna(total) and seg_sum > total * 1.6:
        warns.append(f"공시 부문 합계가 전사 매출의 {seg_sum / total:.1f}배라 자동 부문을 쓰지 않았어요(중복 태깅 의심).")
        return
    notes = {_seg_key(s.get("name")): s.get("note") for s in inputs.get("segments") or [] if s.get("note")}
    for r in rows:
        if notes.get(_seg_key(r["name"])):
            r["note"] = notes[_seg_key(r["name"])]
    inputs["segments"] = rows
    inputs.setdefault("_source", {})["segments"] = f"자동 · {label}"


def _seg_key(name) -> str:
    return "".join(str(name or "").lower().split()).replace("segment", "").replace("부문", "")


def price_reaction(rep: Report) -> tuple[dict | None, pd.DataFrame, pd.DataFrame]:
    start = (pd.Timestamp(rep.period + "-01") - pd.Timedelta(days=45)).date().isoformat()
    h = get_history(rep.ticker, start)
    b = get_history(benchmark(rep.ticker), start)
    if rep.event is None or h.empty:
        return None, h, b
    rx = reaction.compute(h, rep.event, b)
    # 지난 분기를 볼 때 차트가 오늘까지 늘어나 발표 시점이 왼쪽 끝에 몰리지 않게 발표 후 120일까지만 보여준다
    end = (rep.event.tz_convert(None) if rep.event.tzinfo else rep.event) + pd.Timedelta(days=120)
    return rx, _until(h, end), _until(b, end)


def _until(df: pd.DataFrame, end: pd.Timestamp) -> pd.DataFrame:
    if df.empty:
        return df
    idx = df.index.tz_convert(None) if df.index.tz is not None else df.index
    return df[idx <= end]


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
    turns = fool.cached(rep.ticker, fq)
    if turns:
        return turns_to_text(turns), "Motley Fool", turns
    return None, "", []


def turns_to_text(turns: list[dict]) -> str:
    return "\n\n".join(f"[{t['speaker']}" + (f" — {t['title']}" if t.get("title") else "") + f"]\n{t['content']}" for t in turns)

