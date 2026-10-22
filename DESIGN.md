---
name: Earnings Lens
description: An earnings desk where every headline number states its verdict against the street.
colors:
  desk-ground: "#F3F4F8"
  glass-surface: "rgba(255, 255, 255, .80)"
  solid-surface: "#FFFFFF"
  ink: "#12141A"
  ink-secondary: "#474C59"
  ink-tertiary: "#646a79"
  hairline: "rgba(18, 20, 26, .08)"
  hairline-strong: "rgba(18, 20, 26, .14)"
  periwinkle: "#4C63F0"
  periwinkle-ink: "#3346C9"
  periwinkle-soft: "#E7EAFE"
  beat: "#0E8058"
  beat-soft: "#E2F3EB"
  miss: "#C23E2C"
  miss-soft: "#FBE8E4"
  inline: "#8C5F0E"
  inline-soft: "#F7EEDA"
  tint-peri: "#EDEFFF"
  tint-mint: "#E7F5EF"
  tint-apricot: "#FFF0E4"
  tint-lilac: "#F2EDFB"
  tint-rose: "#FCECEA"
  ai-violet: "#5B3FA6"
typography:
  headline:
    fontFamily: "Pretendard, system-ui, -apple-system, sans-serif"
    fontSize: "1.6rem"
    fontWeight: 750
    letterSpacing: "-0.02em"
  verdict:
    fontFamily: "Pretendard, system-ui, -apple-system, sans-serif"
    fontSize: "1.35rem"
    fontWeight: 750
    letterSpacing: "-0.02em"
  figure:
    fontFamily: "Pretendard, system-ui, -apple-system, sans-serif"
    fontSize: "clamp(1.6rem, 2.2vw, 2.1rem)"
    fontWeight: 750
    lineHeight: 1.05
    letterSpacing: "-0.03em"
    fontFeature: "tnum"
  title:
    fontFamily: "Pretendard, system-ui, -apple-system, sans-serif"
    fontSize: ".95rem"
    fontWeight: 650
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Pretendard, system-ui, -apple-system, sans-serif"
    fontSize: ".9rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Pretendard, system-ui, -apple-system, sans-serif"
    fontSize: ".86rem"
    fontWeight: 600
  caption:
    fontFamily: "Pretendard, system-ui, -apple-system, sans-serif"
    fontSize: ".8rem"
    fontWeight: 400
  chip:
    fontFamily: "Pretendard, system-ui, -apple-system, sans-serif"
    fontSize: ".74rem"
    fontWeight: 700
    fontFeature: "tnum"
rounded:
  pill: "999px"
  rail: "22px"
  card: "20px"
  bar: "18px"
  nav: "14px"
  sm: "12px"
  tab: "10px"
spacing:
  xs: "6px"
  sm: "10px"
  md: "14px"
  lg: "18px"
  card-x: "20px"
  gutter: "2.25rem"
components:
  card:
    backgroundColor: "{colors.glass-surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "18px 20px"
  stat-card-beat:
    backgroundColor: "{colors.tint-mint}"
    rounded: "{rounded.card}"
    padding: "18px 20px"
  stat-card-inline:
    backgroundColor: "{colors.tint-apricot}"
    rounded: "{rounded.card}"
    padding: "18px 20px"
  stat-card-miss:
    backgroundColor: "{colors.tint-rose}"
    rounded: "{rounded.card}"
    padding: "18px 20px"
  verdict-chip-beat:
    backgroundColor: "{colors.beat-soft}"
    textColor: "{colors.beat}"
    typography: "{typography.chip}"
    rounded: "{rounded.pill}"
    padding: "4px 9px"
  verdict-chip-miss:
    backgroundColor: "{colors.miss-soft}"
    textColor: "{colors.miss}"
    typography: "{typography.chip}"
    rounded: "{rounded.pill}"
    padding: "4px 9px"
  verdict-chip-inline:
    backgroundColor: "{colors.inline-soft}"
    textColor: "{colors.inline}"
    typography: "{typography.chip}"
    rounded: "{rounded.pill}"
    padding: "4px 9px"
  source-badge-mine:
    backgroundColor: "{colors.periwinkle-soft}"
    textColor: "{colors.periwinkle-ink}"
    rounded: "{rounded.pill}"
    padding: "3px 8px"
  source-badge-ai:
    backgroundColor: "{colors.tint-lilac}"
    textColor: "{colors.ai-violet}"
    rounded: "{rounded.pill}"
    padding: "3px 8px"
  price-pill:
    backgroundColor: "{colors.solid-surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "8px 14px"
  nav-item:
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.nav}"
    size: "44px"
  nav-item-hover:
    backgroundColor: "{colors.periwinkle-soft}"
  nav-item-active:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.solid-surface}"
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.solid-surface}"
    rounded: "{rounded.sm}"
  copilot-pill:
    backgroundColor: "rgba(18, 20, 26, .9)"
    textColor: "{colors.solid-surface}"
    rounded: "{rounded.pill}"
    padding: "10px 18px 10px 14px"
    height: "48px"
