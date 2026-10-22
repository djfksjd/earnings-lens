# API 조사 보고서 — 무료 실적 데이터 소스 (2026-10 기준)

> 범위: 미국·한국 상장사의 분기 실적 대시보드에 필요한 데이터(실시간 가격, 분기 손익, 컨센서스, 세그먼트, 컨콜 트랜스크립트, 가이던스)를 **무료로** 얻을 수 있는 소스를 조사했다.
> 방법: 공식 문서와 엔드포인트를 2026-10-22에 직접 호출해 확인하고(✅ 실측), 공개 자료로 보완했다(📄 문서).
> 가격과 한도는 자주 바뀐다. 쓰기 전에 각 사이트의 최신 안내를 확인하자.

## 요약

| 필요한 데이터 | 채택한 무료 소스 | 확인 | 한계 |
|---|---|---|---|
| 분기 손익(미·한) | yfinance `quarterly_income_stmt` | ✅ NVDA·005930.KS 최근 5~6개 분기 | 비공식 API, 과호출 시 429 |
| 한국 공식 분기 손익 | OpenDART `fnlttSinglAcntAll` | 📄 + 키 오류 응답(010)으로 엔드포인트 확인 | 4분기는 연간에서 1~3분기를 빼서 계산해야 함 |
| EPS 컨센서스 vs 실제 | yfinance `earnings_history`, `get_earnings_dates` | ✅ 2020년부터 분기별 EPS 추정/실제 | 매출·영업이익 과거 컨센서스는 없음 |
| 과거 분기 **매출** 컨센서스(미국) | Alpha Vantage `EARNINGS_ESTIMATES` | ✅ 과거 분기 평균·상단·하단 | 무료 하루 25회 |
| 다음 분기 컨센서스 | yfinance `revenue_estimate`, `earnings_estimate` / 네이버 `finance/quarter`(E) | ✅ | 지난 분기 값은 사라짐 → **매일 스냅샷 저장**으로 해결 |
| 컨콜 트랜스크립트(미국) | Alpha Vantage `EARNINGS_CALL_TRANSCRIPT` | ✅ IBM 2024Q1 37개 발언, 발언별 sentiment | 미국 위주, 하루 25회 |
| 실적 보도자료·가이던스 원문(미국) | SEC EDGAR submissions + 8-K Item 2.02 EX-99.1/99.2 | ✅ NVDA Q2 FY27 보도자료·CFO 코멘터리 | User-Agent에 연락처 필수, 초당 10회 |
| 세그먼트·KPI | (무료 구조화 API 없음) → 보도자료/IR 텍스트를 AI로 추출 | ✅ NVDA 보도자료에서 부문 매출·KPI 추출 | AI 결과는 검토 필요 |
| 실시간 가격(미국) | yfinance(준실시간) / Finnhub 무료 키 | ✅ / 📄 | Finnhub 분당 60회 |
| 실시간 가격(한국) | 네이버 polling API(옵트인) / yfinance(지연) | ✅ `delayTime: 0` | 네이버 robots.txt가 자동 수집 금지 |
| AI 분석 | Claude Code CLI `claude -p` (구독 플랜) | ✅ `--json-schema` 구조화 출력, `--tools ""` | 플랜 사용량 |

## 1. yfinance (키 없음)

- 미국과 한국(`.KS`/`.KQ`) 모두 `fast_info`(가격), `quarterly_income_stmt`(Total Revenue, Operating Income, EBITDA, Diluted EPS), `earnings_history`(최근 4개 분기 EPS 실제/추정/서프라이즈), `get_earnings_dates`(최대 수년치 발표 일시와 EPS), `earnings_estimate`·`revenue_estimate`(0q/+1q/0y/+1y), `calendar`를 준다(✅ 2026-10-22, yfinance 1.7.0).
- Yahoo가 호출이 잦으면 `YFRateLimitError`(429)를 반환한다고 알려져 있다. 그래서 앱은 Streamlit 캐시(6~12시간)로 호출 수를 줄인다.
- 주의: `earnings_history`의 EPS는 **조정(Non-GAAP) EPS**이고, `quarterly_income_stmt`의 Diluted EPS는 **GAAP**이다. 둘을 섞어 QoQ를 계산하면 틀린다(NVDA: GAAP 2.39 vs 조정 2.22). 앱은 조정 EPS 계열만 쓰도록 맞췄다.

## 2. OpenDART (무료 키)

- `fnlttSinglAcntAll.json`: `corp_code`(8자리), `bsns_year`, `reprt_code`(11013=1분기, 11012=반기, 11014=3분기, 11011=사업보고서), `fs_div`(CFS 연결/OFS 별도).
- 손익계산서의 `thstrm_amount`는 분기 보고서에서 **3개월** 값, 사업보고서에서 **연간** 값이다. 그래서 4분기 = 연간 − (1분기+2분기+3분기)로 계산한다. 누적값은 `thstrm_add_amount`에 있다.
- 상태 코드: `000` 정상, `013` 데이터 없음, `020` 요청 제한 초과(일반적으로 하루 2만 건), `010` 미등록 키.
- `corpCode.xml`(zip)로 종목코드→고유번호 매핑을 받는다. 앱은 이를 7일 캐시한다.
- `list.json`: 공시 목록(잠정실적, IR, 분기보고서 등).

## 3. SEC EDGAR (키 없음, 연락처 필수)

