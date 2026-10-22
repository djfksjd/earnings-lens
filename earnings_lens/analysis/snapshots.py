"""컨센서스 스냅샷.

무료 소스는 '지난 분기에 발표 직전 컨센서스가 얼마였는지'(특히 매출·영업이익)를 주지 않는다.
그래서 앱을 열 때마다 다음 분기 컨센서스를 data/snapshots에 저장해 두고,
실적이 나오면 발표 직전 마지막 스냅샷과 비교한다. 실적 시즌 전에 한 번만 열어두면 된다.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from .. import config
from ..security import safe_filename


def _path(ticker: str):
    return config.SNAPSHOT_DIR / f"{safe_filename(ticker)}.jsonl"


def record(ticker: str, period: str, values: dict, source: str) -> None:
    """하루에 한 번만, 값이 있을 때만 기록한다."""
    clean = {k: v for k, v in values.items() if isinstance(v, (int, float)) and v == v}
    if not clean:
        return
    today = date.today().isoformat()
    p = _path(ticker)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines()[-30:]:
            row = json.loads(line)
            if row["date"] == today and row["period"] == period and row["source"] == source:
                return
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"date": today, "period": period, "source": source, "values": clean}) + "\n")


def latest_before(ticker: str, period: str, report_date: str | None) -> dict:
    """해당 분기의 발표일 이전 마지막 스냅샷 값(지표별로 가장 최근 값)."""
    p = _path(ticker)
    if not p.exists():
        return {}
    cutoff = report_date or datetime.now().date().isoformat()
    out: dict = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["period"] == period and row["date"] < cutoff:
            for k, v in row["values"].items():
                out[k] = {"value": v, "date": row["date"], "source": row["source"]}
    return out
