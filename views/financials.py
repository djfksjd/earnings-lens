"""실적: 분기 추이와 컨센서스 대비 이력."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from earnings_lens import service
from earnings_lens.analysis import metrics
from earnings_lens.ui import components as c
from earnings_lens.ui import fmt
from views import _common as k


def render() -> None:
    r = k.rep()
    if r is None:
        return
    c.page_title("실적", f"{r.profile.name} · {k.plabel(r)} 기준 QoQ / YoY")
    k.stat_cards(r)
    st.write("")

    cur = r.profile.currency
    rows = []
    for m in r.changes.index:
        row = r.changes.loc[m]
        cons = r.consensus.get(m)
        v = r.verdicts.get(m)
        rows.append([metrics.LABELS.get(m, m), fmt.metric_value(m, row["value"], cur), fmt.metric_value(m, row["prev_q"], cur),
                     c.colored_pct(row["qoq"]), fmt.metric_value(m, row["prev_y"], cur), c.colored_pct(row["yoy"]),
                     fmt.metric_value(m, cons.value, cur) if cons and cons.value is not None else "—",
                     c.verdict_chip(v) if v else "—", r.fin_src.get(m, "")])
    c.show(c.card("핵심 지표 비교", c.table(["지표", "당분기", "전분기", "QoQ", "전년동기", "YoY", "컨센서스", "판정", "출처"], rows,
                                       raw_cols={3, 5, 7}), i=4, sub=f"분기말 {r.period} · 통화 {cur}"))
    st.write("")

    left, right = st.columns([3, 2])
    with left, st.container(key="card_trend"):
        df = r.fin.tail(8)
        labels = [service.period_label(p, r.profile.fy_end_month) for p in df.index]
        div, unit = c.money_unit(list(df["revenue"]) + list(df["operating_income"]), cur)
        fig = go.Figure()
        fig.add_bar(x=labels, y=df["revenue"] / div, name="매출액", marker_color="#C9D0FB",
                    marker_line_width=0, hovertemplate=f"%{{x}}<br>매출 %{{y:,.2f}}{unit}<extra></extra>")
        fig.add_bar(x=labels, y=df["operating_income"] / div, name="영업이익", marker_color=c.ACCENT,
                    marker_line_width=0, hovertemplate=f"%{{x}}<br>영업이익 %{{y:,.2f}}{unit}<extra></extra>")
        fig.update_yaxes(ticksuffix=unit, tickformat=",.0f")
        margin = (df["operating_income"] / df["revenue"] * 100).where(df["revenue"] > 0)
        fig.add_scatter(x=labels, y=margin, name="영업이익률(%)", yaxis="y2", mode="lines+markers",
                        line=dict(color=c.INK, width=2), marker=dict(size=7))
        fig.update_layout(barmode="group", yaxis2=dict(overlaying="y", side="right", showgrid=False, ticksuffix="%", tickformat=".0f"))
        c.plot_layout(fig, 330)
        c.show(c.card_head("분기 추이", sub="막대: 매출·영업이익, 선: 영업이익률"))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with right, st.container(key="card_eps"):
        eh = service.get_eps_history(r.ticker)
        c.show(c.card_head("EPS 서프라이즈 이력", sub="실제 vs 컨센서스(%)", source="자동 · yfinance"))
        if eh.empty:
            c.show(c.empty("EPS 추정 이력이 없습니다."))
        else:
            eh = eh.tail(8)
            colors = [c.BEAT if (v or 0) > metrics.INLINE else c.MISS if (v or 0) < -metrics.INLINE else "#D8B46A"
                      for v in eh["surprise_pct"]]
            fig = go.Figure(go.Bar(x=[service.period_label(p, r.profile.fy_end_month) for p in eh.index], y=eh["surprise_pct"],
                                   marker_color=colors, marker_line_width=0,
                                   text=[fmt.pct(v) for v in eh["surprise_pct"]], textposition="outside",
                                   hovertemplate="%{x}<br>%{y:.1f}%<extra></extra>"))
            fig.update_yaxes(ticksuffix="%")
            c.plot_layout(fig, 330)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with st.expander("원본 분기 데이터"):
        st.dataframe(r.fin.sort_index(ascending=False), width="stretch")
