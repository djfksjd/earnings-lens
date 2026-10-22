"""KRX 정보데이터시스템 Open API: 한국 공식 일별 시세(종가 동시호가 반영). 무료 키(KRX_OPEN_API_KEY).

키와 별도로 서비스마다 '이용신청' 승인이 필요하다(유가증권/코스닥 일별매매정보, KOSPI/KOSDAQ 시리즈 일별시세).
승인 전에는 401을 돌려준다. 하루 호출 한도가 있어 날짜별 결과를 영구 캐시한다(지난 날짜의 시세는 바뀌지 않는다).
https://openapi.krx.co.kr
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from .. import config
from .http import ProviderError, get

BASE = "https://data-dbg.krx.co.kr/svc/apis"
_SERVICES = {"KS": "sto/stk_bydd_trd", "KQ": "sto/ksq_bydd_trd"}
_INDEX = {"^KS11": ("idx/kospi_dd_trd", "코스피"), "^KQ11": ("idx/kosdaq_dd_trd", "코스닥")}
_KST = timezone(timedelta(hours=9))


def available() -> bool:
    return config.has("KRX_OPEN_API_KEY")


def _num(v) -> float | None:
    if v in (None, "", "-"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _short(code: str) -> str:
    """ISIN(KR7005930003) 또는 단축코드(005930) → 단축코드."""
    code = (code or "").strip()
    return code[3:9] if len(code) == 12 and code.startswith("KR") else code


def _day(service: str, day: date) -> list[dict]:
    """하루치 전 종목 시세. 오늘·미래 날짜는 아직 확정 전이라 캐시하지 않는다."""
    today = datetime.now(_KST).date()
    if day >= today:
        return []
    path = config.CACHE_DIR / "krx" / service.replace("/", "_") / f"{day:%Y%m%d}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    r = get(f"{BASE}/{service}", params={"basDd": f"{day:%Y%m%d}"},
            headers={"AUTH_KEY": config.secret("KRX_OPEN_API_KEY")}, retries=1)
    data = r.json()
    if str(data.get("respCode", "")) == "401":
        raise ProviderError("KRX 서비스 이용 승인 전입니다. openapi.krx.co.kr에서 서비스별 이용신청을 확인하세요.")
    rows = data.get("OutBlock_1") or []
    if not rows and day >= today - timedelta(days=4):
        return []  # 최근 날짜의 빈 응답은 '아직 집계 전'일 수 있어 캐시하지 않는다(휴장일이면 며칠 뒤 캐시된다)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def _spec(ticker: str):
    if ticker in _INDEX:
        service, name = _INDEX[ticker]
        return service, (lambda r: r.get("IDX_NM") == name), ("OPNPRC_IDX", "HGPRC_IDX", "LWPRC_IDX", "CLSPRC_IDX", "ACC_TRDVOL")
    code, mkt = ticker.split(".")
    return (_SERVICES[mkt], (lambda r: _short(r.get("ISU_CD")) == code or r.get("ISU_SRT_CD") == code),
            ("TDD_OPNPRC", "TDD_HGPRC", "TDD_LWPRC", "TDD_CLSPRC", "ACC_TRDVOL"))


def bar(ticker: str, day: date) -> dict | None:
    """하루 일봉. 휴장일·미상장이면 None."""
    service, pick, cols = _spec(ticker)
    row = next((r for r in _day(service, day) if pick(r)), None)
    if not row:
        return None
    vals = [_num(row.get(c)) for c in cols]
    return dict(zip(("Open", "High", "Low", "Close", "Volume"), vals)) if vals[3] else None


def fill_gaps(h: pd.DataFrame, ticker: str, start: date) -> tuple[pd.DataFrame, int]:
    """yfinance 일봉에서 종가가 빈 날과 통째로 빠진 평일만 KRX로 채운다. (결과, 채운 행 수)

    전 기간을 받지 않고 의심 날짜만 부르므로 호출 수가 적다. 휴장일은 빈 응답으로 캐시돼 다시 부르지 않는다."""
    today = datetime.now(_KST).date()
    h = h.copy()
    if not h.empty and h.index.tz is None:
        h.index = h.index.tz_localize("Asia/Seoul")
    have = {ts.date(): ts for ts in h.index if pd.notna(h.at[ts, "Close"])}
    nan_days = {ts.date(): ts for ts in h.index if pd.isna(h.at[ts, "Close"])}
    fixed = 0
    d = start
    while d < today:
        if d.weekday() < 5 and d not in have:
            row = bar(ticker, d)
            if row:
                ts = nan_days.get(d, pd.Timestamp(d).tz_localize("Asia/Seoul"))
                h.loc[ts, list(row)] = list(row.values())
                fixed += 1
        d += timedelta(days=1)
    return h.sort_index(), fixed
