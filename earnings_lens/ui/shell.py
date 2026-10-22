"""앱 셸: 아이콘 레일, 상단 바(종목·분기·실시간 가격), 플로팅 AI 코파일럿."""
from __future__ import annotations

import streamlit as st

from .. import ai, config, manual, service
from ..security import clean_ticker, esc
from . import components as c
from . import fmt

LOGO = '<div class="rail-logo" title="Earnings Lens" aria-label="Earnings Lens"><span></span></div>'


def rail(pages: list[st.Page], bottom: list[st.Page], current: st.Page) -> None:
    def link(p: st.Page) -> None:
        with st.container(key=f"nav_{p.url_path or 'home'}"):
            st.page_link(p, label=p.title, icon=p.icon, help=p.title)

    with st.container(key="rail"):
        st.html(LOGO)
        for p in pages:
            link(p)
        st.html('<div class="rail-sep"></div>')
        for p in bottom:
            link(p)
    # 현재 화면 아이콘을 잉크색 칩으로 표시
    cur = current.url_path or "home"
    st.html(f"<style>.st-key-nav_{cur} a {{ background: var(--ink) !important; }}"
            f".st-key-nav_{cur} a span[data-testid=stIconMaterial] {{ color: #fff !important; }}</style>")


def _on_ticker_change():
    raw = st.session_state.get("_ticker_box") or ""
    try:
        t = clean_ticker(raw)
    except ValueError as e:
        st.session_state["_ticker_error"] = str(e)
        return
    st.session_state.pop("_ticker_error", None)
    wl = manual.watchlist()
    if t not in wl:
        manual.save_watchlist(wl + [t])
    st.session_state["ticker"] = t
    st.query_params["t"] = t


def topbar() -> service.Report | None:
    wl = manual.watchlist()
    if "ticker" not in st.session_state:
        # 새로고침해도 종목이 유지되도록 주소의 ?t= 값을 먼저 본다
        try:
            st.session_state["ticker"] = clean_ticker(st.query_params.get("t", "")) if st.query_params.get("t") else wl[0]
        except ValueError:
            st.session_state["ticker"] = wl[0]
    st.query_params["t"] = st.session_state["ticker"]
    ticker = st.session_state["ticker"]
    options = wl if ticker in wl else [ticker] + wl

    with st.container(key="topbar"):
        cols = st.columns([2.6, 1.6, 1.2, 2.2], vertical_alignment="center")
        with cols[1]:
            st.selectbox("종목", options, index=options.index(ticker), key="_ticker_box", accept_new_options=True,
                         on_change=_on_ticker_change, placeholder="티커 입력 (NVDA, 005930.KS)",
                         help="목록에 없으면 티커를 입력하고 Enter. 6자리 숫자는 코스피(.KS)로 인식합니다.")
        with st.spinner("실적 불러오는 중…"):
            rep = service.build_report(ticker, st.session_state.get(f"period_{ticker}"))
        with cols[0]:
            sector = " · ".join(x for x in (rep.profile.sector, rep.profile.industry) if x)
            st.html(f'<div class="co-title"><b>{esc(rep.profile.name)}</b><span>{esc(ticker)}'
                    f'{(" · " + esc(sector)) if sector else ""}</span></div>')
        with cols[2]:
            periods = list(reversed(rep.fin.index.tolist()))
            if periods:
                st.selectbox("분기", periods, index=periods.index(rep.period) if rep.period in periods else 0,
                             key=f"period_{ticker}", format_func=lambda p: f"{service.period_label(p, rep.profile.fy_end_month)} · {p}")
        with cols[3]:
            price_pill(ticker)
    if st.session_state.get("_ticker_error"):
        st.warning(st.session_state["_ticker_error"])
    for w in rep.warnings:
        st.caption(f":material/warning: {w}")
    return rep


@st.fragment(run_every=config.PRICE_REFRESH_SECONDS)
def price_pill(ticker: str) -> None:
    q = service.get_quote(ticker)
    if not q.get("price"):
        st.html('<div class="price-pill"><small>시세를 가져오지 못했습니다</small></div>')
        return
    chg = q.get("change_pct")
    cls = "up" if chg and chg > 0 else "down" if chg and chg < 0 else ""
    live = q.get("delay") == "실시간"
    st.html(f'<div class="price-pill" title="{esc(q.get("source"))}"><b>{esc(fmt.price(q["price"], q.get("currency") or ""))}</b>'
            f'<span class="chg {cls}">{esc(fmt.pct(chg, 2))}</span>'
            f'<small><i class="live-dot {"" if live else "delayed"}"></i>{esc(q.get("source"))} · {esc(q.get("delay"))}</small></div>')


def copilot(rep: service.Report | None) -> None:
    ok, why = ai.available()
    with st.container(key="copilot"):
        with st.popover("Ask Lens", icon=":material/auto_awesome:"):
            st.html(f'<div class="empty">{c.orb(size="sm")}<div><b>Lens</b><br>'
                    f'<span class="card-sub">지금 보고 있는 종목·분기 데이터로만 답해요</span></div></div>')
            if not ok:
                st.info(why)
                return
            hist = st.session_state.setdefault("chat", [])
            for role, msg in hist[-8:]:
                if role == "user":
                    st.html(f'<div class="chat-msg user">{esc(msg)}</div>')
                else:
                    with st.container():
                        st.markdown(msg)  # 마크다운만 허용, HTML은 렌더링하지 않는다
            with st.form("ask", clear_on_submit=True, border=False):
                q = st.text_input("질문", placeholder="예: 이번 분기 영업이익이 컨센을 이긴 이유는?", label_visibility="collapsed")
                sent = st.form_submit_button("질문하기", type="primary", use_container_width=True)
            if sent and q.strip() and rep is not None:
                with st.spinner("Lens가 생각 중…"):
                    try:
                        answer = ai.ask(q.strip()[:1000], context_for(rep))
                    except ai.AIError as e:
                        answer = f"오류: {e}"
                hist += [("user", q.strip()), ("ai", answer)]
                st.rerun()


def context_for(rep: service.Report) -> dict:
    cur = rep.profile.currency
    return {
        "company": rep.profile.name, "ticker": rep.ticker, "period": rep.period, "currency": cur,
        "financials": {m: {k: rep.changes.at[m, k] for k in ("value", "prev_q", "prev_y", "qoq", "yoy")}
                       for m in rep.changes.index},
        "financials_source": rep.fin_src,
        "consensus": {m: {"value": v.value, "low": v.low, "high": v.high, "source": v.source} for m, v in rep.consensus.items()},
        "verdicts": {m: {"label": v.label, "diff_pct": v.diff_pct} for m, v in rep.verdicts.items()},
        "earnings_date": str(rep.event) if rep.event is not None else None,
        "price_reaction": service.price_reaction(rep)[0],
        "next_quarter_consensus": service.get_forward(rep.ticker).get("0q"),
        "inputs": rep.inputs,
    }
