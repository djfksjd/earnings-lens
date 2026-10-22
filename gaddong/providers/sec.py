"""SEC EDGAR: 미국 8-K(Item 2.02) 실적 보도자료 원문. 키 없음, User-Agent(연락처) 필수.

SEC 정책: 초당 10회 이하, User-Agent에 이름과 이메일. https://www.sec.gov/os/accessing-edgar-data
"""
from __future__ import annotations

import html as htmllib
import json
import re
import time
from datetime import date

from .. import config
from . import xbrl
from .http import ProviderError, get

_HTML_TAG = re.compile(r"<[^>]+>")
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
_HREF = re.compile(r'href="(/Archives/edgar/data/[^"]+)"', re.I)


def _headers() -> dict:
    ua = config.SEC_USER_AGENT
    if not ua or "@" not in ua:
        raise ProviderError("SEC_USER_AGENT(예: 'Hong Gildong you@example.com')를 .env에 넣어주세요.")
    return {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}


def _cached_json(name: str, url: str, max_age: int) -> dict:
    path = config.CACHE_DIR / "sec" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and time.time() - path.stat().st_mtime < max_age:
        return json.loads(path.read_text(encoding="utf-8"))
    data = get(url, headers=_headers()).json()
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def cik(ticker: str) -> int:
    data = _cached_json("company_tickers.json", "https://www.sec.gov/files/company_tickers.json", 7 * 86400)
    t = ticker.upper().replace(".", "-")
    for row in data.values():
        if row.get("ticker", "").upper() == t:
            return int(row["cik_str"])
    raise ProviderError(f"SEC에서 {ticker}를 찾지 못했습니다(미국 상장사만 지원).")


def earnings_filings(ticker: str, limit: int = 6) -> list[dict]:
    """Item 2.02(실적 발표) 8-K 목록, 최신순."""
    c = cik(ticker)
    sub = _cached_json(f"sub_{c}.json", f"https://data.sec.gov/submissions/CIK{c:010d}.json", 6 * 3600)
    r = sub["filings"]["recent"]
    out = []
    for i, form in enumerate(r["form"]):
        if form in ("8-K", "8-K/A") and "2.02" in (r["items"][i] or ""):
            out.append({"cik": c, "accession": r["accessionNumber"][i], "date": r["filingDate"][i]})
            if len(out) >= limit:
                break
    return out


def exhibits(filing: dict) -> list[dict]:
    acc = filing["accession"]
    url = f"https://www.sec.gov/Archives/edgar/data/{filing['cik']}/{acc.replace('-', '')}/{acc}-index.htm"
    page = get(url, headers=_headers()).text
    out = []
    for row in _ROW.findall(page):
        cells = [_HTML_TAG.sub("", c).strip() for c in _CELL.findall(row)]
        href = _HREF.search(row)
        if href and any(c.upper().startswith("EX-99") for c in cells):
            kind = next(c for c in cells if c.upper().startswith("EX-99"))
            desc = cells[1] if len(cells) > 1 else ""
            out.append({"type": kind.upper(), "description": desc, "url": "https://www.sec.gov" + href.group(1)})
    return out


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d)>", "\n", raw)
    raw = re.sub(r"(?i)</t[dh]>", " | ", raw)
    text = htmllib.unescape(_HTML_TAG.sub(" ", raw))
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def exhibit_text(url: str, max_chars: int = 120_000) -> str:
    if not url.startswith("https://www.sec.gov/Archives/"):
        raise ProviderError("SEC 원문 주소만 허용됩니다.")
    key = re.sub(r"[^A-Za-z0-9]", "_", url.split("/Archives/edgar/data/")[-1])[-150:]
    path = config.CACHE_DIR / "sec" / f"doc_{key}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    text = html_to_text(get(url, headers=_headers(), timeout=30).text)[:max_chars]
    path.write_text(text, encoding="utf-8")
    return text


# ---------- 10-Q/10-K XBRL: 사업부문 ----------

def periodic_filings(ticker: str) -> list[dict]:
    """10-Q·10-K 목록(정정 포함), 최신순. reportDate = 분기말."""
    c = cik(ticker)
    sub = _cached_json(f"sub_{c}.json", f"https://data.sec.gov/submissions/CIK{c:010d}.json", 6 * 3600)
    r = sub["filings"]["recent"]
    return [{"cik": c, "accession": r["accessionNumber"][i], "end": r["reportDate"][i], "form": r["form"][i]}
            for i, form in enumerate(r["form"]) if form in ("10-Q", "10-K", "10-Q/A", "10-K/A") and r["reportDate"][i]]


def _xbrl_files(filing: dict) -> tuple[bytes, bytes] | None:
    """(인스턴스, 레이블). 공시는 바뀌지 않으므로 영구 캐시."""
    acc = filing["accession"].replace("-", "")
    folder = config.CACHE_DIR / "sec" / "xbrl" / acc
    inst, lab = folder / "instance.xml", folder / "lab.xml"
    if inst.exists():
        return inst.read_bytes(), lab.read_bytes() if lab.exists() else b""
    base = f"https://www.sec.gov/Archives/edgar/data/{filing['cik']}/{acc}"
    names = [i["name"] for i in get(f"{base}/index.json", headers=_headers()).json()["directory"]["item"]]
    inst_name = next((n for n in names if n.endswith("_htm.xml")), None) or next(
        (n for n in names if n.endswith(".xml") and not re.search(r"_(cal|def|lab|pre)\.xml$|FilingSummary", n)), None)
    if not inst_name:
        return None
    lab_name = next((n for n in names if n.endswith("_lab.xml")), None)
    folder.mkdir(parents=True, exist_ok=True)
    inst.write_bytes(get(f"{base}/{inst_name}", headers=_headers(), timeout=60).content)
    if lab_name:
        lab.write_bytes(get(f"{base}/{lab_name}", headers=_headers(), timeout=60).content)
    return inst.read_bytes(), lab.read_bytes() if lab.exists() else b""


def _loader(ticker: str):
    filings = periodic_filings(ticker)
    loaded: dict[str, tuple | None] = {}

    def load(d: date):
        f = next((f for f in filings if abs((date.fromisoformat(f["end"]) - d).days) <= 15), None)
        if not f:
            return None
        if f["accession"] not in loaded:
            files = _xbrl_files(f)
            loaded[f["accession"]] = (xbrl.parse_instance(files[0]), xbrl.parse_labels(files[1], "en") if files[1] else {},
                                      date.fromisoformat(f["end"])) if files else None
        return loaded[f["accession"]]

    return load


def _end(period: str) -> date:
    return date.fromisoformat(period + "-01").replace(day=28)  # 월 안의 어느 날이든 ±15일 안에 분기말이 있다


def segments(ticker: str, period: str) -> tuple[list[dict], str]:
    """분기 사업부문 매출·영업이익(전분기·전년동기 포함). period = 'YYYY-MM'(분기말 월)."""
    return xbrl.build_segments(_loader(ticker), _end(period))


def quarterly_totals(ticker: str, periods: list[str]) -> dict[str, dict[str, float]]:
    """전사 분기 매출·영업이익·순이익(공시 원본). yfinance가 비운 분기를 채우는 데 쓴다."""
    load = _loader(ticker)
    return {p: v for p in periods if (v := xbrl.build_totals(load, _end(p)))}
