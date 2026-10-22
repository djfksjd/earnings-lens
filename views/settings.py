"""설정: 데이터 소스와 키 상태(값은 절대 표시하지 않음)."""
from __future__ import annotations

import streamlit as st

from earnings_lens import ai, config
from earnings_lens.security import esc, mask
from earnings_lens.ui import components as c


def render() -> None:
    c.page_title("설정 · 데이터 소스", "키는 .env 파일에서만 관리해요. 이 화면은 등록 여부만 보여줘요.")
    rows = []
    for k in config.KEY_SPECS:
        state = mask(config.secret(k.env))
        cls = "up" if state == "등록됨" else ""
        rows.append([f"<b>{esc(k.label)}</b><br><span class='card-sub'>{esc(k.env)}</span>",
                     f'<span class="pill {cls}">{esc(state)}</span>', esc(k.purpose),
                     f'<a href="{esc(k.signup)}" target="_blank" rel="noopener noreferrer">발급</a>'])
    rows.append(["<b>네이버 증권 수집</b><br><span class='card-sub'>NAVER_SCRAPING_ENABLED</span>",
                 f'<span class="pill {"up" if config.NAVER_ENABLED else ""}">{"켜짐" if config.NAVER_ENABLED else "꺼짐"}</span>',
                 "한국 실시간 시세·분기 컨센서스(E)·목표주가. robots.txt가 자동 수집을 막고 있어 기본은 꺼짐", "—"])
    c.show(c.card("데이터 소스", c.table(["소스", "상태", "쓰는 곳", "링크"], rows, raw_cols={0, 1, 2, 3}, text=True), i=0,
                  sub="모두 무료. 키가 없어도 yfinance만으로 기본 화면은 동작해요."))
    st.write("")
    left, right = st.columns(2)
    with left, st.container(key="card_ai"):
        ok, why = ai.available()
        c.show(c.card_head("AI (Claude 플랜)", sub=f"모델 {config.CLAUDE_MODEL} · {why}"))
        if st.button("연결 테스트", disabled=not ok):
            with st.spinner("Claude 호출 중…"):
                try:
                    reply = ai.run("'OK' 두 글자만 출력해.")
                    st.success(f"연결됨 · Claude 응답: {reply.strip()[:40]}")
                except ai.AIError as e:
                    st.error(str(e))
    with right, st.container(key="card_security"):
        c.show(c.card_head("보안 기본 규칙"))
        st.markdown("""
- 앱은 **127.0.0.1:8765** 에만 열려요. 같은 와이파이의 다른 기기도 접속할 수 없어요.
- 키는 `.env`에만 있고 `.gitignore`로 GitHub에 올라가지 않아요.
- 에러 메시지에서 키를 자동으로 지워요.
- AI는 도구가 모두 꺼진 상태로 실행돼 파일·명령에 접근하지 못해요.
- 외부에서 접속하려면 README의 **Tailscale** 절을 보세요(공개 인터넷 노출 금지).
""")
