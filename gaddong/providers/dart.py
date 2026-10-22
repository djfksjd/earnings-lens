"""OpenDART: 한국 공식 공시 재무제표와 공시 목록. 무료 키 필요(DART_API_KEY)."""
from __future__ import annotations

import io
import json
import re
import time
import zipfile
from datetime import date, timedelta
from xml.etree import ElementTree

import pandas as pd

from .. import config
from . import xbrl
from .http import ProviderError, get

BASE = "https://opendart.fss.or.kr/api"
# 보고서 코드 → 분기말 월
REPORTS = {"11013": 3, "11012": 6, "11014": 9, "11011": 12}

_ACCOUNTS = {
    "revenue": {"ifrs-full_Revenue", "ifrs_Revenue"},
    "operating_income": {"dart_OperatingIncomeLoss", "ifrs-full_OperatingIncomeLoss"},
    "net_income": {"ifrs-full_ProfitLossAttributableToOwnersOfParent", "ifrs-full_ProfitLoss", "ifrs_ProfitLoss"},
    "eps": {"ifrs-full_DilutedEarningsLossPerShare", "ifrs-full_BasicEarningsLossPerShare",
            "ifrs_BasicEarningsLossPerShare"},
}
_NAMES = {
    "revenue": ("매출액", "수익(매출액)", "영업수익", "매출"),
    "operating_income": ("영업이익", "영업이익(손실)"),
    "net_income": ("지배기업 소유주지분", "지배기업의 소유주에게 귀속되는 당기순이익", "당기순이익", "당기순이익(손실)"),
    "eps": ("희석주당이익", "기본주당이익", "기본주당이익(손실)", "기본및희석주당이익"),
}


def _key() -> str:
    k = config.secret("DART_API_KEY")
    if not k:
        raise ProviderError("DART_API_KEY가 .env에 없습니다.")
    return k


def _call(path: str, **params) -> dict:
    r = get(f"{BASE}/{path}", params={"crtfc_key": _key(), **params})
    data = r.json()
    status = data.get("status")
    if status == "013":  # 데이터 없음
        return {"list": []}
    if status != "000":
        raise ProviderError(f"DART 응답 {status}: {data.get('message', '')}")
    return data


def _cache_path(name: str):
    return config.CACHE_DIR / "dart" / name


