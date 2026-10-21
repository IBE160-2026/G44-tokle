---
name: LiquidOracle
description: Local web app that tells whether a Polymarket wallet's results show skill or luck. Calm "lab report" look with serif headlines; tech-neutral (frontend chosen in architecture).
status: final
created: 2026-10-16
updated: 2026-10-21
sources:
  - _bmad-output/planning-artifacts/prds/prd-LiquidOracle-2026-10-12/prd.md
colors:
  # Light theme. In the dark theme every {colors.x} resolves to {colors.x-dark}.
  surface: '#F7F7F5'
  surface-raised: '#FFFFFF'
  ink: '#141922'
  ink-muted: '#5A616B'
  border: '#E3E5E8'
  border-strong: '#868D97'
  accent: '#1D5BA6'
  accent-hover: '#1C5396'
  on-accent: '#FFFFFF'
  accent-tint: '#E8F0FA'
  accent-tint-soft: '#F1F5FB'
  neutral-tint: '#F1F2F4'
  dot-empty: '#C5CAD1'
  warning-bg: '#FFF3D1'
  warning-border: '#A87400'
  warning-ink: '#4F3700'
  error: '#B42318'
  pill: '#1A2029'
  on-pill: '#FFFFFF'
  chart-bar: '#8E959F'
  chart-tail: '#3F74B3'
  chart-active: '#43474E'
  # Dark theme
  surface-dark: '#0E1116'
  surface-raised-dark: '#151A21'
  ink-dark: '#E7EAEE'
  ink-muted-dark: '#A2AAB5'
  border-dark: '#272E38'
  border-strong-dark: '#6C7582'
  accent-dark: '#6EA8EE'
  accent-hover-dark: '#7DB0EE'
  on-accent-dark: '#0E1116'
  accent-tint-dark: '#17304F'
  accent-tint-soft-dark: '#132235'
  neutral-tint-dark: '#1B222C'
  dot-empty-dark: '#4A535F'
  warning-bg-dark: '#33270A'
  warning-border-dark: '#D9A21B'
  warning-ink-dark: '#F4D58A'
  error-dark: '#F28B82'
  pill-dark: '#0E1116'
  on-pill-dark: '#E7EAEE'
  chart-bar-dark: '#5E6774'
  chart-tail-dark: '#6193CF'
  chart-active-dark: '#BDC0C5'
typography:
  # Serif: headlines and the Verdict. Sans: everything you read. Mono: addresses and table numbers.
  # Build must-have: an open-licence serif font file is bundled with the app and listed first in the
  # serif stack (chosen in architecture). The system serifs below stay as fallbacks. Nothing is loaded
  # from the internet, so Offline Mode keeps working.
  brand:
    fontFamily: '"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
    fontSize: 26px
    fontWeight: '700'
    letterSpacing: -0.01em
  verdict-display:
    fontFamily: '"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
    fontSize: 56px
    fontWeight: '600'
    lineHeight: '1.08'
    letterSpacing: -0.02em
  verdict-display-sm:
    fontFamily: '"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
    fontSize: 40px
    fontWeight: '600'
    lineHeight: '1.1'
  verdict-display-xs:
    fontFamily: '"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
    fontSize: 34px
    fontWeight: '600'
    lineHeight: '1.12'
  page-title:
    fontFamily: '"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
    fontSize: 52px
    fontWeight: '700'
    lineHeight: '1.08'
    letterSpacing: -0.02em
  page-title-sm:
    fontFamily: '"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
    fontSize: 36px
    fontWeight: '700'
    lineHeight: '1.12'
  lede:
    fontFamily: '"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
    fontSize: 26px
    fontWeight: '400'
    lineHeight: '1.3'
  lede-sm:
    fontFamily: '"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
    fontSize: 21px
    fontWeight: '400'
    lineHeight: '1.3'
  section-title:
    fontFamily: '"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.25'
  stat-figure:
    fontFamily: '"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
    fontSize: 30px
    fontWeight: '600'
    lineHeight: '1.15'
  eyebrow:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
    fontSize: 13px
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: 0.08em
  body:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.55'
  body-strong:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.35'
  small:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  label:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
    fontSize: 13px
    fontWeight: '600'
    lineHeight: '1.4'
  number:
    fontFamily: 'ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace'
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
rounded:
  sm: 6px
  md: 10px
  lg: 14px
  full: 9999px