---

# Design System: Earnings Lens

## Overview

**Creative North Star: "The Verdict Desk"**

A soft, cool off-white desk lit by three faint colour pools (periwinkle top-right, mint bottom-left, apricot bottom-centre). Frosted glass cards float on it, each holding one figure and that figure's verdict against consensus. Colour is semantic before it is decorative: green, amber and red mean beat, inline and miss; periwinkle means interaction and "my input"; lilac means AI. Density is dashboard-medium: one ticker, one quarter, read in two seconds, then scanned.

The system lives inside Streamlit. Every custom graphic is HTML/CSS spans positioned with inline `left`/`width` percentages, because the `st.html` sanitizer strips `<svg>`. Layout is Streamlit columns and keyed containers (`st.container(key=...)` becomes `.st-key-*`) restyled from one stylesheet whose tokens live only in `:root`.

**Key Characteristics:**
- Glass cards with hairline borders and a soft, low, two-layer shadow; lift on hover.
- Verdict colour drives the card tint, chip, strip gap and dot together.
- Tabular numerals on every figure, table, chip and legend.
- Pill-shaped small controls; generous 20px card corners.
- One signature pair: the consensus strip and the tone-coloured AI orb.
- Korean text never breaks mid-word (`word-break: keep-all`).

## Colors

A cool neutral desk with one periwinkle accent and a strict three-state verdict scale, each with a soft companion for grounds.

### Primary
- **Periwinkle** (`periwinkle`): focus ring, selection tint, chart primary series, price-chart line and 7% area fill, consensus band at 18% alpha, Streamlit `primaryColor`.
- **Periwinkle Ink** (`periwinkle-ink`): links and text on periwinkle-soft (my-input badge, accent pill).
- **Periwinkle Soft** (`periwinkle-soft`): rail hover, user chat bubble, my-input badge ground.

### Secondary (verdict scale)
- **Beat Green** (`beat` / `beat-soft`): beat and big beat, positive deltas, live price dot.
- **Inline Amber** (`inline` / `inline-soft`): in-line verdict, delayed quote dot, "example data" badge.
- **Miss Red** (`miss` / `miss-soft`): miss and big miss, negative deltas.

### Tertiary (region tints)
- **Periwinkle, Mint, Apricot, Lilac, Rose tints** (`tint-*`): card grounds only, applied as `linear-gradient(160deg, tint, rgba(255,255,255,.78) 40%)` so the tint pools in the top-left corner and fades into glass. Lilac is the AI field (tone cards, AI badge with `ai-violet` text).

### Neutral
- **Desk Ground** (`desk-ground`): app background beneath the radial colour pools.
- **Glass Surface** (`glass-surface`) over a `blur(16-18px) saturate(1.3-1.4)` backdrop: cards, rail, top bar.
- **Solid Surface** (`solid-surface`): price pill, select fields, expanders, popover.
- **Ink / Ink Secondary / Ink Tertiary**: headings and figures / body and labels / captions, axis ticks, legends.
- **Hairline / Hairline Strong**: card borders and row rules / table header rule, select borders, rail separator.

Chart series run, in order: `#4C63F0`, `#3FB58A`, `#F29A5B`, `#9A7BE0`, `#5CB8E6`, `#E46F8C`, `#B9A23A`.

### Named Rules
**The Verdict Owns Colour Rule.** Green, amber and red appear only to state beat, inline or miss (or up/down/live). Never use them decoratively. When no consensus exists, the card stays untinted and the chip is omitted.

**The Three Sources Rule.** Every figure carries a source badge: neutral grey for auto, periwinkle for my input, lilac/violet for AI, amber for example data.

## Typography

**Display Font:** Pretendard Variable, self-hosted (`static/fonts/PretendardVariable.woff2`, weights 45-920), with system-ui fallback
**Body Font:** Pretendard
**Label/Mono Font:** `ui-monospace, "SF Mono", Menlo` only in transcript text areas (.84rem)