- `https://www.sec.gov/files/company_tickers.json` → CIK
- `https://data.sec.gov/submissions/CIK##########.json` → `form == 8-K` 이고 `items`에 `2.02`(Results of Operations)가 든 공시
- `.../{accession}-index.htm`에서 EX-99.1(보도자료)·EX-99.2(CFO 코멘터리 등) 링크를 얻는다.
- SEC 정책: `User-Agent`에 이름·이메일, 초당 10회 이하.

## 4. Alpha Vantage (무료 키, 하루 25회)

- 무료 키는 대부분의 데이터셋을 하루 25회까지 쓸 수 있다(공식 support 페이지).
- `EARNINGS_CALL_TRANSCRIPT&symbol=&quarter=YYYYQn`: 2010Q1부터, 발언자·직함·내용·sentiment. `quarter`는 **회계분기** 기준이다. 예를 들어 NVDA의 2026년 7월 말 분기는 `2027Q2`다. 앱은 회계연도 종료월로 자동 계산한다.
- `EARNINGS_ESTIMATES`: 분기·연도별 EPS·매출 추정 평균/상단/하단/애널리스트 수와 7·30·60·90일 전 값. **과거 분기도 포함**되어 매출 서프라이즈 판정에 쓸 수 있다.
- `EARNINGS`: 분기별 reportedEPS / estimatedEPS / reportTime(pre/post-market).

## 5. 네이버 증권 (옵트인 룰베이스 수집)

- `polling.finance.naver.com/api/realtime/domestic/stock/{code}`: 실시간 가격(`delayTime: 0`), 등락률, 장 상태
- `m.stock.naver.com/api/stock/{code}/finance/quarter`: 최근 5개 분기 실적과 다음 분기 컨센서스(`isConsensus: "Y"`). 단위는 억원, EPS는 원.
- `m.stock.naver.com/api/stock/{code}/integration`: 목표주가 평균, 투자의견, 최근 리서치 제목, IR 일정
- ⚠️ `finance.naver.com/robots.txt`와 `m.stock.naver.com/robots.txt` 모두 `User-agent: * / Disallow: /`다. 그래서 기본값은 **꺼짐**이고, 사용자가 `.env`에서 켠 경우에만 동작한다.

## 6. 검토했지만 채택하지 않은 소스

| 소스 | 이유 |
|---|---|
| Financial Modeling Prep | 세그먼트·트랜스크립트가 유료 플랜(월 약 $22~$59, 연간 결제 기준). 무료는 하루 250회, EOD 위주. 데이터 표시·재배포에 별도 라이선스 필요 |
| Finnhub 트랜스크립트·추정치 | 프리미엄. 무료는 시세 중심(분당 60회) — 시세용으로만 선택 채택 |
| 한국투자증권 KIS | 무료이고 실시간이지만 계좌 개설·OAuth 토큰(앱키/시크릿) 관리가 필요해 초보자용 기본 구성에서 제외 |
| FnGuide 크롤링 | 약관상 무단 수집 제한 가능성, 구조 변경이 잦음 → 사용자가 직접 입력하는 방식으로 대체 |

## 7. 결론과 설계 결정

1. **키 없이도 동작**: yfinance만으로 실적·EPS 판정·주가 반응이 나온다.
2. **매출·영업이익 컨센서스 공백**은 ① Alpha Vantage 과거 추정치(미국 매출), ② 매일 스냅샷, ③ 사용자 입력으로 메운다.
3. **세그먼트·KPI·가이던스·톤**은 무료 구조화 API가 없다. 그래서 1차 원문(SEC 8-K, 컨콜, IR 자료)을 Claude가 구조화 JSON으로 추출하고, 사용자가 검토해 확정한다.
4. 모든 숫자에 출처를 표시한다(자동·소스명 / 내 입력 / AI 추출).

## 출처

- yfinance 레이트 리밋 이슈 — <https://github.com/ranaroussi/yfinance/issues/2480>
- yfinance 0.2.52 릴리스(YFRateLimitError 추가) — <https://newreleases.io/project/pypi/yfinance/release/0.2.52>
- OpenDART 재무제표 API 해설(2026) — <https://algolab.co.kr/blog/dart-opendart-financial-statement-api-lag-2026>
- OpenDART 소개 — <https://wikidocs.net/336171>
- SEC EDGAR 접근 정책 — <https://www.sec.gov/os/accessing-edgar-data>
- Alpha Vantage 문서 — <https://www.alphavantage.co/documentation/>
- Alpha Vantage 무료 한도 — <https://www.alphavantage.co/support/>
- FMP 가격 비교(2026-08 검증) — <https://multiples.vc/compare/fmp-api-alternatives>
- FMP 가격 정책 문서 — <https://site.financialmodelingprep.com/developer/docs/pricing/jesse>
- Finnhub 무료 티어 리뷰 — <https://orthogonal.info/i-tested-4-free-stock-market-apis-heres-which-one-actually-works-for-side-projects/>
- KIS Developers 설정 가이드(2026) — <https://algolab.co.kr/blog/kis-open-trading-api-github-sample-setup-2026>
- Claude Code 설치 문서 — <https://code.claude.com/docs/en/setup>
- Tailscale serve — <https://tailscale.com/kb/1242/tailscale-serve>
- Tailscale funnel — <https://tailscale.com/kb/1311/tailscale-funnel>
- Antigravity 설치 가이드 — <https://www.secondtalent.com/resources/how-to-download-and-install-googles-antigravity-ide/>
