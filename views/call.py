"""컨콜: 톤 변화, CEO 핵심 발언, Q&A. 트랜스크립트·보도자료 수집과 AI 분석 실행."""
from __future__ import annotations

import statistics

import pandas as pd
import streamlit as st

from earnings_lens import ai, config, manual, service
from earnings_lens.analysis.metrics import prev_period
from earnings_lens.providers import alphavantage, fool, sec
from earnings_lens.providers.http import ProviderError
from earnings_lens.security import esc
from earnings_lens.ui import components as c
from earnings_lens.ui import mascot
from earnings_lens.ui import fmt
from views import _common as k


def render() -> None:
    r = k.rep()
    if r is None:
        return
    c.page_title("컨퍼런스콜", f"{r.profile.name} · {k.plabel(r)} 톤 · 핵심 발언 · Q&A")
    text, src, turns = service.transcript_for(r)

    tab_view, tab_src = st.tabs(["분석 결과", "원문 · AI 실행"])
    with tab_src:
        sources_panel(r, text, src)
    with tab_view:
        results(r, turns)


def _exec_sentiment(turns: list[dict]) -> float | None:
    vals = [t["sentiment"] for t in turns if t.get("sentiment") is not None
            and any(x in (t.get("title") or "").lower() for x in ("chief", "ceo", "cfo", "president", "officer"))]
    return statistics.mean(vals) if vals else None


def results(r: service.Report, turns: list[dict]) -> None:
    tone = r.inputs.get("tone") or {}
    left, right = st.columns([1, 2])
    with left:
        prev = None
        if turns and not service.is_kr(r.ticker):
            pfq = alphavantage.fiscal_quarter(prev_period(r.period, 3), r.profile.fy_end_month)
            p = config.CACHE_DIR / "transcripts" / f"{r.ticker.replace('.', '_')}_{pfq}.json"
            if p.exists():
                prev = _exec_sentiment(alphavantage.transcript(r.ticker, pfq))
        now = _exec_sentiment(turns) if turns else None
        with st.container(key="card_calltone"):
            c.show(c.card_head("경영진 톤", source=k.section_source(r, "tone")))
            pic, text = st.columns([0.36, 0.64], vertical_alignment="center", gap="small")
            with pic:
                mascot.render(mascot.tone_mood(tone), height=120,
                              hue=c.tone_hue(tone.get("score"), tone.get("label")) if tone else None)
            with text:
                st.html(f'<b style="font-size:1.4rem">{esc(tone.get("label", ""))}</b><br><span class="card-sub">'
                        f'전분기 대비 {esc(tone.get("vs_last", ""))}</span>' if tone else
                        '<span class="card-sub">아직 분석 전이에요. <b>원문 · AI 실행</b> 탭에서 시작하세요.</span>')
            body = ""
            if tone:
                body = (f'{c.tone_meter(tone.get("score"))}'
                        f'<p style="font-size:.9rem;line-height:1.6;color:var(--ink-2)">{esc(tone.get("summary", ""))}</p>')
            if now is not None:
                body += (f'<div class="deltas" style="margin-top:8px"><span>경영진 감성(AV) <b>{now:+.2f}</b></span>'
                         + (f'<span>전분기 <b>{prev:+.2f}</b></span>' if prev is not None else "") + "</div>")
            if body:
                st.html(body)
        changes = tone.get("changes") or []
        if changes:
            st.write("")
            c.show(c.card("전분기 대비 달라진 점", k.bullet_rows([('<span class="pill accent">변화</span>', x) for x in changes]), i=1))
    with right:
        quotes = r.inputs.get("quotes") or []
        if quotes:
            html = '<div class="list">' + "".join(
                f'<div class="quote">“{esc(q.get("text", ""))}”<cite>{esc(q.get("speaker", ""))}'
                f'{(" · " + esc(q["role"])) if q.get("role") and q.get("role") != q.get("speaker") else ""}</cite>'
                + (f'<div class="why">{esc(q["why"])}</div>' if q.get("why") else "") + "</div>" for q in quotes) + "</div>"
            c.show(c.card("CEO · CFO 핵심 발언", html, i=2, source=k.section_source(r, "quotes")))
            st.write("")
        qa = r.inputs.get("qa") or []
        if qa:
            html = '<div class="list">' + "".join(
                f'<div class="quote"><b>Q.</b> {esc(x.get("question", ""))}'
                f'<cite>{esc(x.get("analyst", ""))}</cite><div style="margin-top:8px"><b>A.</b> {esc(x.get("answer", ""))}</div>'
                + (f'<div class="why">{esc(x["signal"])}</div>' if x.get("signal") else "") + "</div>" for x in qa) + "</div>"
            c.show(c.card("Q&A 핵심", html, i=3, source=k.section_source(r, "qa")))
        if not quotes and not qa:
            c.show(c.card("발언 · Q&A", c.empty("AI 분석을 실행하거나 입력 관리에서 <code>quotes</code>, <code>qa</code>를 넣으세요."), i=2))