spacing:
  '1': 4px
  '2': 8px
  '3': 12px
  '4': 16px
  '5': 24px
  '6': 32px
  '7': 48px
  '8': 64px
  content-max: 1200px
  top-bar-height: 64px
  # Breakpoints (the only ones; EXPERIENCE.md › Responsive & Platform uses these)
  bp-stack: 900px
  bp-phone: 640px
  bp-small: 400px
components:
  top-bar:
    background: '{colors.surface-raised}'
    border-bottom: '1px solid {colors.border}'
    height: '{spacing.top-bar-height}'
  nav-link-active:
    foreground: '{colors.accent}'
    underline: '2px solid {colors.accent}, 8px below the text'
  nav-link-hover:
    foreground: '{colors.ink}'
    underline: '2px solid {colors.border-strong}'
  focus-ring:
    color: '{colors.accent}'
    width: 2px
    offset: 3px
  theme-toggle:
    size: 40px
    border: '1px solid {colors.border}'
    radius: '{rounded.full}'
    icon: '{colors.ink}'
  offline-pill:
    background: '{colors.pill}'
    foreground: '{colors.on-pill}'
    border-dark-theme: '1px solid {colors.border-strong}'
    radius: '{rounded.full}'
    typography: '{typography.label}'
  card:
    background: '{colors.surface-raised}'
    border: '1px solid {colors.border}'
    radius: '{rounded.lg}'
    shadow-light-theme: '0 1px 2px rgba(20,25,34,.04)'
  verdict-hero:
    dot-size: 30px
    dot-ring: 6px
    dot-filled: '{colors.accent}'
    dot-empty: '{colors.dot-empty}'
    text: '{typography.verdict-display}'
  verdict-pill:
    background: '{colors.accent-tint}'
    background-none: '{colors.neutral-tint}'
    foreground: '{colors.ink}'
    dot-size: 12px
    radius: '{rounded.sm}'
  address-card:
    background: '{colors.surface-raised}'
    border: '1px solid {colors.border}'
    radius: '{rounded.md}'
    typography: '{typography.number}'
  text-input:
    background: '{colors.surface-raised}'
    border: '1px solid {colors.border-strong}'
    border-invalid: '2px solid {colors.error}'
    radius: '{rounded.sm}'
    height: 48px
  warning-box:
    background: '{colors.warning-bg}'
    foreground: '{colors.warning-ink}'
    stripe: '6px solid {colors.warning-border}'
    radius: '{rounded.sm}'
  error-message:
    foreground: '{colors.error}'
    typography: '{typography.small}'
  info-box:
    background: '{colors.accent-tint-soft}'
    foreground: '{colors.ink}'
    border: '1px solid {colors.accent-tint}'
    radius: '{rounded.sm}'
  info-tag:
    foreground: '{colors.ink-muted}'
    border: '1px solid {colors.border-strong}'
    radius: '{rounded.full}'
    typography: '{typography.label}'
  chart-alt-box:
    background: '{colors.neutral-tint}'
    foreground: '{colors.ink}'
    radius: '{rounded.sm}'
  data-table:
    head-background: '{colors.neutral-tint}'
    head-foreground: '{colors.ink-muted}'
    row-divider: '1px solid {colors.border}'
    row-hover: '{colors.accent-tint-soft}'
  tabs:
    active: '{colors.accent}'
    active-underline: 3px
    inactive: '{colors.ink-muted}'
  luck-chart:
    bars: '{colors.chart-bar}'
    gridlines: '{colors.border}'
    marker: '{colors.accent}'
    marker-width: 3px
    marker-dot: 12px
    axis-text: '{colors.ink-muted}'
    active-bar: '{colors.chart-active}'
    tail-bars: '{colors.chart-tail}'
  chart-tooltip:
    background: '{colors.ink}'
    foreground: '{colors.surface-raised}'
    radius: '{rounded.sm}'
  chart-tail-label:
    background: '{colors.accent-tint}'
    foreground: '{colors.ink}'
    radius: '{rounded.sm}'
  button-primary:
    background: '{colors.accent}'
    background-hover: '{colors.accent-hover}'
    foreground: '{colors.on-accent}'
    radius: '{rounded.sm}'
  copied-state:
    background: '{colors.accent-tint}'
    foreground: '{colors.accent}'
  progress-bar:
    track: '{colors.neutral-tint}'
    fill: '{colors.accent}'
    radius: '{rounded.full}'
  motion:
    hover: '120ms ease-out'
    lift: 'translateY(-1px), buttons only'
    lift-shadow-light: '0 3px 8px rgba(20,25,34,.10)'
    lift-shadow-dark: '0 3px 10px rgba(0,0,0,.45)'
    bar-build: '420ms cubic-bezier(.2,.7,.2,1), 4ms stagger'
    marker-drop: '260ms, 14px'
