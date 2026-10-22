"""기업별 KPI."""
from __future__ import annotations

import streamlit as st

from earnings_lens import manual
from earnings_lens.analysis.metrics import pct_change
from earnings_lens.security import esc
from earnings_lens.ui import components as c
from earnings_lens.ui import fmt
from views import _common as k


def render() -> None:
    r = k.rep()
    if r is None:
        return
    c.page_title("기업별 KPI", f"{r.profile.name} · {k.plabel(r)} 회사 고유 지표")
    kpis = r.inputs.get("kpis") or []
    if not kpis:
        c.show(c.card("KPI가 없어요", c.empty(
            "가입자·ARPU·출하량·수주잔고처럼 회사마다 다른 지표예요. 컨콜이나 보도자료를 AI로 분석하면 자동으로 채워지고, "
            "<b>입력 관리</b>에서 <code>kpis</code>로 직접 넣을 수도 있어요."), i=0))
        return
    src = k.section_source(r, "kpis")
    per_row = 3
    for start in range(0, len(kpis), per_row):
        cols = st.columns(per_row)
        for j, kp in enumerate(kpis[start:start + per_row]):
            v, pq, py = (manual.parse_amount(kp.get(x)) for x in ("value", "prev_q", "prev_y"))
            unit = kp.get("unit") or ""
            money = unit.upper() in ("USD", "KRW", "$", "원", "달러")
            cur = "KRW" if unit in ("KRW", "원") else "USD"
            show = (lambda x: fmt.money(x, cur)) if money else (lambda x: fmt.plain(x, unit))  # noqa: E731
            value = show(v) if v is not None else fmt.plain(kp.get("value"), unit)
            body = (f'<div class="stat"><div class="value" style="font-size:1.7rem">{esc(value)}</div>'
                    f'<div class="deltas">{c.delta(pct_change(v, pq), "QoQ")}{c.delta(pct_change(v, py), "YoY")}</div>'
                    + (f'<p class="card-sub" style="margin:.7rem 0 0;line-height:1.5">{esc(kp["note"])}</p>' if kp.get("note") else "")
                    + "</div>")
            with cols[j]:
                c.show(c.card(str(kp.get("name", "KPI")), body, i=start + j, source=src,
                              sub=f"전분기 {show(pq)} · 전년 {show(py)}"))
        st.write("")
