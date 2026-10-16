I am designing a small local web app called **LiquidOracle** for a university course. Please make **4 different HTML prototype versions** of its three main pages, so I can compare layouts and pick one. All the decisions below are fixed; the versions should differ only in **layout and composition** (where things sit, how dense the page is, how the cards are arranged), not in colours, wording or rules.

## What the app does

The user pastes a Polymarket wallet address and the app says whether the wallet's results show skill or just luck. It runs a statistical test: it replays the wallet's bets 10,000 times as if the trader had no edge, and reports how often luck alone does as well. The answer is a **Verdict**, one of four:
- Skilled (high confidence)
- Likely skilled
- No evidence of skill
- Not enough data (fewer than 30 resolved bets)

A second part, "Find wallets to follow", runs a **Scan** of the top 200 wallets by profit made before a chosen **Cut-off Date** and lists the ones rated Skilled (high confidence) in a private **Watchlist**.

## Style (fixed)

- Calm "lab report" look. It must NOT look like a trading app: no green, no red for losses, no buy/sell feel, no check marks, thumbs up, trophies, confetti or emoji.
- Light and dark mode, following the system setting (`prefers-color-scheme`).
- Colours (light / dark):
  - page background `#F7F7F5` / `#16181B`; cards `#FFFFFF` / `#202328`
  - text `#1C1E21` / `#E8EAED`; muted text `#585E66` / `#A3A9B1`
  - borders `#DADDE1` / `#33373D`; strong borders, input outlines, chart bars `#848B94` / `#6E757E`
  - one accent blue `#1D5BA6` / `#7FB0EE` (links, primary button, active nav, focus ring, chart marker); white text on the light-mode button, `#16181B` on the dark one
  - Verdict tints: Skilled (high confidence) `#DCE8F7` / `#1E3A5F`; Likely skilled `#EEF3FA` / `#1C2A3C`; No evidence of skill `#ECEDEF` / `#2A2D32`; Not enough data has no fill and a dashed grey border
  - warning box: background `#FFF4D6` / `#3A2E0F`, left stripe `#A87400` / `#D9A520`, text `#5A3E00` / `#F5D78A`, with a ⚠ icon
  - error text `#B42318` / `#F28B82` (only for real errors, never for losses)
