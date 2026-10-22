"""XBRL 인스턴스 공용 파서 (SEC 10-Q/10-K, DART 정기보고서 원본 공통).

공시 원본의 숫자를 그대로 읽는다. AI 추출과 달리 단위·부호가 틀리지 않는다.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from datetime import date
from xml.etree import ElementTree as ET

_X = "{http://www.xbrl.org/2003/instance}"
_DI = "{http://xbrl.org/2006/xbrldi}"
_LINK = "{http://www.xbrl.org/2003/linkbase}"
_XLINK = "{http://www.w3.org/1999/xlink}"


@dataclass(frozen=True)
class Fact:
    concept: str            # 접두어 없는 이름 (예: Revenues, OperatingIncomeLoss)
    dims: tuple             # ((축, 멤버), ...) 정렬됨. 축·멤버는 'prefix:Name'
    start: date | None
    end: date
    value: float

    @property
    def days(self) -> int:
        return (self.end - self.start).days if self.start else 0

    def dim(self, axis_name: str) -> str | None:
        """축 이름(접두어 무시)으로 멤버를 찾는다."""
        for a, m in self.dims:
            if a.split(":")[-1] == axis_name:
                return m
        return None


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s.strip()[:10]) if s else None


def parse_instance(raw: bytes | str) -> list[Fact]:
    """숫자 사실(fact)만 돌려준다. nil·텍스트 블록은 버린다."""
    root = ET.fromstring(raw)
    ctx: dict[str, tuple] = {}
    for c in root.iter(_X + "context"):
        dims = tuple(sorted((m.get("dimension"), (m.text or "").strip()) for m in c.iter(_DI + "explicitMember")))
        p = c.find(_X + "period")
        if p is None:
            continue
        end = p.findtext(_X + "endDate") or p.findtext(_X + "instant")
        ctx[c.get("id")] = (dims, _d(p.findtext(_X + "startDate")), _d(end))
    out = []
    for el in root:
        ref = el.get("contextRef")
        if ref not in ctx or el.get("unitRef") is None or not (el.text or "").strip():
            continue
        try:
            v = float(el.text.strip())
        except ValueError:
            continue
        dims, start, end = ctx[ref]
        out.append(Fact(el.tag.split("}")[-1], dims, start, end, v))
    return out


def parse_labels(raw: bytes | str, lang: str | None = None) -> dict[str, str]:
    """레이블 링크베이스 → {'prefix_Name' 또는 'Name': 표준 레이블}."""
    root = ET.fromstring(raw)
    out: dict[str, str] = {}
    for link in root.iter(_LINK + "labelLink"):
        loc = {l.get(_XLINK + "label"): l.get(_XLINK + "href", "").split("#")[-1] for l in link.iter(_LINK + "loc")}
        lab: dict[str, str] = {}
        for l in link.iter(_LINK + "label"):
            if lang and not (l.get("{http://www.w3.org/XML/1998/namespace}lang") or "").startswith(lang):
                continue
            role = l.get(_XLINK + "role", "")
            if role.endswith("/label") or l.get(_XLINK + "label") not in lab:
                lab[l.get(_XLINK + "label")] = (l.text or "").strip()
        for arc in link.iter(_LINK + "labelArc"):
            frm, to = loc.get(arc.get(_XLINK + "from")), arc.get(_XLINK + "to")
            if frm and to in lab and lab[to]:
                out.setdefault(frm, lab[to])
    return out


_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_JUNK = re.compile(r"(Member)?Of(OperatingSegments|ProductsAndServices|Segments).*$|(Segment)?Member$")


def member_name(member: str, labels: dict[str, str]) -> str:
    """멤버 QName → 사람이 읽는 이름. 레이블이 있으면 레이블, 없으면 이름을 풀어 쓴다."""
    local = member.split(":")[-1]
    key = member.replace(":", "_")
    for k in (key, local):
        if k in labels:
            name = labels[k]
            return re.sub(r"\s*\[(member|멤버)\]\s*$", "", name, flags=re.I).strip()
    return _CAMEL.sub(" ", _JUNK.sub("", local)).strip() or local


def quarter_value(facts: list[Fact], concepts: tuple[str, ...], end: date, *, dims: tuple = ()) -> float | None:
    """end로 끝나는 약 3개월(80~100일) 값. 개념 우선순위대로."""
    for c in concepts:
        for f in facts:
            if f.concept == c and f.end == end and f.dims == dims and 80 <= f.days <= 100:
                return f.value
    return None


def ytd_value(facts: list[Fact], concepts: tuple[str, ...], end: date, *, dims: tuple = ()) -> tuple[float | None, int]:
    """end로 끝나는 가장 긴 기간(연초 누적) 값과 그 일수."""
    best: tuple[float | None, int] = (None, 0)
    for c in concepts:
        for f in facts:
            if f.concept == c and f.end == end and f.dims == dims and f.days > best[1]:
                best = (f.value, f.days)
        if best[0] is not None:
            return best
    return best


# ---------- 사업부문 ----------
# 미국(US-GAAP)과 한국(K-IFRS) 모두 '부문 축'에 회사별 멤버를 달아 공시한다.
_SEG_AXES = {"StatementBusinessSegmentsAxis", "SegmentsAxis", "OperatingSegmentsAxis", "SegmentConsolidationItemsAxis"}
_PROD_AXES = {"ProductOrServiceAxis", "ProductsAndServicesAxis"}
# 부문 값과 함께 붙어도 되는 축(연결 기준·보고부문 합계 표시)
_OK_DIMS = {("ConsolidatedAndSeparateFinancialStatementsAxis", "ConsolidatedMember"),
            ("ConsolidationItemsAxis", "OperatingSegmentsMember"),
            ("SegmentConsolidationItemsAxis", "OperatingSegmentsMember")}
_STANDARD = ("us-gaap:", "ifrs-full:", "dart:", "srt:")
SEG_REVENUE = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
               "RevenueFromContractWithCustomerIncludingAssessedTax", "Revenue", "RevenueFromContractsWithCustomers",
               "SalesRevenueNet")
SEG_OPERATING = ("OperatingIncomeLoss",)


def _seg_member(f: Fact, axes: set[str], separate_ok: bool) -> str | None:
    seg, ok = None, True
    for a, m in f.dims:
        an, mn = a.split(":")[-1], m.split(":")[-1]
        if an in axes and not m.startswith(_STANDARD):
            if seg:
                return None  # 부문 두 개가 겹친 교차표는 쓰지 않는다
            seg = m
        elif (an, mn) in _OK_DIMS or (separate_ok and mn == "SeparateMember"):
            continue
        else:
            ok = False
    return seg if ok else None


def segment_values(facts: list[Fact], end: date, axes: set[str], separate_ok: bool = False) -> dict[str, dict]:
    """{멤버: {'revenue': (3개월값|None, 누적값, 누적일수), 'operating_income': ...}} — end 시점."""
    out: dict[str, dict] = {}
    for kind, concepts in (("revenue", SEG_REVENUE), ("operating_income", SEG_OPERATING)):
        for c in concepts:
            found = False
            for f in facts:
                if f.concept != c or f.end != end or not f.start or f.days < 80:
                    continue
                m = _seg_member(f, axes, separate_ok)
                if not m:
                    continue
                found = True
                q, ytd, days = out.setdefault(m, {}).get(kind, (None, None, 0))
                if f.days <= 100:
                    q = f.value
                if f.days >= days:
                    ytd, days = f.value, f.days
                out[m][kind] = (q, ytd, days)
            if found:
                break  # 매출 개념은 회사마다 하나만 쓴다
    return out


def pick_segments(facts: list[Fact], end: date) -> tuple[dict[str, dict], set[str], bool]:
    """보고부문 → (없으면) 제품·서비스 순으로, 연결 → 개별 순으로 찾는다. (값, 쓴 축, 개별 여부)."""
    for axes in (_SEG_AXES, _PROD_AXES):
        for separate_ok in (False, True):
            vals = segment_values(facts, end, axes, separate_ok)
            if any("revenue" in v for v in vals.values()):
                return vals, axes, separate_ok
    return {}, set(), False


def quarter_of(cur: tuple | None, prev: tuple | None) -> float | None:
    """(3개월, 누적, 일수) 두 개로 분기 값을 구한다. 3개월 값이 없으면 누적 차이."""
    if not cur:
        return None
    q, ytd, days = cur
    if q is not None:
        return q
    if ytd is not None and days <= 100:
        return ytd
    if ytd is not None and prev and prev[1] is not None and 60 <= days - prev[2] <= 120:
        return ytd - prev[1]
    return None


def _near(target: date, days: int) -> date:
    return date.fromordinal(target.toordinal() - days)


def _norm(name: str) -> str:
    """연도별로 멤버 이름이 조금씩 달라도(오타 수정·'부문' 유무) 같은 부문으로 맞춘다."""
    n = re.sub(r"\[[^\]]*\]|segment|부문|\s|[.,()㈜]", "", name.lower())
    return n


def _fuzzy(src: dict, name: str) -> dict | None:
    """공시 레이블 오타(Haman/Harman) 정도의 차이만 같은 부문으로 본다."""
    names = [k[1:] for k in src if k.startswith("#")]
    hit = difflib.get_close_matches(name, names, n=1, cutoff=0.8)
    return src["#" + hit[0]] if hit else None


def build_segments(load, end: date) -> tuple[list[dict], str]:
    """분기 부문표. load(날짜) → (facts, labels, 실제 분기말) | None. 날짜는 ±15일 안의 보고서를 찾는다.

    돌려주는 행: name, revenue, operating_income, *_prev_q, *_prev_y. 두 번째 값은 쓴 축 설명.
    """
    cur = load(end)
    if not cur:
        return [], ""
    facts, labels, end = cur
    vals, axes, separate_ok = pick_segments(facts, end)
    if not vals:
        return [], ""
    memo: dict[date, tuple[dict, dict]] = {end: (vals, labels)}

    def at(d: date) -> tuple[dict, dict, date | None]:
        rep = load(d)
        if not rep:
            return {}, {}, None
        if rep[2] not in memo:
            memo[rep[2]] = (segment_values(rep[0], rep[2], axes, separate_ok), rep[1])
        return (*memo[rep[2]], rep[2])

    def quarter_map(d: date) -> dict[str, dict]:
        """{멤버 또는 '#정규화 이름': {revenue, operating_income}}"""
        v, labs, real = at(d)
        if real is None:
            return {}
        prev, prev_labs, _ = at(_near(real, 91))
        prev_by_name = {_norm(member_name(m, prev_labs)): x for m, x in prev.items()}
        out: dict[str, dict] = {}
        for m, x in v.items():
            name = _norm(member_name(m, labs))
            p = prev.get(m) or prev_by_name.get(name) or {}
            q = {k: quarter_of(x.get(k), p.get(k)) for k in ("revenue", "operating_income")}
            out[m] = q
            out.setdefault("#" + name, q)
        return out

    now, pq, py = quarter_map(end), quarter_map(_near(end, 91)), quarter_map(_near(end, 364))
    rows: dict[str, dict] = {}
    for m, x in now.items():
        if m.startswith("#") or x.get("revenue") is None:
            continue
        name = member_name(m, labels)
        row = {"name": name, "revenue": x["revenue"], "operating_income": x.get("operating_income")}
        for suffix, src in (("_prev_q", pq), ("_prev_y", py)):
            hit = src.get(m) or src.get("#" + _norm(name)) or _fuzzy(src, _norm(name)) or {}
            for k in ("revenue", "operating_income"):
                row[k + suffix] = hit.get(k)
        # 같은 이름이 여러 표(외부매출/총매출 등)에 나오면 채워진 값이 많은 행 하나만 남긴다
        key = _norm(name)
        filled = sum(v is not None for v in row.values())
        if key not in rows or filled > sum(v is not None for v in rows[key].values()):
            rows[key] = row
    # 이름만 다른 같은 숫자 행(예: '기타'와 '기타, 영업부문')은 하나만 남긴다
    seen, out = set(), []
    for r in sorted(rows.values(), key=lambda r: (-(r["revenue"] or 0), -sum(v is not None for v in r.values()))):
        if r["revenue"] in seen:
            continue
        seen.add(r["revenue"])
        out.append(r)
    return out, "보고부문" if axes == _SEG_AXES else "제품·서비스별"


TOTALS = {"revenue": SEG_REVENUE, "operating_income": SEG_OPERATING, "net_income": ("NetIncomeLoss", "ProfitLoss")}


def build_totals(load, end: date) -> dict[str, float]:
    """전사 분기 합계(축 없는 값). 3개월 값이 없으면(10-K의 4분기) 직전 보고서 누적과의 차이."""
    cur = load(end)
    if not cur:
        return {}
    facts, _, end = cur
    prev = load(_near(end, 91))
    out = {}
    for k, concepts in TOTALS.items():
        for c in concepts:
            q = quarter_value(facts, (c,), end)
            ytd, days = ytd_value(facts, (c,), end)
            p = (None, *ytd_value(prev[0], (c,), prev[2])) if prev else None
            v = quarter_of((q, ytd, days), p) if (q is not None or ytd is not None) else None
            if v is not None:
                out[k] = v
                break
    return out