def corp_code(stock_code: str) -> str:
    """6자리 종목코드 → 8자리 DART 고유번호. 전체 목록을 받아 7일 캐시."""
    path = _cache_path("corp_codes.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or time.time() - path.stat().st_mtime > 7 * 86400:
        r = get(f"{BASE}/corpCode.xml", params={"crtfc_key": _key()}, timeout=60)
        if r.content[:2] != b"PK":
            raise ProviderError("DART 고유번호 파일을 받지 못했습니다. 키를 확인하세요.")
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            root = ElementTree.fromstring(z.read(z.namelist()[0]))
        mapping = {}
        for el in root.iter("list"):
            sc = (el.findtext("stock_code") or "").strip()
            if sc:
                mapping[sc] = el.findtext("corp_code")
        path.write_text(json.dumps(mapping), encoding="utf-8")
    mapping = json.loads(path.read_text(encoding="utf-8"))
    code = mapping.get(stock_code)
    if not code:
        raise ProviderError(f"DART에서 종목코드 {stock_code}를 찾지 못했습니다.")
    return code


def _pick(rows: list[dict], metric: str, field: str):
    ids, names = _ACCOUNTS[metric], _NAMES[metric]
    cands = [r for r in rows if r.get("sj_div") in ("IS", "CIS")]
    for r in cands:
        if r.get("account_id") in ids:
            v = _amount(r.get(field))
            if v is not None:
                return v
    for n in names:
        for r in cands:
            if (r.get("account_nm") or "").replace(" ", "") == n.replace(" ", ""):
                v = _amount(r.get(field))
                if v is not None:
                    return v
    return None


def _amount(v):
    if v in (None, "", "-"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _report(corp: str, year: int, code: str) -> list[dict]:
    path = _cache_path(f"{corp}_{year}_{code}.json")
    fresh = year < date.today().year - 1  # 2년 전 보고서는 확정으로 보고 영구 캐시
    if path.exists() and (fresh or time.time() - path.stat().st_mtime < 86400):
        return json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for fs in ("CFS", "OFS"):  # 연결 우선, 없으면 별도
        rows = _call("fnlttSinglAcntAll.json", corp_code=corp, bsns_year=str(year), reprt_code=code, fs_div=fs).get("list", [])
        if rows:
            break
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def quarterly_financials(ticker: str, years: int = 3) -> pd.DataFrame:
    """분기(3개월) 매출·영업이익·순이익·EPS. 4분기는 연간 − (1~3분기)로 계산한다."""
    corp = corp_code(ticker.split(".")[0])
    this_year = date.today().year
    out: dict[str, dict] = {}
    for year in range(this_year - years + 1, this_year + 1):
        per_q: dict[int, dict] = {}
        for code, month in REPORTS.items():
            rows = _report(corp, year, code)
            if not rows:
                continue
            per_q[month] = {m: _pick(rows, m, "thstrm_amount") for m in _ACCOUNTS}
        if 12 in per_q and all(m in per_q for m in (3, 6, 9)):
            annual = per_q[12]
            per_q[12] = {m: (annual[m] - sum(per_q[q][m] for q in (3, 6, 9))
                             if annual[m] is not None and all(per_q[q][m] is not None for q in (3, 6, 9)) else None)
                         for m in _ACCOUNTS}
        elif 12 in per_q:
            per_q.pop(12)  # 분기 값을 만들 수 없으면 버린다
        for month, vals in per_q.items():
            out[f"{year}-{month:02d}"] = vals
    return pd.DataFrame.from_dict(out, orient="index").sort_index()


# ---------- XBRL 원본(주석 포함): 감가상각비 → EBITDA ----------
# 단일회사 재무제표 API(fnlttSinglAcntAll)는 본문만 준다. 대형사는 감가상각비를 주석에만 적어서
# 정기보고서 XBRL 원본(fnlttXbrl.xml)을 받아 읽는다. 보고서 1건 약 0.5MB, 받은 뒤 영구 캐시.

_REPORT_NAME = {"11013": "분기보고서", "11012": "반기보고서", "11014": "분기보고서", "11011": "사업보고서"}
# 합계 개념이 있으면 그것만, 없으면 감가상각 + 무형자산상각을 더한다. 마지막은 현금흐름표 본문의 조정 항목.
_DA_TOTAL = ("DepreciationAndAmortisationExpense", "DepreciationAmortisationAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss")
_DEP = ("DepreciationExpense", "DepreciationPropertyPlantAndEquipmentIncludingRightofuseAssets")
_DEP_PARTS = ("DepreciationPropertyPlantAndEquipment", "DepreciationRightofuseAssets")
_AMORT = ("AmortisationExpense", "AmortisationIntangibleAssetsOtherThanGoodwill")
_CF_DA = ("AdjustmentsForDepreciationAndAmortisationExpense",)
_CF_PARTS = ("AdjustmentsForDepreciationExpense", "AdjustmentsForAmortisationExpense")
_CONSOLIDATED = (("ifrs-full:ConsolidatedAndSeparateFinancialStatementsAxis", "ifrs-full:ConsolidatedMember"),)
_SEPARATE = (("ifrs-full:ConsolidatedAndSeparateFinancialStatementsAxis", "ifrs-full:SeparateMember"),)


def _rcept_no(corp: str, year: int, code: str) -> str | None:
    """정기보고서 접수번호. 정정 보고서가 있으면 최신 것."""
    month = REPORTS[code]
    data = _call("list.json", corp_code=corp, bgn_de=f"{year}0101", end_de=f"{year + 1}1231",
                 pblntf_ty="A", page_count="100")
    tag = f"({year}.{month:02d})"
    for d in data.get("list", []):  # 최신순
        name = d.get("report_nm", "")
        if _REPORT_NAME[code] in name and tag in name:
            return d.get("rcept_no")
    return None


def _xbrl_files(corp: str, year: int, code: str) -> tuple[bytes, bytes] | None:
    """(인스턴스, 한국어 레이블). 없으면 None. 공시는 바뀌지 않으므로 영구 캐시."""
    folder = _cache_path(f"xbrl/{corp}_{year}_{code}")
    inst, lab, miss = folder / "instance.xbrl", folder / "lab-ko.xml", folder / "missing"
    if inst.exists():
        return inst.read_bytes(), lab.read_bytes() if lab.exists() else b""
    if miss.exists() and time.time() - miss.stat().st_mtime < 86400:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    rno = _rcept_no(corp, year, code)
    r = get(f"{BASE}/fnlttXbrl.xml", params={"crtfc_key": _key(), "rcept_no": rno, "reprt_code": code},
            timeout=60) if rno else None
    if r is None or r.content[:2] != b"PK":
        miss.touch()  # 아직 제출 전이거나 XBRL이 없는 보고서. 하루 뒤 다시 본다
        return None
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        names = z.namelist()
        inst_name = next((n for n in names if n.endswith(".xbrl")), None)
        lab_name = next((n for n in names if n.endswith("_lab-ko.xml")), None)
        if not inst_name:
            miss.touch()
            return None
        inst.write_bytes(z.read(inst_name))
        if lab_name:
            lab.write_bytes(z.read(lab_name))
    return inst.read_bytes(), lab.read_bytes() if lab.exists() else b""


def _report_facts(corp: str, year: int, code: str) -> list:
    files = _xbrl_files(corp, year, code)
    if not files:
        return []
    try:
        facts = xbrl.parse_instance(files[0])
    except ElementTree.ParseError:
        return []
    # 주석 표의 '보고금액' 축은 본문 값과 같은 숫자다. 축을 떼어 본문과 같은 조건으로 찾게 한다.
    return [xbrl.Fact(f.concept, tuple(d for d in f.dims if d[1] != "dart:ReportedAmountMember"), f.start, f.end, f.value)
            for f in facts]


def _da_methods(facts: list, end) -> dict[str, tuple[float | None, float | None]]:
    """계산 방법별 (3개월 값, 연초 누적 값). 연결 → 축 없음 → 개별 중 값이 있는 첫 범위만 쓴다.
    분기 차이를 낼 때 두 보고서가 같은 방법을 써야 하므로 방법별로 따로 돌려준다."""
    def pair(concepts, dims):
        return xbrl.quarter_value(facts, concepts, end, dims=dims), xbrl.ytd_value(facts, concepts, end, dims=dims)[0]

    def add(*vals):
        return None if vals[0] is None else sum(v for v in vals if v is not None)

    for dims in (_CONSOLIDATED, (), _SEPARATE):
        out: dict[str, tuple] = {}
        out["total"] = pair(_DA_TOTAL, dims)
        dep, amort = pair(_DEP, dims), pair(_AMORT, dims)
        out["dep_amort"] = (add(dep[0], amort[0]), add(dep[1], amort[1]))
        ppe, rou = pair(_DEP_PARTS[:1], dims), pair(_DEP_PARTS[1:], dims)
        out["parts"] = (add(ppe[0], rou[0], amort[0]), add(ppe[1], rou[1], amort[1]))
        out["cf_total"] = pair(_CF_DA, dims)
        cdep, camort = pair(_CF_PARTS[:1], dims), pair(_CF_PARTS[1:], dims)
        out["cf_parts"] = (add(cdep[0], camort[0]), add(cdep[1], camort[1]))
        out = {k: v for k, v in out.items() if v[0] is not None or v[1] is not None}
        if out:
            return out
    return {}


def quarterly_da(ticker: str, periods: list[str]) -> dict[str, float]:
    """분기(3개월) 감가상각비+무형자산상각비.

    3개월 값이 공시돼 있으면 그대로, 없으면(4분기 등) 같은 계산 방법의 누적값 차이로 구한다.
    감가상각비는 분기마다 크게 변하지 않는다. 중앙값과 2배 넘게 차이 나면 태깅 오류로 보고 버린다.
    """
    corp = corp_code(ticker.split(".")[0])
    cache: dict[str, dict] = {}

    def methods(p: str) -> dict:
        if p not in cache:
            y, m = int(p[:4]), int(p[5:7])
            code = next((c for c, mm in REPORTS.items() if mm == m), None)
            end = (pd.Timestamp(p + "-01") + pd.offsets.MonthEnd(0)).date()
            cache[p] = _da_methods(_report_facts(corp, y, code), end) if code else {}
        return cache[p]

    out: dict[str, float] = {}
    for p in periods:
        cur = methods(p)
        prev = methods(f"{p[:4]}-{int(p[5:7]) - 3:02d}") if p[5:7] != "03" else {}
        for name in ("total", "dep_amort", "parts", "cf_total", "cf_parts"):
            q, ytd = cur.get(name, (None, None))
            if q is None and ytd is not None:
                if p[5:7] == "03":
                    q = ytd
                elif (prev.get(name, (None, None))[1] or 0) > 0 and ytd > prev[name][1]:
                    q = ytd - prev[name][1]
            if q is not None and q > 0:
                out[p] = q
                break
    if len(out) >= 3:
        med = float(pd.Series(list(out.values())).median())
        out = {p: v for p, v in out.items() if med / 2 <= v <= med * 2}
    return out


def segments(ticker: str, period: str) -> tuple[list[dict], str]:
    """분기 사업부문 매출·영업이익(전분기·전년동기 포함). 대부분 누적값만 공시해 누적 차이로 계산한다."""
    corp = corp_code(ticker.split(".")[0])
    loaded: dict[tuple, tuple | None] = {}

    def load(d: date):
        ts = pd.Timestamp(d)
        for cand in (ts + pd.offsets.MonthEnd(0), ts - pd.offsets.MonthEnd(1)):
            code = next((c for c, mm in REPORTS.items() if mm == cand.month), None)
            if code and abs((cand - ts).days) <= 15:
                key = (cand.year, code)
                if key not in loaded:
                    files = _xbrl_files(corp, cand.year, code)
                    facts = _report_facts(corp, cand.year, code) if files else []
                    loaded[key] = (facts, xbrl.parse_labels(files[1], "ko") if files and files[1] else {},
                                   cand.date()) if facts else None
                return loaded[key]
        return None

    end = (pd.Timestamp(period + "-01") + pd.offsets.MonthEnd(0)).date()
    rows, axes = xbrl.build_segments(load, end)
    for r in rows:  # 한국어 레이블 끝의 '[구성요소]' 같은 표식 제거
        r["name"] = re.sub(r"\s*\[[^\]]*\]\s*$", "", r["name"]).strip()
    return rows, axes


def disclosures(ticker: str, days: int = 120) -> list[dict]:
    """실적·IR 관련 최근 공시."""
    corp = corp_code(ticker.split(".")[0])
    end = date.today()
    data = _call("list.json", corp_code=corp, bgn_de=(end - timedelta(days=days)).strftime("%Y%m%d"),
                 end_de=end.strftime("%Y%m%d"), page_count="100")
    keep = ("잠정", "실적", "기업설명회", "IR", "분기보고서", "반기보고서", "사업보고서", "배당")
    out = []
    for d in data.get("list", []):
        name = d.get("report_nm", "")
        if any(k in name for k in keep):
            out.append({"date": d.get("rcept_dt", ""), "title": name.strip(),
                        "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={d.get('rcept_no', '')}"})
    return out
