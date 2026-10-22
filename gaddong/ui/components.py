"""HTML 조각. 외부 데이터는 전부 esc()를 거친다."""
from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from ..analysis.metrics import Verdict
from ..security import esc
from . import fmt

_CSS = (Path(__file__).parent / "theme.css").read_text(encoding="utf-8")

INK, INK3, LINE = "#12141A", "#646a79", "rgba(18,20,26,.08)"
ACCENT, BEAT, MISS, AMBER = "#4C63F0", "#0E8058", "#C23E2C", "#8C5F0E"
SERIES = ["#4C63F0", "#3FB58A", "#F29A5B", "#9A7BE0", "#5CB8E6", "#E46F8C", "#B9A23A"]


def inject_css() -> None:
    st.html(f"<style>{_CSS}</style>")


def src_badge(source: str) -> str:
    if not source:
        return ""
    cls = "mine" if source.startswith("내 입력") else "ai" if source.startswith("AI") else "example" if source.startswith("예시") else ""
    return f'<span class="src {cls}">{esc(source)}</span>'


def card_head(title: str, *, sub: str = "", source: str = "") -> str:
    return (f'<div class="card-head"><div><h3>{esc(title)}</h3>' + (f'<div class="card-sub">{esc(sub)}</div>' if sub else "")
            + f"</div>{src_badge(source)}</div>")


def card(title: str, body: str, *, i: int = 0, tint: str = "", source: str = "", sub: str = "") -> str:
    """title·sub·source는 여기서 이스케이프한다. body는 호출한 쪽에서 이미 이스케이프한 HTML."""
    head = card_head(title, sub=sub, source=source)
    return f'<div class="el-card {("tint-" + tint) if tint else ""}" style="--i:{int(i)}">{head}{body}</div>'


def show(html: str) -> None:
    st.html(html)


def delta(v, label: str) -> str:
    cls = "flat" if v is None else "up" if v > 0 else "down" if v < 0 else "flat"
    return f'<span>{esc(label)} <b class="{cls}">{fmt.pct(v)}</b></span>'


def verdict_chip(v: Verdict) -> str:
    txt = v.label + (f" {fmt.pct(v.diff_pct)}" if v.diff_pct is not None else "")
    return f'<span class="verdict {esc(v.code)}">{esc(txt)}</span>'


def consensus_strip(actual, cons, low, high, verdict: Verdict, fmt_fn, link: str = "./inputs") -> str:
    """추정 범위(밴드) · 컨센서스(세로 눈금) · 실제(점, 판정 색)."""
    if cons is None:
        # 컨센서스가 없어도 같은 자리에 트랙을 그려 카드 형태를 유지한다
        dot = '<span class="dot" style="left:50%;background:#A3A8B6"></span>' if actual is not None else ""
        return ('<div class="strip"><div class="strip-track empty-track"><span class="rail-line"></span>'
                f'<span class="tick ghost" style="left:50%"></span>{dot}</div>'
                '<div class="legend"><span>컨센서스 미입력</span>'
                f'<a href="{esc(link)}" target="_self">컨센서스 입력</a></div></div>')
    pts = [p for p in (actual, cons, low, high) if p is not None]
    lo, hi = min(pts), max(pts)
    pad = max((hi - lo) * 0.18, abs(cons) * 0.04, 1e-9)
    lo, hi = lo - pad, hi + pad

    def x(v):  # 트랙 위 위치(%)
        return (v - lo) / (hi - lo) * 100

    color = {"big_beat": BEAT, "beat": BEAT, "big_miss": MISS, "miss": MISS, "inline": AMBER}.get(verdict.code, INK3)
    parts = ['<div class="strip-track" role="img" aria-label="컨센서스 대비 위치"><span class="rail-line"></span>']
    if low is not None and high is not None and high > low:
        parts.append(f'<span class="band" style="left:{x(low):.1f}%;width:{max(x(high) - x(low), 1):.1f}%"></span>')
    if actual is not None:
        a, b = sorted((x(cons), x(actual)))
        parts.append(f'<span class="gap" style="left:{a:.1f}%;width:{b - a:.1f}%;background:{color}"></span>')
    parts.append(f'<span class="tick" style="left:{x(cons):.1f}%"></span>')
    if actual is not None:
        parts.append(f'<span class="dot" style="left:{x(actual):.1f}%;background:{color}"></span>')
    svg = "".join(parts) + "</div>"
    rng = f"<span>범위 {esc(fmt_fn(low))}~{esc(fmt_fn(high))}</span>" if low is not None and high is not None else ""
    return f'<div class="strip">{svg}<div class="legend"><span>컨센 {esc(fmt_fn(cons))}</span>{rng}</div></div>'


