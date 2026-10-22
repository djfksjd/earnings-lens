---
version: 1
slug: "app-py"
primary_target: "app.py"
related_targets: ["views"]
---

Scope: Gaddong Streamlit app shell + all views. Mode: Operate (code-led).
Audience/job: investing-study creator reviewing one ticker x one quarter right after earnings; shares screenshots.

## Direction contract

THESIS: An earnings desk where every number states its verdict against the street. Refuses the category default of a grey table dump plus a generic chatbot; instead each headline figure carries its own consensus strip, and the AI orb's colour is the call's tone.

OWN-WORLD: Cool off-white ground (#F4F5F8) with ink #12141A, glass cards (white 72% + 1px hairline + soft offset shadow), pastel tinted bento fields (periwinkle, mint, apricot, lilac) used as region grounds, periwinkle accent #4C63F0, beat green #0F8A5F, miss red #C8402F, inline amber #B7791F. Pretendard (self-hosted) with tabular numerals. Icon rail 68px, Material Symbols Rounded icons, pill controls.

STORY: Visitor picks ticker+quarter, reads the verdict row in two seconds (beat/miss on revenue, OP, EBITDA, EPS with QoQ/YoY), then scans segments, KPIs, tone shift, guidance, quotes, catalysts and price reaction; every figure is labelled auto / my input / AI.

FIRST VIEWPORT: Left icon rail (ink logo mark on top). Top bar: ticker search, quarter select, live price pill with change and delay badge. Headline verdict banner: tone orb + one-sentence verdict ("2Q26 실적, 컨센서스를 넘었습니다") + verdict chip — the two-second read. Row 1: four KPI stat cards each with value, QoQ, YoY and the consensus strip. Row 2 bento (bottoms aligned): wide column = price-reaction chart over tone card; guidance card; next catalysts card. Mobile: KPI cards 2x2, rail becomes bottom bar, Ask Gaddong collapses to an icon circle. Floating "Ask Gaddong" pill bottom-right.

FORM: Brief-pinned minimal AI SaaS dashboard, adapted. Signature move: consensus strip (estimate low-high band, consensus tick, actual dot coloured by verdict) plus tone-coloured AI orb. seed: none (brief-pinned) — the user pinned the aesthetic in the request, so per new-work §3 the roll is not run; mode-operate.md governs.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
