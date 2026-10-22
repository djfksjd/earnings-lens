"""Motley Fool 컨콜 트랜스크립트 룰베이스 수집 (옵트인): 미국 기업 컨콜 전문.

robots.txt는 트랜스크립트 페이지를 막지 않지만, 이용약관은 robots·scripts 같은 자동 수단과 스크래핑을 금지하고
개인 비상업 사본 1부만 허용한다. 그래서 `.env`에 FOOL_SCRAPING_ENABLED=true를 직접 넣었을 때만,
버튼을 눌렀을 때 1건씩 받는다. 받은 원문은 영구 캐시해 다시 호출하지 않는다.
"""
from __future__ import annotations

import html as htmllib
import json
import re
from datetime import date

from .. import config
from ..security import safe_filename
from .http import ProviderError, get

_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/130 Safari/537.36 (personal research; gaddong)", "Accept-Language": "en-US"}
_LINK = re.compile(r"https://www\.fool\.com/earnings/call-transcripts/(\d{4})/(\d{2})/(\d{2})/[a-z0-9-]+/")
_P = re.compile(r"<p>(.*?)</p>", re.S)
_TAG = re.compile(r"<[^>]+>")


def _require():
    if not config.FOOL_ENABLED:
        raise ProviderError("Motley Fool 수집이 꺼져 있습니다(.env의 FOOL_SCRAPING_ENABLED).")


def _cache(ticker: str, fiscal_q: str):
    return config.CACHE_DIR / "transcripts" / f"fool_{safe_filename(ticker)}_{fiscal_q}.json"


def cached(ticker: str, fiscal_q: str) -> list[dict] | None:
    p = _cache(ticker, fiscal_q)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def find_url(links: list[str], ticker: str, fiscal_q: str, event: date | None) -> str | None:
    """회계분기 표기(q2-2027)가 든 주소 → 없으면 발표일 0~14일 뒤에 올라온 주소."""
    t = ticker.lower().replace(".", "-")
    mine = [u for u in dict.fromkeys(links) if f"-{t}-" in u]
    tag = f"q{fiscal_q[-1]}-{fiscal_q[:4]}"
    hit = next((u for u in mine if tag in u), None)
    if hit or event is None:
        return hit
    for u in mine:
        y, m, d = map(int, _LINK.match(u).groups())
        if 0 <= (date(y, m, d) - event).days <= 14:
            return u
    return None


def parse(page: str) -> list[dict]:
    """'Full Conference Call Transcript' 이후 문단 → 발언 목록."""
    i = page.find('id="full-conference-call-transcript"')
    if i < 0:
        return []
    body = page[i:]
    end = body.find("<h2", 50)  # 다음 소제목부터는 본문이 아니다(면책 문구 등)
    body = body[:end] if end > 0 else body
    turns: list[dict] = []
    for raw in _P.findall(body):
        if "This article is a transcript" in raw:
            break
        m = re.match(r"\s*<strong>(.*?)</strong>\s*(.*)", raw, re.S)
        text = htmllib.unescape(_TAG.sub("", m.group(2) if m else raw)).strip()
        if m:
            speaker = htmllib.unescape(_TAG.sub("", m.group(1))).strip().rstrip(":")
            turns.append({"speaker": speaker, "title": "", "content": text, "sentiment": None})
        elif turns and text:
            turns[-1]["content"] += "\n" + text
    return [t for t in turns if t["content"]]


def transcript(ticker: str, fiscal_q: str, event: date | None) -> list[dict]:
    _require()
    hit = cached(ticker, fiscal_q)
    if hit:
        return hit
    links: list[str] = []
    for exch in ("nasdaq", "nyse"):
        try:
            page = get(f"https://www.fool.com/quote/{exch}/{ticker.lower()}/", headers=_UA).text
        except ProviderError:
            continue
        links = [m.group(0) for m in _LINK.finditer(page)]
        if links:
            break
    url = find_url(links, ticker, fiscal_q, event)
    if not url:
        raise ProviderError(f"Motley Fool에서 {ticker} {fiscal_q} 트랜스크립트를 찾지 못했습니다.")
    turns = parse(get(url, headers=_UA, timeout=30).text)
    if len(turns) < 5:
        raise ProviderError("트랜스크립트 본문을 읽지 못했습니다(페이지 구조 변경 가능).")
    p = _cache(ticker, fiscal_q)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(turns, ensure_ascii=False), encoding="utf-8")
    return turns