def sources_panel(r: service.Report, text: str | None, src: str) -> None:
    ok, why = ai.available()
    left, right = st.columns(2)
    with left, st.container(key="card_transcript"):
        c.show(c.card_head("① 컨콜 트랜스크립트", sub=f"현재: {src or '없음'}"))
        if not service.is_kr(r.ticker):
            fq = alphavantage.fiscal_quarter(r.period, r.profile.fy_end_month)
            fq = st.text_input("회계분기(Alpha Vantage)", fq, help="회사 기준 회계분기. NVDA처럼 결산월이 다르면 자동 계산값을 확인하세요.")
            disabled = not config.has("ALPHAVANTAGE_API_KEY")
            if st.button("Alpha Vantage에서 가져오기", disabled=disabled, help="무료 하루 25회. 받은 원문은 저장돼 다시 호출하지 않아요."):
                try:
                    alphavantage.transcript(r.ticker, fq)
                    st.toast("가져왔어요. 저장된 원문으로 분석할 수 있어요.", icon=":material/check:")
                    st.rerun()
                except (ProviderError, ValueError) as e:
                    st.error(str(e))
            if disabled:
                st.caption("ALPHAVANTAGE_API_KEY를 .env에 넣으면 미국 컨콜 원문을 무료로 받을 수 있어요.")
            if st.button("Motley Fool에서 가져오기", disabled=not config.FOOL_ENABLED,
                         help="옵트인 수집(.env의 FOOL_SCRAPING_ENABLED). 사이트 약관이 자동 수집을 금지하니 개인 학습 용도로만 쓰세요."):
                ev = r.event.tz_convert(None).date() if r.event is not None and r.event.tzinfo else (
                    r.event.date() if r.event is not None else None)
                try:
                    fool.transcript(r.ticker, fq, ev)
                    st.toast("가져왔어요. 저장된 원문으로 분석할 수 있어요.", icon=":material/check:")
                    st.rerun()
                except ProviderError as e:
                    st.error(str(e))
        else:
            st.caption("한국 기업 컨콜 원문은 무료 API가 없어요. IR 페이지의 녹취록·발표 요지를 붙여넣으세요.")
        pasted = st.text_area("원문 붙여넣기", height=160, placeholder="컨콜 녹취록이나 발표 요지를 붙여넣고 저장하세요.")
        # 버튼을 글 유무로 비활성화하면 붙여넣은 직후 첫 클릭이 '글 확정'에만 쓰인다. 누른 뒤 검사한다.
        if st.button("붙여넣은 원문 저장"):
            if pasted.strip():
                p = manual.save_transcript(r.ticker, r.period, pasted)
                st.toast(f"저장: {p.relative_to(config.ROOT)}", icon=":material/check:")
                st.rerun()
            else:
                st.warning("붙여넣은 원문이 없어요.")
        if text:
            with st.expander(f"원문 미리보기 ({len(text):,}자)"):
                st.text(text[:4000] + ("\n…" if len(text) > 4000 else ""))
        if st.button("컨콜 AI 분석 실행", type="primary", disabled=not (ok and text)):
            last = manual.load_ai(r.ticker, prev_period(r.period, 3), "call").get("tone", {}).get("summary")
            with st.spinner("Claude가 컨콜을 읽는 중… (1~3분)"):
                try:
                    out = ai.analyze_call(r.profile.name, k.plabel(r), text or "", last)
                    manual.save_ai(r.ticker, r.period, "call", out)
                    st.toast("분석을 저장했어요. 분석 결과 탭에서 보세요.", icon=":material/check:")
                    st.rerun()
                except ai.AIError as e:
                    st.error(str(e))
        if not ok:
            st.caption(why)

    with right, st.container(key="card_release"):
        c.show(c.card_head("② 실적 보도자료 · IR 자료", sub="세그먼트 · KPI · 가이던스 추출"))
        doc_text = None
        if not service.is_kr(r.ticker):
            docs, err = service.get_disclosures(r.ticker)
            if err:
                st.caption(err)
            ev = r.event.tz_convert(None) if r.event is not None and r.event.tzinfo else r.event
            near = [d for d in docs if ev is not None and abs((pd.Timestamp(d["date"]) - ev).days) <= 5]
            options = near or docs
            if options:
                pick = st.selectbox("SEC 8-K 첨부", options, format_func=lambda d: f"{d['date']} · {d['title']}")
                st.caption(f"[원문 열기]({pick['url']})")
                if st.button("보도자료로 AI 추출", type="primary", disabled=not ok):
                    try:
                        doc_text = sec.exhibit_text(pick["url"])
                    except ProviderError as e:
                        st.error(str(e))
        ir_text = st.text_area("IR 자료 텍스트 붙여넣기", height=140, placeholder="한국 기업은 IR 발표자료 PDF의 텍스트를 붙여넣으세요.")
        if st.button("붙여넣은 자료로 AI 추출", disabled=not ok):
            if ir_text.strip():
                doc_text = ir_text
            else:
                st.warning("IR 자료 텍스트를 먼저 붙여넣으세요.")
        if doc_text:
            with st.spinner("Claude가 보도자료를 읽는 중…"):
                try:
                    out = ai.analyze_release(r.profile.name, k.plabel(r), doc_text)
                    manual.save_ai(r.ticker, r.period, "release", out)
                    st.toast(f"추출 완료: {out.get('headline', '')}", icon=":material/check:")
                    st.rerun()
                except ai.AIError as e:
                    st.error(str(e))

    st.write("")
    with st.container(key="card_promote"):
        c.show(c.card_head("③ AI 결과 검토 후 내 입력으로 확정",
                           sub="AI 결과는 data/ai/에 따로 저장돼요. 확정하면 my_inputs/ YAML로 복사되고, 이후 직접 고칠 수 있어요."))
        if st.button("AI 결과를 내 입력으로 저장", disabled=not (manual.load_ai(r.ticker, r.period, "call") or manual.load_ai(r.ticker, r.period, "release"))):
            mine, src_label = manual.load_inputs(r.ticker, r.period)
            mine = dict(mine) if src_label == "내 입력" else {}
            for sec_name, val in manual.combined_ai(r.ticker, r.period).items():
                if sec_name in manual.SECTIONS and not mine.get(sec_name):
                    mine[sec_name] = val
            mine = manual.readable_amounts(mine, lambda v: fmt.money(v, r.profile.currency))
            p = manual.save_inputs(r.ticker, r.period, mine)
            st.toast(f"저장: {p.relative_to(config.ROOT)} — 입력 관리에서 수정하세요.", icon=":material/check:")
            st.rerun()
