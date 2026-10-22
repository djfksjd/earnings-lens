"""사용자가 직접 넣는 데이터(my_inputs/)와 AI 결과(data/ai/) 읽기·쓰기.

우선순위: 내 입력(my_inputs) > AI 추출(data/ai) > 자동 수집.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from . import config
from .security import clean_period, safe_filename

SECTIONS = ("consensus", "actual_override", "segments", "kpis", "guidance", "tone", "quotes", "qa", "catalysts", "notes")

_SUFFIX = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12, "천": 1e3, "만": 1e4, "억": 1e8, "조": 1e12}
_AMT = re.compile(r"^\s*([-+]?[\d,]*\.?\d+)\s*(K|M|B|T|천|만|억|조)?\s*(원|달러|USD|KRW|\$)?\s*$", re.I)


def parse_amount(v):
    """숫자 또는 '41.1B', '1.2조', '3,500억원' 같은 문자열을 숫자로. 실패하면 None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("$", "").strip()
    if not s:
        return None
    # '1조 2,000억' 같은 복합 표기
    if "조" in s and "억" in s:
        jo, eok = s.split("조", 1)
        a, b = parse_amount(jo + "조"), parse_amount(eok)
        return a + b if a is not None and b is not None else None
    m = _AMT.match(s)
    if not m:
        return None
    num = float(m.group(1).replace(",", ""))
    suf = m.group(2)
    return num * _SUFFIX[suf.upper() if suf and suf.isascii() else suf] if suf else num


_TOTAL = re.compile(r"(합계|총계|전사|^\s*total\b|consolidated)", re.I)


def is_total_row(name) -> bool:
    """세그먼트 목록에 섞인 전사 합계 행인지."""
    return bool(name) and bool(_TOTAL.search(str(name)))


def _company_dir(ticker: str, base: Path | None = None) -> Path:
    return (base or config.MY_INPUTS) / "companies" / safe_filename(ticker)


def input_path(ticker: str, period: str, base: Path | None = None) -> Path:
    return _company_dir(ticker, base) / f"{clean_period(period)}.yaml"


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}  # safe_load: 임의 객체 생성 차단
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: 최상위는 키-값 형태여야 합니다.")
    return data


def load_inputs(ticker: str, period: str) -> tuple[dict, str]:
    """(데이터, 출처). 예시 폴더는 작성법 참고용이라 실제 종목 화면에 섞지 않는다."""
    p = input_path(ticker, period)
    if p.exists():
        return load_yaml(p), "내 입력"
    return {}, ""


def save_inputs(ticker: str, period: str, data: dict) -> Path:
    unknown = set(data) - set(SECTIONS)
    if unknown:
        raise ValueError(f"알 수 없는 항목: {', '.join(sorted(unknown))}")
    p = input_path(ticker, period)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


def validate_yaml_text(text: str) -> dict:
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("최상위는 키-값 형태여야 합니다.")
    unknown = set(data) - set(SECTIONS)
    if unknown:
        raise ValueError(f"알 수 없는 항목: {', '.join(sorted(unknown))} (허용: {', '.join(SECTIONS)})")
    for sec in ("segments", "kpis", "guidance", "quotes", "qa", "catalysts"):
        if data.get(sec) is not None and not isinstance(data[sec], list):
            raise ValueError(f"'{sec}'는 목록(- 로 시작)이어야 합니다.")
    return data


def watchlist() -> list[str]:
    for base in (config.MY_INPUTS, config.EXAMPLES):
        p = base / "watchlist.yaml"
        if p.exists():
            data = load_yaml(p)
            items = data.get("tickers") or []
            if items:
                return [str(t) for t in items]
    return ["NVDA", "005930.KS"]


def save_watchlist(tickers: list[str]) -> None:
    p = config.MY_INPUTS / "watchlist.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump({"tickers": tickers}, allow_unicode=True), encoding="utf-8")


def transcript_text(ticker: str, period: str) -> str | None:
    """my_inputs/transcripts/<티커>_<분기>.txt (직접 붙여넣은 컨콜 원문)."""
    p = config.MY_INPUTS / "transcripts" / f"{safe_filename(ticker)}_{clean_period(period)}.txt"
    return p.read_text(encoding="utf-8") if p.exists() else None


def save_transcript(ticker: str, period: str, text: str) -> Path:
    p = config.MY_INPUTS / "transcripts" / f"{safe_filename(ticker)}_{clean_period(period)}.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


# ---------- AI 결과 ----------

def ai_path(ticker: str, period: str, kind: str) -> Path:
    if not re.fullmatch(r"[a-z_]{2,30}", kind):
        raise ValueError("bad kind")
    return config.AI_DIR / f"{safe_filename(ticker)}_{clean_period(period)}_{kind}.json"


def load_ai(ticker: str, period: str, kind: str) -> dict:
    p = ai_path(ticker, period, kind)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_ai(ticker: str, period: str, kind: str, data: dict) -> None:
    ai_path(ticker, period, kind).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def combined_ai(ticker: str, period: str) -> dict:
    """보도자료·컨콜 AI 결과를 합친다. 목록 항목(가이던스·체크포인트 등)은 둘 다 살리고
    보도자료(공식 숫자)를 앞에 둔다. 한쪽만 쓰면 다른 쪽 가이던스가 조용히 사라진다."""
    ai: dict = {}
    for kind in ("release", "call"):
        for k, v in load_ai(ticker, period, kind).items():
            if isinstance(v, list) and isinstance(ai.get(k), list):
                ai[k] = ai[k] + v
            else:
                ai.setdefault(k, v)
    return ai


def merged(ticker: str, period: str) -> dict:
    """섹션별로 내 입력 > AI 결과. 각 섹션에 출처 라벨을 붙인다."""
    mine, mine_src = load_inputs(ticker, period)
    ai = combined_ai(ticker, period)
    out: dict = {"_source": {}}
    for sec in SECTIONS:
        if mine.get(sec):
            out[sec], out["_source"][sec] = mine[sec], mine_src
        elif ai.get(sec):
            out[sec], out["_source"][sec] = ai[sec], "AI 추출"
    return out


_MONEY_KEYS = re.compile(r"^(revenue|operating_income|ebitda|net_income)(_prev_[qy]|_low|_high)?$")


def readable_amounts(data: dict, money) -> dict:
    """확정 파일을 사람이 고치기 쉽게: 세그먼트·컨센서스의 금액을 '95.00조', '$89.00B'로 바꾼다.
    money(value) -> str. parse_amount가 다시 숫자로 읽으므로 계산은 그대로다."""
    def conv(d: dict) -> dict:
        return {k: (money(v) if _MONEY_KEYS.match(k) and isinstance(v, (int, float)) and not isinstance(v, bool) else v)
                for k, v in d.items()}
    out = dict(data)
    if isinstance(out.get("segments"), list):
        out["segments"] = [conv(x) if isinstance(x, dict) else x for x in out["segments"]]
    for sec in ("consensus", "actual_override"):
        if isinstance(out.get(sec), dict):
            out[sec] = conv(out[sec])
    return out

