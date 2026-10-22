"""입력 관리: 사용자가 직접 넣는 값(my_inputs/)을 앱 안에서 편집."""
from __future__ import annotations

import streamlit as st
import yaml

from earnings_lens import config, manual
from earnings_lens.security import clean_ticker
from earnings_lens.ui import components as c
from views import _common as k

TEMPLATE = """# 이 파일은 내가 직접 넣는 값이에요. 비워둔 항목은 자동 수집·AI 결과를 씁니다.
# 금액은 숫자 또는 '41.1B', '1.2조', '3,500억' 처럼 써도 돼요.
consensus:              # 발표 직전 컨센서스 (FnGuide·증권사 리포트 등에서)
  revenue:
  operating_income:
  ebitda:
  eps:
  source: ""            # 예: "FnGuide 2026-07-25"
segments: []            # - {name: 메모리, revenue: 25조, revenue_prev_q: 21조, revenue_prev_y: 15조, operating_income: 9조}
kpis: []                # - {name: HBM 출하 비중, value: 32, prev_q: 28, prev_y: 15, unit: "%", note: ""}
guidance: []            # - {metric: 3Q 매출, period: 3Q26, low: 50B, high: 52B, unit: USD, direction: 상향, note: ""}
catalysts: []           # - {date: 2026-11-18, event: 다음 실적 발표, why: 신제품 램프업 확인}
notes: ""
"""


def render() -> None:
    r = st.session_state.get("_rep")
    c.page_title("입력 관리", "자동 수집이 못 채우는 값을 직접 넣는 곳 · 파일은 my_inputs/ 에 저장돼요")
    c.show(c.card("무엇을 직접 넣나요?", k.bullet_rows([
        ('<span class="pill accent">필수 X</span>', "아무것도 안 넣어도 실적·EPS 컨센서스·주가 반응은 자동으로 나와요."),
        ('<span class="pill">추천</span>', "한국 기업 영업이익 컨센서스(FnGuide·리포트), 세그먼트, KPI"),
        ('<span class="pill">선택</span>', "컨콜 원문(한국 기업), 가이던스·체크포인트를 직접 정리하고 싶을 때"),
        ('<span class="pill">우선순위</span>', "내 입력 > AI 추출 > 자동 수집 — 화면의 출처 배지로 확인할 수 있어요"),
    ]), i=0))
    st.write("")
    if r is not None and r.period:
        left, right = st.columns([3, 2])
        with left, st.container(key="card_editor"):
            path = manual.input_path(r.ticker, r.period)
            c.show(c.card_head(f"{r.ticker} · {r.period} 입력", sub=str(path.relative_to(config.ROOT))))
            mine, src = manual.load_inputs(r.ticker, r.period)
            if src == "내 입력":
                start = yaml.safe_dump(mine, allow_unicode=True, sort_keys=False)
                if not mine.get("consensus"):  # AI 결과를 확정한 파일에는 컨센서스 칸이 없어 어디에 쓸지 모르기 쉽다
                    start += ("\n# 컨센서스를 넣으려면 아래 주석(#)을 지우고 채우세요.\n"
                              "# consensus:\n#   revenue: 79조\n#   operating_income: 4.6조\n#   source: \"FnGuide 2026-07-05\"\n")
            else:
                start = TEMPLATE
            text = st.text_area("YAML", start, height=460, label_visibility="collapsed", key=f"yaml_{r.ticker}_{r.period}")
            if st.button("검사 후 저장", type="primary"):
                try:
                    data = manual.validate_yaml_text(text)
                    manual.save_inputs(r.ticker, r.period, data)
                    st.cache_data.clear()
                    st.success("저장했어요. 다른 화면에 바로 반영돼요.")
                except (ValueError, yaml.YAMLError) as e:
                    st.error(f"저장하지 않았어요: {e}")
        with right, st.container(key="card_help"):
            c.show(c.card_head("항목 설명"))
            st.markdown("""
- **consensus**: 발표 *직전* 시장 예상치. 비우면 앱이 매일 저장한 스냅샷과 yfinance EPS 추정치를 씁니다.
- **actual_override**: 자동 수집한 실적이 틀렸을 때만 씁니다.
- **segments**: 사업부문. `revenue_prev_q`(전분기), `revenue_prev_y`(전년동기)를 넣으면 QoQ/YoY가 계산돼요.
- **kpis**: 회사 고유 지표와 단위.
- **guidance**: `direction`은 상향 / 유지 / 하향 / 신규 / 철회 / 정성적 중 하나.
- **tone**, **quotes**, **qa**: 보통 AI가 채웁니다. 직접 써도 돼요.
- **catalysts**: 날짜는 `YYYY-MM-DD`.
""")
    st.write("")
    with st.container(key="card_watchlist"):
        c.show(c.card_head("관심 종목", sub="my_inputs/watchlist.yaml"))
        wl = manual.watchlist()
        text = st.text_input("티커(쉼표로 구분)", ", ".join(wl))
        if st.button("관심 종목 저장"):
            try:
                tickers = []
                for t in (x.strip() for x in text.split(",")):
                    if not t:
                        continue
                    try:
                        tickers.append(clean_ticker(t))
                    except ValueError:
                        raise ValueError(f"'{t}' — 티커 형식이 올바르지 않아요. 예: NVDA, 005930.KS") from None
                tickers = list(dict.fromkeys(tickers))
                manual.save_watchlist(tickers)
                st.success("저장했어요.")
            except ValueError as e:
                st.error(str(e))
