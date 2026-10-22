"""사업부문별 매출·영업이익."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from earnings_lens import manual
from earnings_lens.analysis.metrics import pct_change
from earnings_lens.ui import components as c
from earnings_lens.ui import fmt
from views import _common as k


def render() -> None:
    r = k.rep()
    if r is None:
        return
    c.page_title("사업부문", f"{r.profile.name} · {k.plabel(r)} 세그먼트별 QoQ / YoY")
    # AI가 가끔 '전사 합계' 행을 부문처럼 넣는다. 합계가 섞이면 비중이 틀어지므로 뺀다.
    segs = [s for s in (r.inputs.get("segments") or []) if not manual.is_total_row(s.get("name"))]
    if not segs:
        c.show(c.card("세그먼트 데이터가 없어요", c.empty(
            "무료 API는 사업부문 수치를 주지 않아요. 두 가지 방법 중 하나를 쓰세요.<br>"
            "① <b>컨콜</b> 화면 → <b>보도자료로 AI 추출</b>(미국: SEC 8-K 자동, 한국: IR 자료 붙여넣기)<br>"
            f"② <b>입력 관리</b>에서 <code>segments</code>에 직접 입력 · 파일 위치 <code>my_inputs/companies/{r.ticker.replace('.', '_')}/{r.period}.yaml</code>"),
            i=0))
        return

    cur = r.profile.currency
    m = lambda v: fmt.money(manual.parse_amount(v), cur)  # noqa: E731
    total = sum(manual.parse_amount(s.get("revenue")) or 0 for s in segs) or None
    rows = []
    for s in segs:
        rev, rq, ry = (manual.parse_amount(s.get(x)) for x in ("revenue", "revenue_prev_q", "revenue_prev_y"))
        op, oq, oy = (manual.parse_amount(s.get(x)) for x in ("operating_income", "operating_income_prev_q", "operating_income_prev_y"))
        rows.append([s.get("name", ""), m(rev), c.colored_pct(pct_change(rev, rq)), c.colored_pct(pct_change(rev, ry)),
                     fmt.pct(rev / total * 100, signed=False) if rev and total else "—",
                     m(op), c.colored_pct(pct_change(op, oq)), c.colored_pct(pct_change(op, oy)),
                     fmt.pct(op / rev * 100, signed=False) if op is not None and rev else "—"])
    c.show(c.card("세그먼트 성과", c.table(["사업부문", "매출", "QoQ", "YoY", "비중", "영업이익", "QoQ", "YoY", "이익률"], rows,
                                       raw_cols={2, 3, 6, 7}), i=0, source=k.section_source(r, "segments")))
    st.write("")

    left, right = st.columns(2)
    names = [s.get("name", "") for s in segs]
    with left, st.container(key="card_seg_rev"):
        fig = go.Figure()
        for label, key, color in (("전년동기", "revenue_prev_y", "#DDE1F6"), ("전분기", "revenue_prev_q", "#A9B4F6"), ("당분기", "revenue", c.ACCENT)):
            fig.add_bar(x=names, y=[manual.parse_amount(s.get(key)) for s in segs], name=label, marker_color=color, marker_line_width=0)
        fig.update_layout(barmode="group")
        c.plot_layout(fig, 320)
        c.show(c.card_head("부문 매출 비교"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with right, st.container(key="card_seg_mix"):
        vals = [manual.parse_amount(s.get("revenue")) or 0 for s in segs]
        fig = go.Figure(go.Pie(labels=names, values=vals, hole=.62, marker=dict(colors=c.SERIES, line=dict(color="#fff", width=2)),
                               textinfo="percent", sort=False))
        c.plot_layout(fig, 320)
        c.show(c.card_head("매출 구성"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    notes = [s for s in segs if s.get("note")]
    if notes:
        c.show(c.card("부문 코멘트", k.bullet_rows([(f'<span class="pill">{c.esc(s.get("name", ""))}</span>', s["note"]) for s in notes]), i=3))
