"""핵심 계산·보안 규칙 테스트. 네트워크 없이 실행된다:  pytest -q"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd
import pytest

from earnings_lens import ai, config, manual, security
from earnings_lens.analysis import metrics, reaction
from earnings_lens.providers import alphavantage, dart, sec
from earnings_lens.ui import components, fmt

ROOT = Path(__file__).resolve().parent.parent


# ---------- 보안 ----------

@pytest.mark.parametrize("raw,want", [("nvda", "NVDA"), ("005930", "005930.KS"), ("brk-b", "BRK-B"), ("035720.kq", "035720.KQ")])
def test_clean_ticker_ok(raw, want):
    assert security.clean_ticker(raw) == want


@pytest.mark.parametrize("raw", ["../etc", "A/B", "", "NVDA;rm", "a" * 20, "<script>"])
def test_clean_ticker_rejects(raw):
    with pytest.raises(ValueError):
        security.clean_ticker(raw)


def test_paths_cannot_escape_my_inputs():
    with pytest.raises(ValueError):
        manual.input_path("NVDA", "../../x")
    p = manual.input_path("005930.KS", "2026-06")
    assert p.resolve().is_relative_to(config.MY_INPUTS.resolve())


def test_redact_hides_keys(monkeypatch):
    monkeypatch.setenv("DART_API_KEY", "supersecretvalue123")
    msg = "HTTPError for https://x.com/api?crtfc_key=supersecretvalue123&apikey=abc123 supersecretvalue123"
    out = security.redact(msg)
    assert "supersecretvalue123" not in out and "abc123" not in out


def test_mask_never_reveals():
    assert security.mask("abcdefghijk") == "등록됨" and security.mask("") == "미등록"


def test_html_is_escaped_in_cards():
    html = components.card("<img src=x onerror=alert(1)>", "", source="<b>")
    assert "<img" not in html and "&lt;img" in html


def test_ai_subprocess_env_has_no_keys(monkeypatch):
    monkeypatch.setenv("DART_API_KEY", "k1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k2")
    env = ai._env()
    assert "DART_API_KEY" not in env and "ANTHROPIC_API_KEY" not in env


def test_sec_only_fetches_sec_urls():
    with pytest.raises(Exception):
        sec.exhibit_text("https://evil.example.com/a.htm")


def test_env_file_is_gitignored():
    if not (ROOT / ".git").exists():
        pytest.skip("git 저장소 아님")
    for path in (".env", "my_inputs/watchlist.yaml", "data/cache/x.json"):
        r = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT)
        assert r.returncode == 0, f"{path} 가 .gitignore에 없음"


def test_streamlit_binds_localhost_only():
    cfg = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'address = "127.0.0.1"' in cfg and "port = 8765" in cfg


# ---------- 계산 ----------

def test_prev_period():
    assert metrics.prev_period("2026-06", 3) == "2026-03"
    assert metrics.prev_period("2026-01", 3) == "2025-10"
    assert metrics.prev_period("2026-06", 12) == "2025-06"
    assert metrics.prev_period("2026-10", -3) == "2027-01"


def test_pct_change_negative_base():
    assert metrics.pct_change(-50, -100) == pytest.approx(50.0)  # 적자 축소 = 개선
    assert metrics.pct_change(10, 0) is None


@pytest.mark.parametrize("actual,est,code", [(112, 100, "big_beat"), (105, 100, "beat"), (101, 100, "inline"),
                                             (96, 100, "miss"), (85, 100, "big_miss"), (1, None, "na")])
def test_verdict(actual, est, code):
    assert metrics.verdict(actual, est).code == code


def test_change_table_qoq_yoy():
    df = pd.DataFrame({"revenue": [100, 110, 120, 130, 150]}, index=["2025-06", "2025-09", "2025-12", "2026-03", "2026-06"])
    t = metrics.change_table(df, "2026-06")
    assert t.at["revenue", "qoq"] == pytest.approx(150 / 130 * 100 - 100)
    assert t.at["revenue", "yoy"] == pytest.approx(50.0)


@pytest.mark.parametrize("period,fy,want", [("2026-07", 1, "2027Q2"), ("2026-06", 9, "2026Q3"), ("2026-06", 12, "2026Q2"),
                                            ("2026-12", 12, "2026Q4"), ("2026-10", 1, "2027Q3")])
def test_fiscal_quarter(period, fy, want):
    assert alphavantage.fiscal_quarter(period, fy) == want


@pytest.mark.parametrize("raw,want", [("41.1B", 41.1e9), ("1.2조", 1.2e12), ("3,500억", 3.5e11), ("1조 2,000억", 1.2e12),
                                      (2100, 2100.0), ("$2.5M", 2.5e6), ("abc", None), ("", None)])
def test_parse_amount(raw, want):
    got = manual.parse_amount(raw)
    assert got == pytest.approx(want) if want is not None else got is None


def test_validate_yaml_rejects_unknown_and_objects():
    with pytest.raises(ValueError):
        manual.validate_yaml_text("hacker: 1")
    with pytest.raises(Exception):
        manual.validate_yaml_text("!!python/object/apply:os.system ['echo hi']")
    assert manual.validate_yaml_text("segments: []")["segments"] == []


def test_example_input_is_valid():
    text = (config.EXAMPLES / "companies" / "EXAMPLE" / "2026-06.yaml").read_text(encoding="utf-8")
    data = manual.validate_yaml_text(text)
    assert data["segments"] and data["guidance"]


def test_reaction_after_close_uses_next_session():
    idx = pd.DatetimeIndex(pd.to_datetime(["2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28"])).tz_localize("America/New_York")
    h = pd.DataFrame({"Open": [10, 10, 10, 11, 12], "High": [10, 10, 10, 12, 12], "Low": [10, 10, 10, 10, 11],
                      "Close": [10, 10, 10, 11, 12], "Volume": [1, 1, 1, 3, 1]}, index=idx)
    ev = pd.Timestamp("2026-08-26 16:05", tz="America/New_York")
    r = reaction.compute(h, ev)
    assert r["reaction_date"] == "2026-08-27" and r["d1_pct"] == pytest.approx(10.0) and r["gap_pct"] == pytest.approx(10.0)
    ev_pre = pd.Timestamp("2026-08-26 07:00", tz="America/New_York")
    assert reaction.compute(h, ev_pre)["reaction_date"] == "2026-08-26"


def test_dart_q4_is_annual_minus_three_quarters(monkeypatch):
    def rows(v):
        return [{"sj_div": "IS", "account_id": "ifrs-full_Revenue", "thstrm_amount": str(v)}]
    data = {"11013": rows(10), "11012": rows(20), "11014": rows(30), "11011": rows(100)}
    monkeypatch.setattr(dart, "corp_code", lambda _: "00000000")
    monkeypatch.setattr(dart, "_report", lambda corp, year, code: data[code] if year == 2025 else [])
    df = dart.quarterly_financials("005930.KS", years=2)
    assert df.at["2025-12", "revenue"] == 40 and df.at["2025-06", "revenue"] == 20


def test_money_format():
    assert fmt.money(96.22e9, "USD") == "$96.22B"
    assert fmt.money(1.715e14, "KRW") == "171.50조"
    assert fmt.money(-3.2e10, "KRW") == "−320억"
    assert fmt.pct(None) == "—"


def test_components_avoid_svg_which_streamlit_sanitizer_strips():
    v = metrics.verdict(105, 100)
    html = components.consensus_strip(105, 100, 95, 110, v, str) + components.orb(0.5)
    assert "<svg" not in html and 'class="dot"' in html and 'class="band"' in html


def test_segment_total_row_detected():
    from earnings_lens.manual import is_total_row
    assert is_total_row("전사 합계(GAAP)") and is_total_row("Total") and is_total_row("총계")
    assert not is_total_row("Data Center") and not is_total_row("메모리") and not is_total_row(None)


def test_combined_ai_keeps_both_guidance_lists(tmp_path, monkeypatch):
    from earnings_lens import config, manual
    monkeypatch.setattr(config, "AI_DIR", tmp_path)
    manual.save_ai("005930.KS", "2026-06", "call", {"guidance": [{"metric": "call"}], "tone": {"label": "긍정"}})
    manual.save_ai("005930.KS", "2026-06", "release", {"guidance": [{"metric": "release"}], "segments": [{"name": "DS"}]})
    ai = manual.combined_ai("005930.KS", "2026-06")
    assert [g["metric"] for g in ai["guidance"]] == ["release", "call"]
    assert ai["tone"]["label"] == "긍정" and ai["segments"][0]["name"] == "DS"


def test_money_unit_uses_korean_units_for_krw():
    from earnings_lens.ui.components import money_unit
    assert money_unit([1.7e14, None], "KRW") == (1e12, "조")
    assert money_unit([3e11], "KRW") == (1e8, "억")
    assert money_unit([9.6e10], "USD") == (1e9, "B")
    assert money_unit([], "USD") == (1e6, "M")


def test_readable_amounts_round_trip():
    from earnings_lens.manual import parse_amount, readable_amounts
    from earnings_lens.ui import fmt
    out = readable_amounts({"segments": [{"name": "DS", "revenue": 95e12, "note": "x"}], "kpis": [{"value": 40}]},
                           lambda v: fmt.money(v, "KRW"))
    assert out["segments"][0]["revenue"] == "95.00조" and parse_amount(out["segments"][0]["revenue"]) == 95e12
    assert out["kpis"][0]["value"] == 40  # KPI는 단위가 제각각이라 건드리지 않는다