---

## Brand & Style

LiquidOracle reads like a **research report**, not a trading app. It answers one question, skill or luck, and its value is that the user can trust the answer. The look: a large serif headline stating the Verdict, the odds in a quiet serif line under it, calm grey surfaces, white cards, one blue accent, and figures you can compare at a glance. Nothing celebrates or urges action.

What it must never look like: a trading terminal with green "buy" and red "sell" signals, a leaderboard, or a tip service. A strong Verdict is *strong evidence*, not a recommendation, so nothing on screen may read as "go copy this wallet". Edvard rejected check marks for this reason (2026-10-16), and later renamed the second section from "Find wallets to follow" to **"Scan wallets"** after the wording review (same day).

**Visual reference.** Edvard chose this direction from ChatGPT image references (round 2): `imports/round-2-images/verdict-light.webp`, `verdict-dark.webp`, `watchlist-light.webp`, `watchlist-dark.webp`. The built references are `mockups/verdict.html` and `mockups/lookup.html`, written from scratch to match the images. This file and `EXPERIENCE.md` win over all of them. Round 1 (`imports/round-1-html/`, four ChatGPT HTML layouts made from the prompt in `.working/chatgpt-prototype-prompt.md`) was not used as a base.

**Logo.** A ring around the luck curve, with a marker line where the wallet sits on the chart: two thirds of a spread right of the middle, as at odds of about 1 in 4. It says what the product does: put one result against what luck alone would give. Edvard chose the idea from a ChatGPT image (`imports/round-3-logo/logo-reference.webp`). It was redrawn from scratch as SVG, with the marker moved right into the curve's tail (his change) and the strokes sized to read at 16 px; he picked marker position A of three (`.working/logo-variants.png`). Files: `mockups/logo/liquidoracle-logo.svg` (master, accent blue) and `mockups/logo/favicon.svg` (switches to the dark-theme blue when the browser is dark). Reference page with the logo at all sizes and the tab behaviour: `mockups/logo-and-tab.html`.

**Light and dark.** Both themes exist. The app starts on the computer's system setting; a toggle in the top bar switches theme, and the pick is remembered in that browser (Edvard, 2026-10-16). In the dark theme every colour token resolves to its `-dark` twin; where a component differs by theme, its token says so (`border-dark-theme`, `shadow-light-theme`).

## Colors

Each colour has one job. Dark values in brackets.

- **Surface `#F7F7F5` (`#0E1116`)** is the page background. **Surface raised `#FFFFFF` (`#151A21`)** is used for cards, the top bar and the address card.
- **Ink `#141922` (`#E7EAEE`)** covers headlines, the Verdict and body text. **Ink muted `#5A616B` (`#A2AAB5`)** covers eyebrow labels, captions, axis labels, "Data stored …", table headers and the odds line under the Verdict.
- **Border `#E3E5E8` (`#272E38`)** is for card edges, rules and table rows. It is decoration only. **Border strong `#868D97` (`#6C7582`)** is for anything the user must see to use it, such as input outlines, the nav hover underline and the dashed *Not enough data* box (3:1 or better).
- **Accent blue `#1D5BA6` (`#6EA8EE`)** is for links, the active nav item and tab, the focus ring, filled evidence dots, the Real PnL marker on the chart, and the primary button. **Accent hover `#1C5396` (`#7DB0EE`)** is the primary button under the pointer or focus. Blue carries no profit or loss meaning, unlike green and red.
- **Accent tints:** `accent-tint` (`#E8F0FA` / `#17304F`) behind Verdict pills, the "Copied" state and the chart's tail label; `accent-tint-soft` (`#F1F5FB` / `#132235`) behind info notes and hovered table rows.
- **Neutral tint `#F1F2F4` (`#1B222C`)** sits behind the chart's text alternative, the table header row and the *No evidence of skill* pill.
- **Empty dot `#C5CAD1` (`#4A535F`)** is the ring of an empty evidence dot. It is decoration; the Verdict text carries the meaning.
- **Warning** (`#FFF3D1` background, `#A87400` stripe, `#4F3700` text; dark `#33270A`, `#D9A21B`, `#F4D58A`) is only for cautions about a result: the Exit PnL warning (FR-11), the Flag (FR-22), the dropped-wallets message (FR-17), positions left out of the Copy Test (FR-18) and the "no bets after this date" Scan warning. It always comes with a ⚠ and text.
- **Error `#B42318` (`#F28B82`)** is only for things that went wrong: an invalid address or Scan field, Polymarket not answering, "Not available offline", a failed copy. It is never used for losses or weak Verdicts.
- **Offline pill:** `#1A2029` with white text. In the dark theme it is `#0E1116` with a `border-strong` outline, so it still stands out against the top bar.
- **Chart:** bars `#8E959F` (`#5E6774`) are just dark enough to reach 3:1 on the card and no darker, so the blue marker (3 px, with a dot and a label above the bars) is still the one thing the eye goes to. Tail bars `#3F74B3` (`#6193CF`) are blue *and* clearly darker than plain bars, so the highlight also shows without colour vision. The active bar is `#43474E` (`#BDC0C5`).

