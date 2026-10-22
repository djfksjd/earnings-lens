"""QoQ/YoY 변화와 컨센서스 대비 판정."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

LABELS = {"revenue": "매출액", "operating_income": "영업이익", "ebitda": "EBITDA", "eps": "EPS", "net_income": "순이익"}

# 컨센서스 대비 괴리율 기준(%). |diff| ≤ INLINE → 부합, ≥ BIG → 서프라이즈/쇼크
INLINE = 2.0
BIG = 10.0


def prev_period(period: str, months: int) -> str:
    y, m = int(period[:4]), int(period[5:7])
    total = y * 12 + (m - 1) - months
    return f"{total // 12}-{total % 12 + 1:02d}"


def pct_change(cur, base):
    """전기 대비 증감률(%). 기준이 음수면 개선/악화 방향이 뒤집히므로 |base|로 나눈다."""
    if cur is None or base is None or pd.isna(cur) or pd.isna(base) or base == 0:
        return None
    return (cur - base) / abs(base) * 100


def _nearest(df: pd.DataFrame, period: str) -> str | None:
    """결산월이 한두 달 어긋나는 경우(예: 1월 말 vs 2월 1일)를 허용해 가장 가까운 분기 키."""
    if period in df.index:
        return period
    for d in (1, -1, 2, -2):
        p = prev_period(period, d)
        if p in df.index:
            return p
    return None


def change_table(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """period 기준 각 지표의 값·전분기·전년동기·QoQ·YoY."""
    rows = []
    for metric in df.columns:
        cur = df.at[period, metric] if period in df.index else None
        pq, py = _nearest(df, prev_period(period, 3)), _nearest(df, prev_period(period, 12))
        vq = df.at[pq, metric] if pq else None
        vy = df.at[py, metric] if py else None
        rows.append({"metric": metric, "label": LABELS.get(metric, metric), "value": cur, "prev_q": vq, "prev_y": vy,
                     "qoq": pct_change(cur, vq), "yoy": pct_change(cur, vy)})
    return pd.DataFrame(rows).set_index("metric")


@dataclass
class Verdict:
    code: str   # big_beat | beat | inline | miss | big_miss | na
    label: str
    diff_pct: float | None


def verdict(actual, estimate) -> Verdict:
    d = pct_change(actual, estimate)
    if d is None:
        return Verdict("na", "컨센서스 없음", None)
    if d >= BIG:
        return Verdict("big_beat", "어닝 서프라이즈", d)
    if d > INLINE:
        return Verdict("beat", "상회", d)
    if d <= -BIG:
        return Verdict("big_miss", "어닝 쇼크", d)
    if d < -INLINE:
        return Verdict("miss", "하회", d)
    return Verdict("inline", "부합", d)


def overall(verdicts: list[Verdict]) -> Verdict:
    """헤드라인 판정: 영업이익(없으면 EPS) 우선, 나머지는 보조."""
    real = [v for v in verdicts if v.code != "na"]
    if not real:
        return Verdict("na", "컨센서스 데이터 없음", None)
    return real[0]