**Character:** One variable sans across the whole UI, using in-between weights (650, 750) to separate tiers without size jumps. Headings tighten to -0.02em; big figures to -0.03em.

### Hierarchy
- **Headline** (750, 1.6rem): page titles, with a 0.9rem ink-tertiary subline.
- **Verdict** (750, 1.35rem; 1.08rem mobile): the one-sentence verdict in the headline banner.
- **Figure** (750, clamp(1.6rem, 2.2vw, 2.1rem), lh 1.05, tnum; 1.35rem mobile): KPI values.
- **Title** (650, .95rem): card headings. Company name in the top bar is 700 at 1.12rem.
- **Body** (400, .9rem, lh 1.55): lists, quotes (.92rem), chat, empty states.
- **Label** (600, .86rem, ink-secondary): metric name on stat cards. Table headers are 600 at .76rem ink-tertiary.
- **Caption** (400, .8rem, ink-tertiary): card sublines, legends (.72rem).
- **Chip** (700, .74rem): verdict chips; pills .70rem/700; source badges .68rem/600.

### Named Rules
**The Tabular Rule.** Every number is set with `font-variant-numeric: tabular-nums`. Tables right-align numbers and left-align the first column.

**The Keep-All Rule.** `word-break: keep-all; overflow-wrap: anywhere` on the document; headings also `text-wrap: balance`.

## Layout

A fixed left icon rail (72px including its 12px inset) and a content column capped at 1680px plus rail, padded `1.25rem 2.25rem 7rem` with rail clearance on the left. A sticky glass top bar (company title, ticker select, quarter select, price pill in a 2.6 : 1.6 : 1.2 : 2.2 split) sits 10px from the top, 18px above content.

Pages compose as bento rows of Streamlit columns: headline banner, then a row of four stat cards, then a 2 : 1 : 1 bento. Cards in a bento row stretch so bottoms align. Card internal rhythm is 6 / 10 / 12 / 14 / 18px.

Mobile (max-width 760px): the rail becomes a 60px bottom bar inset 10px with logo and separator hidden; content padding drops to 1rem (9rem bottom); stat cards wrap 2x2 with deltas stacked and source badges hidden; the headline banner keeps the orb at 48px and drops its subline; the top bar wraps with selects at 50% each; card padding becomes 14px; Ask Lens collapses to a 48px icon circle 84px above the bottom.

## Elevation & Depth

Hybrid: glass layering plus soft ambient shadows. Surfaces sit on the desk via backdrop blur, a hairline border and a low shadow. Hover raises cards 4px and swaps to an indigo-tinted lift shadow. Motion uses one easing curve, `cubic-bezier(.16, 1, .3, 1)`: cards rise in (10px translate plus 8px blur, .7s, staggered 70ms by index), pages rise in at .55s. All animation and hover transforms switch off under `prefers-reduced-motion`.

### Shadow Vocabulary
- **Rest** (`box-shadow: 0 1px 2px rgba(18, 20, 26, .04), 0 8px 24px -12px rgba(18, 20, 26, .14)`): cards, rail, top bar.
- **Lift** (`box-shadow: 0 2px 4px rgba(18, 20, 26, .05), 0 18px 36px -16px rgba(40, 52, 140, .26)`): card hover, popover.
- **Copilot glow** (`box-shadow: 0 14px 34px -14px rgba(40, 52, 140, .6)`; hover `0 20px 40px -16px rgba(40, 52, 140, .7)`): the floating Ask Lens pill only.

