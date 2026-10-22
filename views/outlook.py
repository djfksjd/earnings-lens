"""가이던스와 앞으로의 카탈리스트."""
from __future__ import annotations

import streamlit as st

from gaddong import service
from gaddong.security import esc
from gaddong.ui import components as c
from gaddong.ui import fmt
from views import _common as k


def _link(title: str, url: str) -> str:
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(title)}</a>' if url.startswith("https://") else esc(title)


def render() -> None:
    r = k.rep()
    if r is None:
        return
    c.page_title("가이던스 · 카탈리스트", f"{r.profile.name} · 회사 전망과 앞으로 확인할 것")
    cur = r.profile.currency
    left, right = st.columns([3, 2])
    with left:
        body = k.guidance_rows(r) if r.inputs.get("guidance") else c.empty(
            "가이던스가 없어요. 컨콜·보도자료 AI 분석을 실행하거나 <code>guidance</code>를 직접 넣으세요.")
        c.show(c.card("회사 가이던스", body, i=0, tint="apricot", source=k.section_source(r, "guidance")))
        st.write("")
        fwd = service.get_forward(r.ticker)
        nq = fwd.get("0q") or {}
        rows = []
        if nq:
            rows.append(["다음 분기 매출", fmt.money(nq.get("rev_avg"), cur), f"{fmt.money(nq.get('rev_low'), cur)} ~ {fmt.money(nq.get('rev_high'), cur)}",
                         fmt.plain(nq.get("rev_n"), "명")])
            rows.append(["다음 분기 EPS", fmt.eps(nq.get("eps_avg"), cur), f"{fmt.eps(nq.get('eps_low'), cur)} ~ {fmt.eps(nq.get('eps_high'), cur)}",
                         fmt.plain(nq.get("eps_n"), "명")])
        body = c.table(["항목", "컨센서스", "범위", "애널리스트"], rows) if rows else c.empty("다음 분기 컨센서스가 없어요.", with_orb=False)
        c.show(c.card("시장 기대치 (다음 분기)", body, i=1, source="자동 · yfinance",
                      sub="가이던스와 비교해 보세요 · 이 값은 매일 스냅샷으로 저장돼 다음 실적 때 비교 기준이 돼요"))
    with right:
        items = []
        nd = (service.get_forward(r.ticker) or {}).get("next_date")
        if nd:
            items.append(('<span class="pill accent">자동</span>', f"다음 실적 발표 예정일 {nd}"))
        body = k.catalyst_rows(r) if r.inputs.get("catalysts") else ""
        auto = k.bullet_rows(items) if items else ""
        c.show(c.card("체크포인트", (auto + ("<div style='height:10px'></div>" if auto and body else "") + body)
                      or c.empty("체크포인트가 없어요."), i=2, tint="mint", source=k.section_source(r, "catalysts")))
        st.write("")
        nav = service.get_naver_integration(r.ticker)
        if nav:
            rows = [f"목표주가 평균 {fmt.price(nav.get('target_price'), 'KRW')} · 투자의견 {fmt.plain(nav.get('recomm_mean'))}/5 ({nav.get('consensus_date') or ''})"]
            rows += [f"{x['date']} {x['broker']} — {x['title']}" for x in nav.get("researches", [])]
            c.show(c.card("증권사 시각", k.bullet_rows([('<span class="pill">리서치</span>', x) for x in rows]), i=3, source="네이버(옵트인)"))
            st.write("")
        docs, err = service.get_disclosures(r.ticker)
        if docs:
            html = '<div class="list">' + "".join(
                f'<div class="row"><span class="pill">{esc(d["date"])}</span><span>{_link(d["title"], d["url"])}</span></div>' for d in docs[:8]) + "</div>"
            c.show(c.card("관련 공시", html, i=4, source="DART" if service.is_kr(r.ticker) else "SEC EDGAR"))
        elif err:
            c.show(c.card("관련 공시", c.empty(esc(err), with_orb=False), i=4))
        st.write("")
        news = service.get_news(r.ticker)
        if news:
            html = '<div class="list">' + "".join(
                f'<div class="row"><span class="pill">{esc(n["publisher"][:14])}</span><span>{_link(n["title"], n["url"])}</span></div>' for n in news[:6]) + "</div>"
            c.show(c.card("최근 뉴스", html, i=5, source="yfinance"))