VERDICT_TINT = {"big_beat": "mint", "beat": "mint", "inline": "apricot", "miss": "rose", "big_miss": "rose"}


def stat_card(label: str, value: str, qoq, yoy, verdict: Verdict, strip: str, *, i: int, source: str) -> str:
    chip = verdict_chip(verdict) if verdict.code != "na" else ""
    body = (f'<div class="stat"><div class="card-head" style="margin-bottom:0"><span class="label">{esc(label)}</span>{chip}</div>'
            f'<div class="value">{esc(value)}</div><div class="deltas">{delta(qoq, "QoQ")}{delta(yoy, "YoY")}</div>{strip}'
            f'<div style="margin-top:10px">{src_badge(source)}</div></div>')
    tint = VERDICT_TINT.get(verdict.code, "")
    return f'<div class="el-card {("tint-" + tint) if tint else ""}" style="--i:{int(i)}">{body}</div>'


TONE_HUE = {"자신감": 158, "긍정": 168, "중립": 230, "신중": 38, "부정": 8}


def tone_hue(score: float | None, label: str | None = None) -> int | None:
    """톤이 없으면 None — 오브는 회색·반쯤 감은 눈으로 '분석 전'을 말한다."""
    if label in TONE_HUE:
        return TONE_HUE[label]
    if score is None:
        return None
    return 168 if score > 0.35 else 230 if score > -0.1 else 38 if score > -0.45 else 8


def orb(score: float | None = None, label: str | None = None, size: str = "") -> str:
    h = tone_hue(score, label)
    if h is None:
        return f'<div class="orb idle {esc(size)}" aria-hidden="true"></div>'
    return f'<div class="orb {esc(size)}" style="--h:{h}" aria-hidden="true"></div>'


def tone_meter(score: float | None) -> str:
    if score is None:
        return ""
    left = (max(-1.0, min(1.0, score)) + 1) / 2 * 100
    return f'<div class="tone-meter"><i style="left:{left:.1f}%"></i></div><div class="strip"><div class="legend"><span>부정</span><span>중립</span><span>긍정</span></div></div>'


def empty(text_html: str, with_orb: bool = False) -> str:
    return f'<div class="empty">{orb(size="sm") if with_orb else ""}<div>{text_html}</div></div>'


def table(headers: list[str], rows: list[list[str]], raw_cols: set[int] | None = None, text: bool = False) -> str:
    """raw_cols에 든 열은 이미 이스케이프된 HTML로 취급한다."""
    raw_cols = raw_cols or set()
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c if j in raw_cols else esc(c)}</td>" for j, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<div class="table-wrap"><table class="el-table{' text' if text else ''}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def colored_pct(v) -> str:
    cls = "flat" if v is None else "up" if v > 0 else "down" if v < 0 else "flat"
    return f'<span class="{cls}">{esc(fmt.pct(v))}</span>'


def page_title(title: str, sub: str = "") -> None:
    st.html(f'<div class="page-title page-in"><div><h1>{esc(title)}</h1>' + (f"<p>{esc(sub)}</p>" if sub else "") + "</div></div>")


def money_unit(values, currency: str) -> tuple[float, str]:
    """차트 축 단위. 원화는 조/억, 그 외는 B/M — 'T'(SI 접두어)가 원화 축에 찍히지 않게."""
    vals = [abs(v) for v in values if v is not None and v == v]
    top = max(vals) if vals else 0
    if currency == "KRW":
        return (1e12, "조") if top >= 1e12 else (1e8, "억")
    return (1e9, "B") if top >= 1e9 else (1e6, "M")


def plot_layout(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Pretendard, system-ui, sans-serif", color=INK, size=12),
        legend=dict(orientation="h", y=1.08, x=0, bgcolor="rgba(0,0,0,0)", font=dict(size=12)),
        hoverlabel=dict(bgcolor="#fff", bordercolor=LINE, font=dict(family="Pretendard", color=INK)),
        colorway=SERIES, bargap=0.35,
    )
    fig.update_xaxes(showgrid=False, linecolor=LINE, tickfont=dict(color=INK3))
    fig.update_yaxes(gridcolor="rgba(18,20,26,.06)", zeroline=False, tickfont=dict(color=INK3))
    return fig
