"""MarketBeat 실적 페이지 룰베이스 수집 (옵트인): 미국 과거 분기 매출·EPS 컨센서스.

robots.txt는 이 페이지를 막지 않지만, 이용약관은 제공된 화면 외 접근과 대량 재배포를 금지하고
개인 1인 사용만 허용한다. 그래서 `.env`에 MARKETBEAT_SCRAPING_ENABLED=true를 직접 넣었을 때만 동작한다.
종목당 하루 1번만 호출하고 결과를 캐시한다.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import time
from datetime import datetime

from .. import config
from ..security import safe_filename
from .http import ProviderError, get

_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/130 Safari/537.36 (personal research; gaddong)", "Accept-Language": "en-US"}
_ROW = re.compile(r"<tr.*?</tr>", re.S)
_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
_TAG = re.compile(r"<[^>]+>")
_SUFFIX = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def _require():
    if not config.MARKETBEAT_ENABLED:
        raise ProviderError("MarketBeat 수집이 꺼져 있습니다(.env의 MARKETBEAT_SCRAPING_ENABLED).")


def _money(s: str) -> float | None:
    m = re.fullmatch(r"\(?-?\$?(-?[\d,]*\.?\d+)([KMBT])?\)?", s.replace(" ", ""))
    if not m:
        return None
    v = float(m.group(1).replace(",", "")) * _SUFFIX.get(m.group(2) or "", 1)
    return -v if s.strip().startswith(("-", "(")) and v > 0 else v


def parse(page: str) -> list[dict]:
    """'Earnings History by Quarter' 표 → [{date, quarter, eps_est, eps_actual, revenue_est, revenue_actual}]."""
    i = page.find("Earnings History by Quarter")
    table = re.search(r"<table.*?</table>", page[i:], re.S) if i >= 0 else None
    if not table:
        return []
    rows = []
    for tr in _ROW.findall(table.group(0)):
        cells = [htmllib.unescape(_TAG.sub("", c)).strip() for c in _CELL.findall(tr)]
        if len(cells) < 8 or "Estimated" in cells[0]:
            continue
        try:
            day = datetime.strptime(cells[0], "%m/%d/%Y").date()
        except ValueError:
            continue  # 머리글 행
        rows.append({"date": day.isoformat(), "quarter": cells[1], "eps_est": _money(cells[2]),
                     "eps_actual": _money(cells[3]), "revenue_est": _money(cells[6]), "revenue_actual": _money(cells[7])})
    return rows


def history(ticker: str) -> list[dict]:
    _require()
    path = config.CACHE_DIR / "marketbeat" / f"{safe_filename(ticker)}.json"
    if path.exists() and time.time() - path.stat().st_mtime < 86400:
        return json.loads(path.read_text(encoding="utf-8"))
    # 거래소가 틀리면 MarketBeat가 올바른 주소로 돌려보낸다(301)
    page = get(f"https://www.marketbeat.com/stocks/NASDAQ/{ticker.upper()}/earnings/", headers=_UA).text
    rows = parse(page)
    if not rows:
        raise ProviderError("MarketBeat 실적 표를 찾지 못했습니다(페이지 구조 변경 가능).")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")
    return rows
