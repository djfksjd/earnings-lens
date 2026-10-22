"""개요: 헤드라인 판정 → KPI 스탯 카드 → 벤토 그리드."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from earnings_lens import service
from earnings_lens.security import esc
from earnings_lens.ui import components as c
from views import _common as k


def render() -> None:
    r = k.rep()
    if r is None:
        return
    hv, basis = k.headline_verdict(r)
    tone = r.inputs.get("tone") or {}
    when = f"발표 {r.event:%Y-%m-%d %H:%M}" if r.event is not None else "발표일 정보 없음"
    lead = {"big_beat": "컨센서스를 크게 넘었습니다", "beat": "컨센서스를 넘었습니다", "inline": "컨센서스에 부합했습니다",
            "miss": "컨센서스에 못 미쳤습니다", "big_miss": "컨센서스를 크게 밑돌았습니다"}.get(hv.code, "비교할 컨센서스가 아직 없습니다")
    c.show(f'<div class="el-card headline tint-peri" style="--i:0">{c.orb(tone.get("score"), tone.get("label"), "lg")}'
           f'<div><h2>{esc(k.plabel(r))} 실적, {esc(lead)}</h2>'
           f'<p>{esc(r.profile.name)} · 분기말 {esc(r.period)} · {esc(when)} · 판정 기준 {esc(basis)}</p></div>'
           f'<div style="margin-left:auto">{c.verdict_chip(hv)}</div></div>')
    k.stat_cards(r, offset=1)

    left, mid, right = st.columns([2, 1, 1])
    with left:
        reaction_card(r)
        tone_card(r)
    with mid:
        src = k.section_source(r, "guidance")
        body = k.guidance_rows(r, 4) if r.inputs.get("guidance") else c.empty(
            "가이던스가 아직 없어요. <b>컨콜</b> 화면에서 AI로 추출하거나 <b>입력 관리</b>에서 직접 넣으세요.")
        c.show(c.card("가이던스", body, i=7, tint="apricot", source=src))
    with right:
        src = k.section_source(r, "catalysts")
        body = k.catalyst_rows(r, 3) if r.inputs.get("catalysts") else c.empty("다음 체크포인트가 비어 있어요.")
        c.show(c.card("다음 체크포인트", body, i=8, tint="mint", source=src))


def reaction_card(r: service.Report) -> None:
    rx, h, b = service.price_reaction(r)
    if h.empty:
        c.show(c.card("주가 반응", c.empty("가격 데이터를 불러오지 못했습니다."), i=5))
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=h.index, y=h["Close"], mode="lines", name=r.ticker, line=dict(color=c.ACCENT, width=2.4),
                             fill="tozeroy", fillcolor="rgba(76,99,240,.07)"))
    if r.event is not None:
        fig.add_vline(x=r.event.tz_convert(h.index.tz) if h.index.tz else r.event, line_width=1.5, line_dash="dot", line_color=c.INK,
                      annotation_text="실적 발표", annotation_position="top left", annotation_font=dict(size=11, color=c.INK))
    lo, hi = h["Close"].min(), h["Close"].max()
    fig.update_yaxes(range=[lo * 0.96, hi * 1.02])
    fig.update_layout(showlegend=False)
    fig.update_xaxes(tickformat="%Y.%m")
    fig.update_yaxes(tickformat=",.0f")
    c.plot_layout(fig, 250)
    if rx:
        stats = (f'<div class="deltas" style="margin-bottom:6px">'
                 f'{c.delta(rx["d1_pct"], "반응일")}{c.delta(rx["gap_pct"], "갭")}{c.delta(rx.get("d5_pct"), "D+5")}'
                 f'{c.delta(rx.get("excess_d1_pct"), "시장 대비")}</div>')
        sub = f"반응일 {rx['reaction_date']} · 기준 전일 종가"
    else:
        stats, sub = "", "발표일 이후 데이터가 아직 없어요"
    with st.container(key="card_reaction"):
        c.show(c.card_head("주가 반응", sub=sub, source="자동 · yfinance") + stats)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def tone_card(r: service.Report) -> None:
    tone = r.inputs.get("tone") or {}
    if not tone:
        body = c.empty("컨콜 톤 분석이 아직 없어요. <b>컨콜</b> 화면에서 트랜스크립트를 넣고 AI 분석을 실행하세요.", with_orb=True)
        c.show(c.card("컨콜 톤", body, i=6, tint="lilac"))
        return
    changes = "".join(f"<li>{esc(x)}</li>" for x in (tone.get("changes") or [])[:3])
    body = (f'<div style="display:flex;gap:14px;align-items:center">{c.orb(tone.get("score"), tone.get("label"))}'
            f'<div><b style="font-size:1.25rem">{esc(tone.get("label", ""))}</b><br>'
            f'<span class="card-sub">전분기 대비 {esc(tone.get("vs_last", "비교불가"))}</span></div></div>'
            f'{c.tone_meter(tone.get("score"))}'
            f'<p style="font-size:.88rem;color:var(--ink-2);line-height:1.55;margin:.6rem 0 .2rem">{esc(tone.get("summary", ""))}</p>'
            f'<ul style="font-size:.84rem;color:var(--ink-2);padding-left:1.1rem;margin:0">{changes}</ul>')
    c.show(c.card("컨콜 톤", body, i=6, tint="lilac", source=k.section_source(r, "tone")))