Not used: green anywhere; red for negative PnL (a negative number gets a minus sign, in ink); gradients.

**Contrast** (WCAG 2.1 AA: 4.5:1 for text, 3:1 for UI parts and graphics), computed with a script on 2026-10-16 and confirmed by two independent reviewers:

| Pair | Light | Dark |
|---|---|---|
| ink on surface-raised | 17.62 | 14.48 |
| ink-muted on surface | 5.83 | 8.06 |
| ink-muted on neutral-tint (table head) | 5.58 | 6.83 |
| accent on surface-raised (links) | 6.78 | 7.07 |
| accent on accent-tint ("Copied", pills) | 5.90 | 5.41 |
| on-accent on accent (primary button) | 6.78 | 7.65 |
| on-accent on accent-hover | 7.70 | 8.39 |
| warning-ink on warning-bg | 10.11 | 10.26 |
| warning-border on warning-bg (stripe) | 3.68 | 6.36 |
| error on surface-raised | 6.57 | 7.32 |
| on-pill on pill | 16.37 | 15.67 |
| border-strong on surface-raised (inputs) | 3.35 | 3.75 |
| chart-bar on surface-raised | 3.02 | 3.05 |
| chart-tail on surface-raised | 4.82 | 5.48 |
| chart-active on surface-raised | 9.33 | 9.58 |
| tooltip text (surface-raised on ink) | 17.62 | 14.48 |
| focus ring (accent) on surface | 6.32 | 7.65 |

Below 3:1 on purpose, because text carries the meaning: the empty dot (1.65 / 2.24), the marker against the bars next to it (2.24 / 2.32), the dark pill's fill against the top bar (its outline is 3.75), and tail bars against plain bars (1.59 / 1.79, a lightness change on top of the hue change). The light warning stripe uses `#A87400` rather than the brighter yellow in the image, because the brighter yellow is under 3:1. The chart bars were first lighter than 3:1; Edvard had them darkened to just reach it, and the marker made thicker so it still stands out (2026-10-16).

**Windows High Contrast (forced colours).** Bars, evidence dots and the progress fill are drawn as backgrounds, which forced colours removes. Under `forced-colors: active` they keep their shape in system colours: bars and filled dots in `CanvasText`, tail and active bars and the progress fill in `Highlight`.

## Typography

There are three families. Nothing is ever loaded from the internet, so Offline Mode looks the same (UJ-3):

- **Serif** (a bundled open-licence font in the build; system fallbacks Iowan Old Style / Palatino Linotype / Palatino / Georgia): the brand name, the Verdict (`verdict-display`), page titles (`page-title`), the odds line and page ledes (`lede`), card titles (`section-title`), and big figures in the honesty notes (`stat-figure`). The serif carries the "report" feel.
- **Sans** (system UI font): everything read as running text, such as body, notes, stats, nav and tabs. `eyebrow` (13 px, uppercase, tracked +0.08em, muted) labels a page above its title: "WALLET ANALYSIS", "WALLET SCAN", "SKILL OR LUCK". Stats in the Verdict card use `body-strong` (20 px) with the number in semibold. `label` (13 px semibold) is for pills, tags and field labels.
- **Monospace**: Wallet addresses, plus numbers in table columns (Resolved bets, Real PnL), right-aligned so the digits line up. Odds phrases stay in sans, because they are words. Numbers outside tables use the sans with tabular figures.

