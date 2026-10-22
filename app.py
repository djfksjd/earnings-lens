"""Gaddong(가똥) — 실행: streamlit run app.py  (주소 고정: http://127.0.0.1:8765)"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Gaddong(가똥)", page_icon=":material/donut_large:", layout="wide",
                   initial_sidebar_state="collapsed")

from gaddong.ui import components, shell  # noqa: E402  set_page_config가 먼저 와야 한다
from views import call, financials, inputs, kpis, outlook, overview, reaction, segments, settings  # noqa: E402

MAIN = [
    st.Page(overview.render, title="개요", icon=":material/space_dashboard:", default=True),
    st.Page(financials.render, title="실적", icon=":material/monitoring:", url_path="financials"),
    st.Page(segments.render, title="사업부문", icon=":material/donut_small:", url_path="segments"),
    st.Page(kpis.render, title="KPI", icon=":material/speed:", url_path="kpis"),
    st.Page(call.render, title="컨콜", icon=":material/record_voice_over:", url_path="call"),
    st.Page(outlook.render, title="가이던스·카탈리스트", icon=":material/flag:", url_path="outlook"),
    st.Page(reaction.render, title="주가 반응", icon=":material/candlestick_chart:", url_path="reaction"),
]
BOTTOM = [
    st.Page(inputs.render, title="입력 관리", icon=":material/edit_note:", url_path="inputs"),
    st.Page(settings.render, title="설정", icon=":material/tune:", url_path="settings"),
]

page = st.navigation(MAIN + BOTTOM, position="hidden")
components.inject_css()
shell.rail(MAIN, BOTTOM, page)
st.session_state["_rep"] = shell.topbar()
page.run()
shell.copilot(st.session_state["_rep"])