### Named Rules
**The Soft Offset Rule.** Shadows are always blurred and negatively spread. No hard offset shadows. (The logo mark's `6px 6px 0` ring is how the mark is drawn, not elevation.)

## Shapes

Generously rounded. Cards 20px, rail 22px, top bar and popover 18-20px, nav items and chat bubbles 14px, inputs, buttons, quotes and alerts 12px, tabs 10px. Every small status element (verdict chip, source badge, pill, price pill, copilot) is a full pill (999px). Graphics are built from circles and rounded bars: the strip's 2px rail, 8px band and 20px tick; a 14px white-ringed dot; the orb's slowly morphing blob.

**The No-SVG Rule.** `st.html` strips `<svg>`. Draw every graphic (consensus strip, logo mark, orb, tone meter) with absolutely positioned HTML spans and CSS. Icons come from Streamlit's Material Symbols Rounded (`:material/...:`).

## Components

### Buttons
- **Shape:** gently rounded (12px).
- **Primary:** ink fill with white text; hover `#2a2e3a`.
- **Secondary:** Streamlit default with the shared 12px radius.
- **Focus:** 2px periwinkle outline at 2px offset, everywhere.

### Chips
- **Verdict chip:** pill, soft verdict ground with full verdict text, 700 weight, label plus signed percent.
- **Source badge:** pill, .68rem, coloured by origin (see The Three Sources Rule).
- **Pill:** neutral `rgba(18,20,26,.06)`, or up/down/accent variants.

### Cards / Containers
- **Corner Style:** 20px.
- **Background:** glass surface, or a 160deg tint gradient for region cards.
- **Shadow Strategy:** Rest, then Lift with a 4px raise on hover.
- **Border:** 1px hairline.
- **Internal Padding:** 18px 20px (14px mobile). Chart cards use keyed containers (`card_*`) with the same treatment and 10px bottom padding.
- **Head:** title left, source badge right; optional caption subline.

### Stat Card
Label plus verdict chip, then the big figure, QoQ/YoY deltas coloured up/down, the consensus strip, then the source badge. Tinted by verdict: mint for beat, apricot for inline, rose for miss, untinted when no consensus.

### Consensus Strip (signature)
26px track: a 2px hairline rail; an 8px periwinkle band for the estimate low-to-high range; a 3px gap bar in verdict colour from consensus to actual; a 2px x 20px ink tick at consensus; a 14px verdict-coloured dot with a 2.5px white ring at actual. Legend underneath in .72rem tabular. With no consensus the strip keeps its footprint: a dashed rail, a ghost tick at centre, a grey dot, and a link to enter consensus.

### AI Orb (signature)
A circle with a radial gradient on one hue `--h`, inset shading and a hue-matched drop glow, plus two white eyes. It breathes (5s), morphs its radius (9s) and blinks (6s). Hue comes from call tone: confident 158, positive 168, neutral 230, cautious 38, negative 8. With no tone it shows idle grey (`#F1F2F5` to `#9EA2AE`) with eyes held at 28% height. Sizes are 36 / 64 / 92px. Pairs with the tone meter, an 8px gradient bar from `#E58A73` through `#E8C27A` and `#B9C2F5` to `#79CFAE`, with a white, ink-ringed 14px marker.

### Inputs / Fields
- **Style:** solid white, 12px radius, hairline-strong border, minimum 40px high in the top bar. Labels are hidden in the top bar.

### Navigation
- **Rail:** glass column with an ink logo tile at the top (36px, 12px radius), 44px icon targets (22px icons, ink-secondary), a 28px hairline separator before the utility pages. Hover gives a periwinkle-soft ground and a 1px raise; the current page is an ink chip with a white icon.
- **Mobile:** a horizontal bottom bar.

### Price Pill
White pill: price (700, 1.05rem), change in beat/miss colour, then source and delay as a .72rem caption with a 7px live dot (green with a 2.2s pulse when real-time, amber and static when delayed).

### Ask Lens (floating copilot)
Fixed bottom-right ink-glass pill (90% ink, 14px blur, white 12% border, copilot glow) that raises 3px on hover. It opens a 20px-radius popover with a small orb header. Chat bubbles are 14px radius: user on periwinkle-soft, AI on 4% ink.

### Tables
.88rem tabular text; .76rem/600 ink-tertiary headers over a hairline-strong rule; 10px cells with hairline row rules; hovered rows get a 4% periwinkle wash. A text variant left-aligns and wraps.

## Do's and Don'ts

### Do:
- **Do** define new tokens only in `theme.css` `:root` and mirror chart colours in `components.py` constants.
- **Do** give every figure a verdict (chip, tint, strip) and a source badge.
- **Do** use tabular numerals for every number.
- **Do** draw graphics with positioned spans; keep the strip's footprint even when data is missing.
- **Do** keep transitions on `cubic-bezier(.16, 1, .3, 1)` and honour reduced motion.

### Don't:
- **Don't** use `<svg>` in `st.html`; it is stripped.
- **Don't** use beat/inline/miss colours for anything except verdicts and up/down/live state.
- **Don't** tint a stat card when there is no consensus.
- **Don't** use hard offset shadows; elevation is the Rest and Lift pair only.
- **Don't** let Korean break mid-word; keep `word-break: keep-all`.