- Fonts: system fonts only (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`), no web fonts. Every number and wallet address in a monospaced font (`ui-monospace, "Cascadia Mono", Menlo, Consolas, monospace`), right-aligned in tables.
- Flat: no shadows, small corners (4–6 px). Content max width 960 px, centred.

## Verdict badge (fixed)

Each Verdict is shown as **text plus evidence dots**, never by colour alone:
- `●●●` Skilled (high confidence)
- `●●○` Likely skilled
- `○○○` No evidence of skill
- Not enough data: no dots, dashed grey outline, muted text

The dots get `aria-hidden="true"`; the text carries the meaning. Warnings are never inside the badge; they sit in their own yellow box just under it.

## Navigation (fixed)

A top bar on every page: the name "LiquidOracle" on the left, then two section links, **Check a wallet** and **Find wallets to follow** (the active one underlined in accent blue), and on the right a dark pill reading **"Offline Mode · sample data only"** (show it in the prototypes).

## Accessibility (fixed, WCAG 2.1 AA)

Real `<button>`, `<a>`, `<label>`, `<table>` with `<th>` elements; a visible focus ring; a "Skip to content" link; headings in order; usable at 320 px width (tables scroll inside their card, not the page).

## Wording rules (fixed)

Plain and unexcited. Never use "guaranteed", "insider", "will win", "copy this" or "recommended". The odds are always written in words, like "a trader with no edge would do this well about 1 time in 4".

## Page 1: Verdict page (use this content)

- Full address: `0x7c3a9e2b41d05f6a8c1e93b7d2f4a6c8e0b1d3f5`
- Verdict: ○○○ No evidence of skill
- Odds: "a trader with no edge would do this well about 1 time in 4"
- Stats: 212 resolved bets · Real PnL $40,180
- A small line: "Data stored 15 Oct 2026, 14:02"
- A warning box right under the badge: "⚠ Positions this Wallet sold before resolution lost money in total. This Verdict covers only bets held to resolution."
- **Luck chart**: an inline SVG histogram of 10,000 simulated results (a bell shape roughly from −$60,000 to +$80,000), x-axis in dollars, with a blue vertical marker labelled "This wallet: $40,180" sitting inside the bars. Directly under the chart, always visible, the text alternative: "This wallet made $40,180 on 212 resolved bets. In 10,000 replays with no edge, a result this good came up about 1 time in 4."
- **Card "What this test can't see"** (always open):
  - 70% of the profit came from the single largest bet.
  - 212 of 260 positions held to resolution. Positions sold early: −$3,150 (Exit PnL).
  - Fixed note: "Long shots tend to be overpriced. The Verdict covers only bets held to resolution, so early exits are not measured and can make a Wallet look better or worse than it is. Wallets are often looked up because they already looked good, and picking by results makes luck look more like skill."
  - "This is not financial advice."

## Page 2: Watchlist (use this content)

- Section "Find wallets to follow" active in the top bar.
- Header line: "Scan of 200 Wallets · Cut-off Date 1 June 2026 · run 14 Oct 2026"
- Sub-navigation for this Scan: **Watchlist** (current) · Hold-up Test · Copy Test
- Note above the table: "At least about 2 of 200 would pass by luck alone, probably more, because these Wallets were picked for high profit."
- Table, sorted by p-value (smallest first), caption saying so. Columns: Wallet (shortened address as a link), Verdict (small badge), Odds, Resolved bets, Real PnL. 7 rows, all ●●● Skilled (high confidence), for example:
  - `0x1a2b…9f0e` · fewer than 1 time in 10,000 · 640 · $212,400
  - `0x88c1…04aa` · about 1 time in 2,500 · 418 · $96,050
  - `0x3f07…b21c` · about 1 time in 1,100 · 305 · $58,900
  - `0xd4e9…7713` · about 1 time in 600 · 1,020 · $141,300
  - `0x5b60…c8e2` · about 1 time in 350 · 188 · $22,750
  - `0x9a12…3d4f` · about 1 time in 210 · 256 · $31,480
  - `0x0c7e…e690` · about 1 time in 130 · 97 · $12,020
- Clicking a wallet would open its Verdict page (just make it a link).

## Page 3: Scans (use this content)

- Section "Find wallets to follow" active.
- A "New Scan" form: Cut-off Date (date field), Number of Wallets (number field, default 200), primary button "Start Scan". Since Offline Mode is on, the date is fixed to 1 June 2026, with a short note saying so.
- A running Scan: progress bar with the text "84 of 200 Wallets checked".
- A list of earlier Scans, newest first, with columns Run date, Cut-off Date, Wallets, Watchlist, Status:
  - 14 Oct 2026 · 1 June 2026 · 200 · 7 · Finished (link "Open Watchlist")
  - 12 Oct 2026 · 1 May 2026 · 200 · — · Interrupted at 120 of 200 (button "Resume")
  - 10 Oct 2026 · 1 Apr 2026 · 100 · 0 · Finished ("No Wallet was rated Skilled (high confidence)", stated plainly, not as an error)

## The 4 versions

Make each version clearly different in layout, for example:
- **A. Classic report**: one column, cards stacked top to bottom, generous spacing.
- **B. Dense dashboard**: tighter spacing, Verdict card and chart side by side on wide screens.
- **C. Document style**: no card boxes, sections divided by rules and headings, like a printed report.
- **D. Your own idea**, still within every fixed rule above.

## Output format

- **One self-contained HTML file per version** (4 files), each containing all three pages one below another, each page introduced by a small grey label like "Page 1: Verdict page".
- Inline CSS only, inline SVG for the chart, no JavaScript needed, no external links, images, fonts or CDNs: it must open offline by double-clicking.
- Use the exact texts given above; do not invent extra features, buttons or claims.
- After the files, write 2–3 lines per version on what it does well and what it does badly.
