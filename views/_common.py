"""화면 공용 도우미."""
from __future__ import annotations

from urllib.parse import quote

import streamlit as st

from gaddong import manual, service
from gaddong.analysis import metrics
from gaddong.security import esc
from gaddong.ui import components as c
from gaddong.ui import fmt

HEADLINE = ("revenue", "operating_income", "ebitda", "eps")


def rep() -> service.Report | None:
    r = st.session_state.get("_rep")
    if r is None or r.changes.empty:
        c.show(c.card("데이터 없음", c.empty("이 종목의 분기 실적을 찾지 못했습니다. 티커를 확인하거나 "
                                          "<code>설정</code>에서 데이터 소스 상태를 보세요."), i=0))
        return None
    return r


def plabel(r: service.Report, p: str | None = None) -> str:
    return service.period_label(p or r.period, r.profile.fy_end_month)


def value_fmt(r: service.Report, metric: str):
    cur = r.profile.currency
    return lambda v: fmt.metric_value(metric, v, cur)


def stat_cards(r: service.Report, offset: int = 0) -> None:
    cols = st.columns(4)
    for i, m in enumerate(HEADLINE):
        row = r.changes.loc[m] if m in r.changes.index else None
        cons = r.consensus.get(m)
        v = r.verdicts.get(m, metrics.Verdict("na", "컨센서스 없음", None))
        f = value_fmt(r, m)
        val = row["value"] if row is not None else None
        strip = c.consensus_strip(r.actuals.get(m, val), cons.value if cons else None, cons.low if cons else None,
                                  cons.high if cons else None, v, f,
                                  link=f"./inputs?t={quote(r.ticker)}&p={quote(r.period)}")  # 새로 열려도 같은 종목·분기
        src = r.fin_src.get(m, "")
        with cols[i]:
            c.show(c.stat_card(metrics.LABELS[m], f(val), row["qoq"] if row is not None else None,
                               row["yoy"] if row is not None else None, v, strip, i=i + offset,
                               source=f"자동 · {src}" if src and not src.startswith(("내 입력", "예시")) else src))


def headline_verdict(r: service.Report) -> tuple[metrics.Verdict, str]:
    """헤드라인 판정: 영업이익 → EPS → 매출 → EBITDA 순으로 컨센서스가 있는 첫 지표."""
    for m in ("operating_income", "eps", "revenue", "ebitda"):
        v = r.verdicts.get(m)
        if v and v.code != "na":
            return v, metrics.LABELS[m]
    return metrics.Verdict("na", "컨센서스 데이터 없음", None), "없음"


def section_source(r: service.Report, sec: str) -> str:
    return r.inputs.get("_source", {}).get(sec, "")


def bullet_rows(items: list[tuple[str, str]]) -> str:
    """(pill html, text) 목록. text는 여기서 이스케이프."""
    return '<div class="list">' + "".join(f'<div class="row">{p}<span>{esc(t)}</span></div>' for p, t in items) + "</div>"


def guidance_rows(r: service.Report, limit: int | None = None) -> str:
    items = (r.inputs.get("guidance") or [])[:limit]
    rows = []
    for g in items:
        d = str(g.get("direction") or "")
        cls = "up" if d in ("상향", "신규") else "down" if d in ("하향", "철회") else "accent"
        rng = ""
        lo, hi = g.get("low"), g.get("high")
        unit = g.get("unit") or ""
        if lo is not None or hi is not None:
            if str(unit).upper() in ("USD", "KRW", "$", "원", "달러"):
                cur = "KRW" if unit in ("KRW", "원") else "USD"
                rng = f" {fmt.money(manual.parse_amount(lo), cur)}~{fmt.money(manual.parse_amount(hi), cur)}"
            else:
                rng = f" {fmt.plain(lo)}~{fmt.plain(hi)} {unit}".rstrip()
        text = f"{g.get('metric', '')}{(' (' + str(g['period']) + ')') if g.get('period') else ''}{rng}"
        if g.get("note"):
            text += f" — {g['note']}"
        rows.append((f'<span class="pill {cls}">{esc(d or "가이던스")}</span>', text))
    return bullet_rows(rows)


def catalyst_rows(r: service.Report, limit: int | None = None) -> str:
    items = sorted(r.inputs.get("catalysts") or [], key=lambda x: str(x.get("date") or "9999"))[:limit]
    return bullet_rows([(f'<span class="pill">{esc(x.get("date") or "날짜 미정")}</span>',
                         f"{x.get('event', '')} — {x.get('why', '')}".strip(" —")) for x in items])
