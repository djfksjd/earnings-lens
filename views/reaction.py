"""주가 반응: 이번 분기와 과거 발표 패턴."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from gaddong import service
from gaddong.ui import components as c
from gaddong.ui import fmt
from views import _common as k


def render() -> None:
    r = k.rep()
    if r is None:
        return
    c.page_title("주가 반응", f"{r.profile.name} · 발표 전후 가격과 시장({service.benchmark(r.ticker)}) 대비")
    rx, h, b = service.price_reaction(r)
    cols = st.columns(5)
    stats = [("반응일 수익률", rx and rx["d1_pct"]), ("시가 갭", rx and rx["gap_pct"]), ("D+5 누적", rx and rx.get("d5_pct")),
             ("D+20 누적", rx and rx.get("d20_pct")), ("시장 대비 초과", rx and rx.get("excess_d1_pct"))]
    for i, (label, v) in enumerate(stats):
        cls = "up" if v and v > 0 else "down" if v and v < 0 else "flat"
        with cols[i]:
            c.show(f'<div class="el-card stat" style="--i:{i}"><span class="label">{label}</span>'
                   f'<div class="value {cls}" style="font-size:1.6rem">{fmt.pct(v) if v is not None else "—"}</div>'
                   f'<span class="card-sub">{"거래량 " + format(rx["vol_x"], ".1f") + "배" if rx and rx.get("vol_x") and i == 0 else ""}</span></div>')
    st.write("")
    with st.container(key="card_price"):
        sub = f"반응일 {rx['reaction_date']} · 점선 = 발표 시점" if rx else "발표일 정보가 없거나 아직 반응 데이터가 없어요"
        c.show(c.card_head("발표 전후 가격 (정규화 100)", sub=sub, source="자동 · yfinance"))
        if not h.empty:
            base = h["Close"].iloc[0]
            fig = go.Figure()
            fig.add_scatter(x=h.index, y=h["Close"] / base * 100, name=r.ticker, line=dict(color=c.ACCENT, width=2.6))
            if not b.empty:
                bb = b["Close"][b.index >= h.index[0]]
                if len(bb):
                    fig.add_scatter(x=bb.index, y=bb / bb.iloc[0] * 100, name=service.benchmark(r.ticker), line=dict(color="#A3A8B6", width=1.8))
            if r.event is not None:
                fig.add_vline(x=r.event.tz_convert(h.index.tz) if h.index.tz else r.event, line_dash="dot", line_color=c.INK,
                              annotation_text="실적 발표", annotation_position="top left")
            fig.update_xaxes(tickformat="%Y.%m")
            c.plot_layout(fig, 360)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.write("")
    hist = service.reaction_history(r.ticker)
    left, right = st.columns([3, 2])
    with left:
        if hist.empty:
            c.show(c.card("과거 발표 반응", c.empty("과거 발표 데이터가 없어요.", with_orb=False), i=6))
        else:
            rows = [[x["발표일"], c.colored_pct(x["EPS 서프라이즈(%)"]), c.colored_pct(x["갭(%)"]), c.colored_pct(x["D+1(%)"]),
                     c.colored_pct(x["D+5(%)"]), c.colored_pct(x["시장 대비 D+1(%p)"])] for _, x in hist.iloc[::-1].iterrows()]
            c.show(c.card("과거 발표 반응", c.table(["발표일", "EPS 서프", "갭", "D+1", "D+5", "시장 대비"], rows, raw_cols={1, 2, 3, 4, 5}),
                          i=6, source="자동 · yfinance"))
    with right, st.container(key="card_scatter"):
        c.show(c.card_head("서프라이즈 vs 반응", sub="좋은 실적에도 빠지는 패턴이 있는지 보세요"))
        if not hist.empty:
            fig = go.Figure(go.Scatter(x=hist["EPS 서프라이즈(%)"], y=hist["D+1(%)"], mode="markers+text", text=hist["발표일"].str[2:7],
                                       textposition="top center", marker=dict(size=12, color=c.ACCENT, line=dict(color="#fff", width=2))))
            fig.add_hline(y=0, line_color="rgba(18,20,26,.2)")
            fig.add_vline(x=0, line_color="rgba(18,20,26,.2)")
            fig.update_xaxes(title="EPS 서프라이즈(%)", ticksuffix="%")
            fig.update_yaxes(title="D+1(%)", ticksuffix="%")
            c.plot_layout(fig, 300)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
