"""공시 XBRL·KRX·옵트인 수집기 파서 테스트. 네트워크 없이 실행된다:  pytest -q"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from gaddong.analysis import reaction
from gaddong.providers import dart, fool, krx, marketbeat, xbrl

_HEAD = ('<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" '
         'xmlns:us-gaap="http://fasb.org/us-gaap" xmlns:co="http://co">')


def _ctx(cid, start, end, *members):
    dims = "".join(f'<xbrldi:explicitMember dimension="{a}">{m}</xbrldi:explicitMember>' for a, m in members)
    seg = f"<segment>{dims}</segment>" if dims else ""
    return (f'<context id="{cid}"><entity><identifier scheme="x">1</identifier>{seg}</entity>'
            f"<period><startDate>{start}</startDate><endDate>{end}</endDate></period></context>")


def _fact(concept, cid, v):
    return f'<us-gaap:{concept} contextRef="{cid}" unitRef="usd" decimals="-6">{v}</us-gaap:{concept}>'


SEG = "us-gaap:StatementBusinessSegmentsAxis"
CONS = ("srt:ConsolidationItemsAxis", "us-gaap:OperatingSegmentsMember")


def _instance(end, q_start, rows, ytd_start=None, ytd_rows=None, extra=""):
    """rows: {member: (매출, 영업이익)} 3개월 값. ytd_rows: 누적 값."""
    parts = [_HEAD]
    for i, (m, (rev, oi)) in enumerate(rows.items()):
        parts += [_ctx(f"q{i}", q_start, end, (SEG, m), CONS), _fact("Revenues", f"q{i}", rev),
                  _fact("OperatingIncomeLoss", f"q{i}", oi)]
    for i, (m, (rev, oi)) in enumerate((ytd_rows or {}).items()):
        parts += [_ctx(f"y{i}", ytd_start, end, (SEG, m), CONS), _fact("Revenues", f"y{i}", rev),
                  _fact("OperatingIncomeLoss", f"y{i}", oi)]
    return "".join(parts) + extra + "</xbrl>"


def test_xbrl_parses_dimensions_and_skips_cross_tables():
    inst = _instance("2026-07-26", "2026-04-27", {"co:ComputeMember": (88, 62)},
                     extra=_ctx("x", "2026-04-27", "2026-07-26", (SEG, "co:ComputeMember"),
                                ("srt:StatementGeographicalAxis", "co:TaiwanMember")) + _fact("Revenues", "x", 9))
    facts = xbrl.parse_instance(inst)
    assert len(facts) == 3 and facts[0].dim("StatementBusinessSegmentsAxis") == "co:ComputeMember"
    vals = xbrl.segment_values(facts, date(2026, 7, 26), xbrl._SEG_AXES)
    assert vals["co:ComputeMember"]["revenue"][0] == 88  # 지역과 교차된 9는 쓰지 않는다


def test_build_segments_us_with_prev_quarter_and_year():
    reports = {
        date(2026, 7, 26): _instance("2026-07-26", "2026-04-27", {"co:ComputeMember": (88, 62), "co:GraphicsMember": (8, 4)}),
        date(2026, 4, 26): _instance("2026-04-26", "2026-01-26", {"co:ComputeMember": (74, 53), "co:GraphicsMember": (7, 3)}),
        date(2025, 7, 27): _instance("2025-07-27", "2025-04-28", {"co:ComputeMember": (41, 28), "co:GraphicsMember": (5, 2)}),
    }

    def load(d):
        hit = next((e for e in reports if abs((e - d).days) <= 15), None)
        return (xbrl.parse_instance(reports[hit]), {"co_ComputeMember": "Compute & Networking [Member]"}, hit) if hit else None

    rows, axes = xbrl.build_segments(load, date(2026, 7, 28))
    assert axes == "보고부문" and [r["name"] for r in rows] == ["Compute & Networking", "Graphics"]
    top = rows[0]
    assert (top["revenue"], top["revenue_prev_q"], top["revenue_prev_y"]) == (88, 74, 41)
    assert top["operating_income_prev_y"] == 28


def test_build_segments_kr_ytd_only_uses_difference():
    """한국 반기보고서처럼 누적(6개월) 값만 있으면 1분기 누적을 빼서 2분기 값을 만든다."""
    h1 = _instance("2026-06-30", "2026-04-01", {}, "2026-01-01", {"co:DsMember": (209, 143)})
    q1 = _instance("2026-03-31", "2026-01-01", {}, "2026-01-01", {"co:DsMember": (82, 54)})
    reports = {date(2026, 6, 30): h1, date(2026, 3, 31): q1}

    def load(d):
        hit = next((e for e in reports if abs((e - d).days) <= 15), None)
        return (xbrl.parse_instance(reports[hit]), {}, hit) if hit else None

    rows, _ = xbrl.build_segments(load, date(2026, 6, 30))
    assert rows[0]["revenue"] == 127 and rows[0]["operating_income"] == 89 and rows[0]["revenue_prev_q"] == 82


def test_segment_names_match_across_years_despite_label_typo():
    assert xbrl._norm("DS 부문 [구성요소]") == xbrl._norm("DS부문")
    src = {"#harman": {"revenue": 3.8}}
    assert xbrl._fuzzy(src, "haman") == {"revenue": 3.8}
    assert xbrl._fuzzy(src, "dx") is None


def test_dart_da_quarter_from_ytd_and_outlier_dropped(monkeypatch):
    # 1분기 누적 100, 반기 누적 210, 3분기 누적 320, 연간 430 → 분기 100/110/110/110
    ytd = {"2025-03": 100, "2025-06": 210, "2025-09": 320, "2025-12": 430, "2026-03": 400}
    monkeypatch.setattr(dart, "corp_code", lambda _: "0")
    monkeypatch.setattr(dart, "_report_facts", lambda corp, y, code: (y, code))
    def methods(facts, end):
        p = f"{end.year}-{end.month:02d}"
        return {"dep_amort": (None, ytd[p])} if p in ytd else {}
    monkeypatch.setattr(dart, "_da_methods", methods)
    out = dart.quarterly_da("005930.KS", list(ytd))
    assert out["2025-06"] == 110 and out["2025-12"] == 110
    assert "2026-03" not in out  # 다른 분기의 4배 → 태깅 오류로 버림


def test_krx_fill_gaps_only_queries_missing_days(monkeypatch):
    idx = pd.DatetimeIndex(pd.to_datetime(["2026-10-19", "2026-10-20", "2026-10-22"])).tz_localize("Asia/Seoul")
    h = pd.DataFrame({"Open": [1.0, 1, 1], "High": [1.0, 1, 1], "Low": [1.0, 1, 1], "Close": [100.0, 101, None],
                      "Volume": [1.0, 1, 1]}, index=idx)
    asked = []

    def bar(ticker, d):
        asked.append(d)
        return {"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 102.0 if d.day == 21 else 103.0, "Volume": 1.0}

    monkeypatch.setattr(krx, "bar", bar)
    monkeypatch.setattr(krx, "datetime", type("D", (), {"now": staticmethod(lambda tz=None: pd.Timestamp("2026-10-23 09:00"))}))
    out, n = krx.fill_gaps(h, "005930.KS", date(2026, 10, 19))
    assert asked == [date(2026, 10, 21), date(2026, 10, 22)] and n == 2
    assert list(out["Close"]) == [100, 101, 102, 103]


def test_krx_isin_to_short_code():
    assert krx._short("KR7005930003") == "005930" and krx._short("005930") == "005930"


def test_reaction_skips_empty_bar_and_misaligned_benchmark():
    idx = pd.DatetimeIndex(pd.to_datetime(["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"])).tz_localize("Asia/Seoul")
    h = pd.DataFrame({"Open": [1.0] * 4, "High": [1.0] * 4, "Low": [1.0] * 4, "Close": [100, 100, 110, None],
                      "Volume": [1.0] * 4}, index=idx)
    after = pd.Timestamp("2026-10-21 16:00", tz="Asia/Seoul")  # 반응일 = 10/22, 종가 없음
    assert reaction.compute(h, after) is None
    bench = pd.DataFrame({"Close": [10.0, 10.0, 11.0]}, index=idx[[0, 1, 3]])  # 지수 10/21 누락
    r = reaction.compute(h, pd.Timestamp("2026-10-20 16:00", tz="Asia/Seoul"), bench)
    assert r["d1_pct"] == pytest.approx(10.0) and "excess_d1_pct" not in r


_MB = """<h2>Earnings History by Quarter</h2><table><tr><th>Date</th><th>Quarter</th><th>Consensus Estimate</th>
<th>Reported EPS</th><th>Beat/Miss</th><th>GAAP EPS</th><th>Revenue Estimate</th><th>Actual Revenue</th><th>Details</th></tr>
<tr><td>11/18/2026 <span>(Estimated)</span></td><td>-</td><td>$2.49</td><td>-</td><td>-</td><td>-</td><td>$108.82B</td><td>-</td><td></td></tr>
<tr><td>8/26/2026</td><td>Q2 2027</td><td>$2.09</td><td>$2.22</td><td>+$0.13</td><td>$2.46</td><td>$92.27B</td><td>$96.22B</td><td></td></tr>
<tr><td>5/28/2025</td><td>Q1 2026</td><td>$0.87</td><td>($0.06)</td><td>-$0.06</td><td>$0.76</td><td>$43.09B</td><td>$44.06B</td><td></td></tr>
</table>"""


def test_marketbeat_parse():
    rows = marketbeat.parse(_MB)
    assert len(rows) == 2
    assert rows[0] == {"date": "2026-08-26", "quarter": "Q2 2027", "eps_est": 2.09, "eps_actual": 2.22,
                       "revenue_est": 92.27e9, "revenue_actual": 96.22e9}
    assert rows[1]["eps_actual"] == -0.06


def test_fool_parse_and_find_url():
    page = ('<h2 id="full-conference-call-transcript">Full Conference Call Transcript</h2>'
            "<p><strong>Operator:</strong> Good afternoon.</p><p><strong>Jensen Huang:</strong> Thanks.</p>"
            "<p>Second paragraph &amp; more.</p><p>This article is a transcript of this conference call</p>"
            "<h2>Should you buy?</h2><p><strong>Ad:</strong> buy now</p>")
    turns = fool.parse(page)
    assert [t["speaker"] for t in turns] == ["Operator", "Jensen Huang"]
    assert turns[1]["content"] == "Thanks.\nSecond paragraph & more."
    base = "https://www.fool.com/earnings/call-transcripts/"
    links = [base + "2026/08/31/nvidia-nvda-q2-2027-earnings-call-transcript/",
             base + "2026/05/20/nvidia-nvda-q1-2027-earnings-transcript/",
             base + "2026/08/30/other-oth-q2-2027-earnings-call-transcript/"]
    assert fool.find_url(links, "NVDA", "2027Q2", None) == links[0]
    assert fool.find_url(links[1:2], "NVDA", "2027Q2", date(2026, 5, 20)) == links[1]  # 표기 없으면 날짜로
    assert fool.find_url(links[2:], "NVDA", "2027Q2", date(2026, 8, 26)) is None


def test_mascot_payload_cannot_break_out_of_script(monkeypatch):
    from gaddong.ui import mascot
    seen = {}
    monkeypatch.setattr(mascot.components, "html", lambda html, height: seen.update(html=html, height=height))
    mascot.render("happy", label="</script><img src=x onerror=alert(1)>", height=90)
    assert "</script><img" not in seen["html"] and seen["height"] == 90
    assert mascot.tone_mood({}) == "sleepy" and mascot.tone_mood({"label": "부정"}) == "sad"
    assert set(m for m, _ in mascot.VERDICT.values()) <= set(mascot.MOODS)