**Smaller screens.** Below `{spacing.bp-phone}` (640 px): `verdict-display-sm` (40 px), `page-title-sm` (36 px), `lede-sm` (21 px). Below `{spacing.bp-small}` (400 px): `verdict-display-xs` (34 px).

**Must-have for the build (Edvard, 2026-10-16): bundle an open-licence serif font.** System serifs differ per computer (Palatino on Windows, Iowan on Mac), so the headline look would change from machine to machine. The build ships one serif font file under an open licence (SIL Open Font License) inside the app, served locally, first in the serif stack. The system serifs stay as fallbacks. Which font is chosen in `bmad-architecture`. Candidates: IBM Plex Serif (same family as the IBM Plex Sans and Mono named in Edvard's image prompt) or Source Serif 4. The mockups use the system stack only.

No text below 13 px, at any width. Text must still read at 200% browser zoom.

## Layout & Spacing

The scale is based on 4 px: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64. Content sits in one centred column, up to `{spacing.content-max}` (1200 px, wide enough for the Verdict on one line), with `{spacing.5}` side margins (`{spacing.4}` below 640 px).

**Breakpoints** are `{spacing.bp-stack}` (900 px: two-column parts stack), `{spacing.bp-phone}` (640 px: phone sizes, short axis labels) and `{spacing.bp-small}` (400 px: smallest type, end axis labels hidden). There are no others.

**Page header pattern** (Verdict page, Scan pages, Lookup): the eyebrow, the serif title and a serif lede on the left; on Verdict and Scan pages a supporting card on the right (the address card; the Scan summary card). Below 900 px the right card drops below the title.

**Verdict page, top to bottom** (fixed; every other mention points here):
1. **Verdict card** (the PRD's "Verdict card", FR-8): on the left the Verdict hero, the odds phrase, and in S3 the Flag directly under the odds phrase; on the right the address card. Then a thin rule, then the stats line on the left and the Exit PnL warning on the right, level with it. The warning and the Flag are inside the card, next to the Verdict (FR-11, FR-22), never inside the Verdict hero.
2. **Explanation** (S3): directly under the Verdict card, before the chart (FR-23).
3. **Chart card.**
4. **Honesty notes card** ("What this test can't see").
5. **Domain table** (S3).

Below 900 px the two-column parts stack: the address card under the hero, the warning under the stats.

**Lookup page** (S1, `mockups/lookup.html`): eyebrow "SKILL OR LUCK", the title "Check a wallet" in `page-title`, and a lede saying what the check does. Then the address field card: the label "Wallet address", the field and the primary button "Check wallet" on one row (the button drops under the field below 640 px), and a hint under it. In Offline Mode, a second card follows: "Sample Wallets", a list of the Sample Dataset's Wallets in two groups, *Real Wallets* and *Synthetic Wallets*. The content column is narrower here (720 px), because the page is one form.

**Scan pages** (S2): page header with the Scan summary card, then the Scan tabs, then the page's content (info box, then the table card).

Wide tables scroll inside their own card, never the whole page.

## Elevation & Depth

Nearly flat. Cards are lifted from the page by colour (`surface-raised` on `surface`), a 1 px `border`, and in the light theme a barely visible 1–2 px shadow. The dark theme has no shadow. The top bar has a bottom border. There are no pop-ups.

The only things that rise are **buttons under the pointer or keyboard focus**: 1 px up, with the lift shadow (`components.motion`) (Edvard, 2026-10-16). Cards, stats and text never move. The chart's small hover labels sit just above the bars with the same shadow.

## Shapes

- `{rounded.lg}` (14 px) for the big cards: chart, honesty notes, table cards, Scan summary, the Lookup form card.
- `{rounded.md}` (10 px) for the address card and the Sample Wallets items.
- `{rounded.sm}` (6 px) for inputs, the warning box, info box, chart text box, Verdict pills and buttons.
- `{rounded.full}` for the Offline pill, the theme toggle, info tags, the progress bar and the evidence dots.

## Components

Stage marks: **S1**, **S2**, **S3** = stage 1, 2, 3 (PRD §6.1). Each component has one name, used the same way in `EXPERIENCE.md`. Behaviour lives in `EXPERIENCE.md` › Component Patterns; this section gives the look.

- **Skip link (S1).** First thing on every page, hidden until it gets keyboard focus; then a `surface-raised` box with a 2 px accent border at the top left, "Skip to content".
- **Logo (S1).** The mark is 32 px in the top bar, left of the name, in `{colors.accent}`. As the favicon it is 16 px, with the ring at least 1.1 px and the marker 0.8 px. It is always one colour on a plain background: no gradient, no outline, no text inside it. During a Scan, the favicon's ring becomes a progress ring: a faint full ring (20% opacity) with an accent arc filling clockwise from the top.
- **Top bar (S1).** On the left, the logo and the serif brand "LiquidOracle" (one link to *Check a wallet*), then the two section links, *Check a wallet* (S1) and *Scan wallets* (S2, absent until stage 2 is built). The active section is in accent with a 2 px underline. On the right, the theme toggle, then the Offline pill. Below 640 px the section links wrap under the brand and the tools move to their own row, right-aligned.
- **Theme toggle (S1).** A 40 px round button with a moon icon (light theme) or a sun icon (dark theme), named "Dark theme" for screen readers with a pressed state. It never shrinks below 40 px.
- **Offline pill (S1).** "**Offline Mode** · sample data only" in `label` type, the first two words semibold, at 13 px at every width (it wraps rather than shrinks).
- **Verdict card (S1).** The whole top block of the Verdict page (see Layout). It has no box of its own: it is the page header, so it sits on `surface` and ends at the chart card.
- **Verdict hero (S1).** Three evidence dots, then the Verdict in `verdict-display`. It is the page's main heading.
  - `●●●` *Skilled (high confidence)*: three filled accent dots
  - `●●○` *Likely skilled*: two filled, one empty
  - `○○○` *No evidence of skill*: three empty rings
  - *Not enough data*: no dots, the text in muted ink, inside a dashed `border-strong` outline
- **Odds phrase (S1).** Under the hero in `lede`, ink muted.
- **Verdict pill (S2, S3).** The small version for tables (Watchlist, Hold-up group cards, Domain table): a tinted box with 12 px dots and the Verdict in `small` semibold. *No evidence of skill* uses `neutral-tint`; *Not enough data* uses a dashed outline and no fill.
- **Copy Verdict pill (S2).** Same shape, text only: *Beat random picks* (accent tint), *No better than random picks* (neutral tint), *Not enough data* (dashed). No dots, because the dots belong to the skill Verdict.
- **Address card (S1).** Label "Wallet address" (small, muted), the full address in monospace, and the copy button: a 36 px icon button. In the copied state it shows "Copied" beside the icon on `accent-tint`; when copying fails, an error message appears under the card and the address text is selected.
- **Stats line (S1).** Label "Stats" (muted), then "**212** resolved bets · Real PnL **$40,180**" in `body-strong`, then "Data stored 15 Oct 2026, 14:02" in `small` muted.
- **Warning box (S1).** `warning-box` tokens: ⚠ icon, a bold first sentence, a normal second sentence. Screen readers hear a hidden "Warning:" first.
- **Flag (S3).** A compact warning box directly under the odds phrase: "⚠ Likely market maker (heuristic, may be wrong)".
- **Explanation (S3).** Body text up to 60 words in a `card` without a title, directly under the Verdict card. In Mock LLM Mode, or when the template replaced the model's text, an info tag "Template text" sits at its top right.
- **Chart card (S1).** Title "Simulated results" in `section-title` with "(10,000 replays with no edge)" in `small` after it; the "About this chart" disclosure on the right (accent text; it opens below the header in an `accent-tint-soft` box); the luck chart; a one-line hint in `small` muted; the text alternative in a `chart-alt-box`.
- **Luck chart (S1).** `luck-chart` tokens: grey bars, faint gridlines, a y-axis "Number of replays", an x-axis in dollars. The Real PnL marker is a 3 px accent line with a 12 px dot on top and the label "This Wallet: $40,180" above it in semibold accent. About 240 px tall (200 px below 640 px). Below 640 px the x-axis uses short labels ("−$100k") and drops every other tick; below 400 px the two end labels go too.
- **Chart tooltip (S1).** A small dark label (`chart-tooltip`) above the bar under the pointer or keyboard: the range on one line, the replay count in semibold on the next. It never covers the marker's dot or label: next to the marker it moves to the side.
- **Chart tail label (S1).** `chart-tail-label`: "2,500 of 10,000 replays did this well or better", semibold, right of the marker near the top of the plot, wrapping within a third of the plot's width.
- **Honesty notes card (S1).** Title "What this test can't see". Three columns split by thin rules: (1) the share of the Real PnL from the largest bet as a `stat-figure` ("70%") with its sentence under it, or the dollar amount when the share would not make sense (see EXPERIENCE.md); (2) "212 of 260" as a `stat-figure` with "positions held to resolution" and the Exit PnL under it; (3) the fixed limits text and "This is not financial advice." Below 900 px the columns stack. Under the columns, split by a thin rule, the "Left out of the test" line in `body-sm` (counts per reason, fees not counted, and FR-11's plain sentences when they apply, the 10% sentence in the warning style of the Exit PnL warning), then the computed-on line ("Computed on the latest 2,000 bets · Seed 44") in `caption`.
- **Domain table (S3).** A Data table with columns Domain, Resolved bets, Domain Verdict (Verdict pill), and the note under it in `small` muted.
- **Back link (S1, used from S2).** A plain accent text link above the eyebrow: "← Back to Watchlist (Cut-off Date 1 Jun 2026)".
- **Address field (S1).** On the Lookup page: the label "Wallet address" in `label` type above it, the field in monospace (`text-input` tokens, 48 px tall, full width of its card) and the primary button "Check wallet" beside it. Invalid: a 2 px error border and an error message under it.
- **Sample Wallets list (S1, Offline Mode only).** In its own card on the Lookup page, titled "Sample Wallets". Two groups with `label` headings: *Real Wallets* (shortened addresses in monospace) and *Synthetic Wallets* (names such as "Sharp trader", each with an info tag "synthetic"). Each item is a full-width link row, 48 px tall, `rounded.md`, with a chevron at the right; it reacts like a clickable table row.
- **Fetching indicator (S1).** On the Verdict page, in place of the Verdict card while data is fetched: the heading "Checking 0x7c3a…d3f5" in `section-title`, then three small accent dots pulsing in turn and "Fetching trades from Polymarket…" in `small` muted. Static dots with *reduce motion*.
- **Error message (S1).** `error-message` tokens: a ✕ icon (hidden from screen readers) and the error sentence, directly under the field or card it belongs to; screen readers hear a hidden "Error:" first.
- **Scan header (S2).** Eyebrow "WALLET SCAN", the title "Scan of 200 Wallets" in `page-title`, and the lede "Cut-off Date 1 June 2026 · run 14 Oct 2026", with a second lede line in `body-sm` for the population tested ("Markets resolved in the 90 days before the Cut-off Date, top 100 by volume · 97 of 100 Markets used · Seed 44"). On the right, the Scan summary card with three figures split by rules: Wallets scanned, rated *Skilled (high confidence)*, Scan run date (see `imports/round-2-images/watchlist-light.webp`).
- **Scan tabs (S2).** *Watchlist* · *Hold-up Test* · *Copy Test*: links styled as tabs. The current one is in accent with a 3 px underline, over a 1 px rule across the full width.
- **New Scan form (S2).** In a `card`: two fields side by side (one column below 640 px), "Cut-off Date" (a date field) and "Number of Wallets" (a number field), both `text-input` with `label` type labels and a hint line under each ("Must be in the past." / "10 to 500."); then the primary button "Start Scan". In Offline Mode the date field is read-only with an info box under it.
- **Scan list (S2).** A Data table of earlier Scans: Run date, Cut-off Date, Wallets, Watchlist size, Status. Status is text ("Finished", "Running: Fetching Wallets 84 of 600", "Interrupted at 120 of 200", "Stopped at 120 of 200", "Failed", "Data rebuilt, cannot resume") with a secondary button "Resume" only for interrupted and stopped Scans.
- **Scan progress bar (S2).** 8 px high, accent fill on `neutral-tint`, with "84 of 200 Wallets checked" beside it.
- **Hold-up group cards (S2).** Two `card`s side by side (stacked below 900 px), titled *Before-Cut-off Passers* and *Comparison Group*: a Verdict pill, the odds phrase, then four small figures in a 2 × 2 grid (Resolved bets counted, Real PnL, Wallets in the group, Wallets dropped).
- **Info box (S2).** `info-box` tokens, for neutral notes that qualify a result but are not warnings (the Minimum Luck Passes line, the offline Scan date).
- **Data table (S2, S3).** Used for the Watchlist, the Copy Test's per-Wallet table, the Scan list and the Domain table. Inside a card, with a serif card title and a muted caption above the table. The header row has a `neutral-tint` background. No rank column. The Wallet address is shortened (`0x1a2b…9f0e`, monospace) and is an accent link that opens the Verdict page inside the app, with **no external-link icon** (Edvard, 2026-10-16); its accessible name is "Open Verdict for Wallet 0x1a2b…9f0e". Number columns are monospace and right-aligned. A table that can scroll sideways sits in a focusable scroll area with the focus ring.
- **Info tag (S2).** `info-tag` tokens: "Extra information", "Not luck-checked", "synthetic", "Template text".
- **Button, primary.** `button-primary` tokens, 44 px tall, `label`-weight 15 px text. At most one per page. **Button, secondary:** `surface-raised` with a `border-strong` outline and accent text ("Resume").

### Interaction states (Edvard, 2026-10-16)

The page should feel satisfying to use, quietly. **Only clickable things react**, and keyboard focus looks exactly like hover, plus the focus ring (`components.focus-ring`):

| Element | Hover / focus | Pressed or done |
|---|---|---|
| Top bar links | `nav-link-hover`: text turns ink, grey 2 px underline (the current section stays accent) | — |
| Brand (logo + name) | Name turns accent | — |
| Buttons (primary, secondary, theme toggle, icon buttons) | Lift 1 px with the lift shadow; primary turns `accent-hover`; icon buttons get a `neutral-tint` background | Back down on press |
| Copy button | As icon buttons | `copied-state` for 2 s |
| "About this chart" | Underline appears, faint `accent-tint-soft` behind it | — |
| Clickable table rows, Sample Wallets items | The whole row turns `accent-tint-soft`; focus also draws the ring around the row | — |
| Chart bars | The bar under the pointer (or keyboard) turns `chart-active`; the chart tooltip shows above it | — |
| Wallet marker | Every bar from the wallet's bar rightwards turns `chart-tail`; the chart tail label shows | A click pins the highlight; Esc clears it |

**Chart build-up.** When the chart comes into view, the bars grow up into the curve from left to right (`components.motion.bar-build`, under a second in all). Then the wallet marker drops 14 px into place and fades in (260 ms). It happens once per page view. Without JavaScript the chart is simply shown complete.

**Calm and quick.** Hover and focus changes take 120 ms. Nothing bounces, loops or flashes. With the system's *reduce motion* setting on, nothing moves at all: no lift, no build-up, no drop, no pulsing dots. The chart appears complete, and colour changes happen instantly.

## Do's and Don'ts

| Do | Don't |
|---|---|
| State the Verdict as a big serif headline, with dots as a second signal | Show a Verdict by colour or dots alone |
| Use blue intensity (filled vs empty dots, tint vs none) for evidence strength | Use green for skilled, or red for unskilled or losses |
| Keep warnings in their own yellow box inside the Verdict card, next to the Verdict | Merge a warning into the Verdict headline |
| Use monospace for addresses and table numbers, right-aligned | Use monospace for sentences such as the odds phrase |
| Keep the chart's text alternative visible under the chart | Hide the text alternative or put it behind a hover |
| Bundle the serif font file with the app; system fonts for the rest | Load web fonts from the internet (that breaks Offline Mode) |
| Open Wallets inside the app with a plain link | Put an external-link icon on in-app links |
| Sort by evidence and say so in the caption | Rank numbers ("#1"), which read as "best wallet" |
| One primary button per page | Celebratory visuals: confetti, trophies, check marks, thumbs up, emoji |
| Give hover feedback only to things you can click | Hover effects on cards, stats or text, which suggest a click that does nothing |
| Make keyboard focus look the same as hover | Hover-only feedback that keyboard users never see |
| Keep motion under a second, and only on first view | Looping, bouncing or attention-seeking animation; any motion with *reduce motion* on |
