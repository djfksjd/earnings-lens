"""숫자 표기: 원화는 조·억, 달러는 B·M."""
from __future__ import annotations

import math


def _bad(v) -> bool:
    return v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))


def money(v, currency: str) -> str:
    if _bad(v):
        return "—"
    sign = "−" if v < 0 else ""
    a = abs(v)
    if currency == "KRW":
        if a >= 1e12:
            return f"{sign}{a / 1e12:,.2f}조"
        if a >= 1e8:
            return f"{sign}{a / 1e8:,.0f}억"
        return f"{sign}{a:,.0f}원"
    sym = "$" if currency in ("USD", "") else ""
    unit = "" if sym else f" {currency}"
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            return f"{sign}{sym}{a / div:,.2f}{suf}{unit}"
    return f"{sign}{sym}{a:,.2f}{unit}"


def eps(v, currency: str) -> str:
    if _bad(v):
        return "—"
    if currency == "KRW":
        return f"{v:,.0f}원"
    return f"{'−' if v < 0 else ''}${abs(v):,.2f}"


def metric_value(metric: str, v, currency: str) -> str:
    return eps(v, currency) if metric == "eps" else money(v, currency)


def pct(v, digits: int = 1, signed: bool = True) -> str:
    if _bad(v):
        return "—"
    s = f"{abs(v):,.{digits}f}%"
    if not signed:
        return s
    return ("+" if v > 0 else "−" if v < 0 else "±") + s


def price(v, currency: str) -> str:
    if _bad(v):
        return "—"
    return f"{v:,.0f}원" if currency == "KRW" else f"${v:,.2f}"


def plain(v, unit: str = "") -> str:
    if _bad(v):
        return "—"
    if isinstance(v, (int, float)):
        txt = f"{v:,.0f}" if abs(v) >= 100 or float(v).is_integer() else f"{v:,.2f}"
    else:
        txt = str(v)
    return f"{txt}{(' ' + unit) if unit else ''}"
