---
name: LiquidOracle
status: final
created: 2026-10-16
updated: 2026-10-21
sources:
  - _bmad-output/planning-artifacts/prds/prd-LiquidOracle-2026-10-12/prd.md
---

# LiquidOracle: Experience Spine

How the app works: pages, navigation, states, wording and accessibility. How it looks is in `DESIGN.md`. Terms (Wallet, Verdict, Real PnL, Cut-off Date …) are used as defined in PRD §3; the few on-screen words that differ are mapped in *Voice and Tone*. Component names are the same as in `DESIGN.md` › Components. Stage marks: **S1**, **S2**, **S3** = stage 1, 2, 3 (PRD §6.1). Each stage must work on its own, so a page or element marked S2 or S3 is simply absent until that stage is built.

## Foundation

- **Form factor:** a web page in the browser on the user's or examiner's own laptop, served by the app running locally (PRD §8). Laptop screen first; pages must still work in a narrow window.
- **UI system:** none chosen yet. The frontend technology is decided in `bmad-architecture`; this spine is tech-neutral.
- **Visual identity:** `DESIGN.md`. Built references: [`mockups/verdict.html`](mockups/verdict.html) (Verdict page, both themes, interactive chart), [`mockups/lookup.html`](mockups/lookup.html) (Lookup page with the Sample Wallets list and its states) and [`mockups/logo-and-tab.html`](mockups/logo-and-tab.html) (logo, tab titles, Scan progress in the tab). The Scan pages follow `imports/round-2-images/watchlist-light.webp` and the tables below. Both spines win over any mock, prototype or image.
- **Theme:** light and dark. The app starts on the system setting; the theme toggle switches theme and the choice is remembered in that browser (Edvard, 2026-10-16).
- **Accessibility target:** WCAG 2.1 AA (decided 2026-10-16). WCAG is the standard checklist for accessible web pages; AA is the normal level. See *Accessibility Floor*.
- **Modes:** Offline Mode (FR-14) and Mock LLM Mode (FR-15, S3) are set when the app starts, not switched inside the app: a start-command flag (`--offline`, `--mock-llm`) or the same setting in `.env` (architecture, 2026-10-21). Offline Mode never calls the language model, even with a key set, and never shows data from online runs.

## Information Architecture

The top bar is on every page: the logo and name **LiquidOracle** (goes to *Check a wallet*), the two section links, and on the right the theme toggle and, when that mode is on, the Offline pill.

| Section | Surface | Stage | Reached from | Purpose | PRD |
|---|---|---|---|---|---|
| Check a wallet | **Lookup** (start page) | S1 | App open; top bar; the logo and name | Enter a Wallet address. In Offline Mode, also the Sample Wallets list | FR-1, FR-12, FR-14, UJ-3 |
| Check a wallet | **Verdict page** | S1 | Lookup; a Sample Wallets item; a Watchlist row; a Copy Test row | Verdict card, chart card, honesty notes card; S3 adds Flag, Explanation, Domain table | FR-2, FR-8 to FR-11, FR-21 to FR-23 |
| Scan wallets | **Scans** | S2 | Top bar | Start a Scan (Cut-off Date, size); see earlier Scans; follow progress; resume a stopped Scan | FR-16 |
| Scan wallets | **Watchlist** (one per Scan) | S2 | A finished Scan in the Scan list | Wallets rated *Skilled (high confidence)*, sorted by p-value, with the Minimum Luck Passes note | FR-16 |
| Scan wallets | **Hold-up Test** (one per Scan) | S2 | Scan tabs | Before-Cut-off Passers vs Comparison Group on the after part | FR-17 |
| Scan wallets | **Copy Test** (one per Scan) | S2 | Scan tabs | Random Group Check, then per-Wallet Follower PnL and Follower Return | FR-18 |
| — | **Page not found** | S1 | A mistyped or old address | "Page not found", with a link to *Check a wallet* | — |

The second section is called **Scan wallets** (Edvard, 2026-10-16, after the wording review): "Find wallets to follow" read as advice, and the PRD forbids trade signals (§2.2, §5).

**Scan pages (S2).** Watchlist, Hold-up Test and Copy Test belong to one finished Scan. They share the Scan header (eyebrow "Wallet scan", title "Scan of 200 Wallets", lede "Cut-off Date 1 June 2026 · run 14 Oct 2026", a second lede line stating the population tested: "Markets resolved in the 90 days before the Cut-off Date, top 100 by volume · 97 of 100 Markets used · Seed 44", and the Scan summary card) and the Scan tabs: *Watchlist* · *Hold-up Test* · *Copy Test*. The tabs are ordinary links, each to its own page.

**Links between sections.** Clicking a Wallet on the Watchlist or on the Copy Test's per-Wallet table opens its Verdict page inside the app (Edvard's addition). These links get no external-link icon, since they don't leave the app (Edvard, 2026-10-16). The Verdict page then shows a back link to where the user came from: "← Back to Watchlist (Cut-off Date 1 Jun 2026)" or "← Back to Copy Test (Cut-off Date 1 Jun 2026)".

**Addresses in the URL.** Every surface has its own address in the browser (for example `/wallet/0x…`, `/scans/3/hold-up`), so the browser's back button, bookmarks and opening in a new tab all work. A bad or unknown address (`/wallet/abc`, a Scan that does not exist) shows *Page not found*.

No modals, no settings page, no login (PRD §5).

## Voice and Tone

Plain, exact, unexcited: the voice of a lab report written for a non-statistician. The app describes past evidence; it never advises.

| Do | Don't |
|---|---|
| "a trader with no edge would do this well about 1 time in 300" | "99.7% skilled!" |
| "*No evidence of skill*" | "Bad trader", "Loser", "Avoid" |
| "12 resolved bets; at least 30 are needed for a Verdict (18 more)" | "Insufficient sample size (n<30)" |
| "No Polymarket history found for this address" | "Error 404" |
| "Polymarket did not answer. Showing stored data from 15 Oct, 14:02." | "Something went wrong :(" |
| "7 Wallets rated *Skilled (high confidence)*" | "7 winners to copy" |
| State limits next to the claim they limit | Bury limits in a footer or a tooltip |

**On-screen words for glossary terms.** The screens use two everyday words for PRD terms, always with the same meaning:
- a **replay** is a Simulation (PRD §3). Where the PRD fixes the wording, the PRD word stays: the FR-9 marker label says "above all 10,000 Simulations". "About this chart" says it once: "Each replay (a Simulation) …".
- a **bet** is a Position, and a **resolved bet** is a Resolved Position. Every table header and card uses "Resolved bets"; the after part reads "640 resolved bets after the Cut-off Date".

Glossary terms are capitalised on screen as in the PRD's own texts: Wallet, Verdict, Real PnL, Exit PnL, Simulation, Scan, Watchlist, Cut-off Date ("This Wallet made $40,180 …").

**Banned words** about a Wallet anywhere in the app, including Explanations (PRD §8, FR-24): "guaranteed", "insider", "will win". **Also avoided** about a Wallet: "copy this", "follow", "recommended", "winner", "best", "top" (except in the factual Scan definition "top Wallets by profit"), "safe", "proven", "sure thing", "beat the market", "genius", "smart money". The PRD's test names (Copy Test, Follower PnL, Follower Return) are allowed.

**Number and phrase rules** (repeated from the PRD because they are what the user reads):
- The odds phrase follows FR-8 exactly: "about 1 time in N" (N to 2 significant figures), "fewer than 1 time in 10,000", "more than half the time".
- Money: `$12,340` and `−$1,240` (real minus sign), no colour for sign. Follower Return as a percentage with one decimal: `+4.2%`, `−1.8%`.
- Counts in words and digits together where they matter: "48 of 60 positions held to resolution".
- Copy p-value (FR-18): "random groups did as well in X% of draws", with X to one decimal under 10% and whole above ("0.4%", "23%"). When no random group scored as well: "no random group did as well in 10,000 draws" (FR-18, added 2026-10-16).
- Minimum Luck Passes for a Scan of n Wallets: "At least about {n × 0.01} of {n} would pass by luck alone, probably more, because these Wallets were picked for high profit." The number is rounded to one decimal under 2 ("0.5 of 50", "1.5 of 150") and whole from 2 up ("2 of 200").
- Share of the Real PnL from the largest bet (FR-11): "70% of the Real PnL came from the single largest bet." If the Real PnL is $0 or below, show the amount instead: "Largest single bet: $3,200". If the share is over 100%: "More than all of the Real PnL came from the single largest bet ($52,000); the other bets lost money overall."

## Component Patterns

Behaviour only; visuals are in `DESIGN.md` › Components, under the same names. Components with no behaviour beyond what is listed under *State Patterns* (Warning box, Info box, Info tag, Error message, Logo) are not repeated here.

| Component | Stage | Where | Behaviour |
|---|---|---|---|
| Address field | S1 | Lookup | The visible label is "Wallet address". Enter or "Check wallet" submits. Leading and trailing spaces are removed. An empty or wrong-format address shows an error under the field and fetches nothing (FR-1); focus stays in the field. A valid address opens its Verdict page (`/wallet/0x…`), which does the fetching. |
| Sample Wallets list | S1 | Lookup, Offline Mode only | The Sample Dataset's Wallets in two groups, *Real Wallets* (shortened addresses) and *Synthetic Wallets* (names such as "Sharp trader", tagged "synthetic"). One click opens the Verdict page. |
| Offline pill | S1 | Top bar, every page | Visible whenever Offline Mode is on. Text, not icon only. Not interactive. |
| Theme toggle | S1 | Top bar, every page | One button named "Dark theme", pressed or not pressed. First visit: follows the system setting. A click switches at once and stores the choice in the browser; later visits use the stored choice. If storage is blocked, it still switches for the current page. |
| Verdict card | S1 | Verdict page | The whole top block (layout in `DESIGN.md` › Layout & Spacing): eyebrow "Wallet analysis", the Verdict hero as the page's main heading, the odds phrase, the Flag (S3), the address card, the stats line, and the Exit PnL warning beside the stats when Exit PnL < 0 (FR-11). |
| Verdict hero | S1 | Verdict card | Dots + Verdict text; the dots are hidden from screen readers, the heading is read as "Verdict: No evidence of skill". |
| Verdict pill | S2, S3 | Tables, Hold-up group cards | Dots + Verdict text, the same rule. |
| Copy address | S1 | Address card | Copies the full address. On success the button shows "Copied" for 2 seconds and a status line (outside the button) announces "Address copied". If the browser refuses, an error appears under the card: "Copy failed. Select the address and press Ctrl+C." (⌘C on a Mac), it is announced, and the address text is selected for the user. |
| Luck chart | S1 | Chart card | Histogram of the Luck Distribution with the Real PnL marker (FR-9). It is centred where luck alone lands on average ($0, since each bet is replayed at its own price), so the user sees how much of the curve lies at or beyond the marker; that share is the evidence. The axis always includes the Real PnL. Beyond every Simulation, the marker label says "above all 10,000 Simulations" (or "below …"). The first and last bars hold everything beyond the axis and are labelled "−$195,000 or less" and "$195,000 or more". Not shown for *Not enough data* (FR-10). |
| Chart explore | S1 | Luck chart | Pointing at a bar shows the chart tooltip with its range and number of replays. The tooltip stays while the pointer moves onto it and for 300 ms after the pointer leaves, and Esc hides it (WCAG 1.4.13); next to the marker it moves aside so it never covers the marker's dot or label. By keyboard the bars are one *slider* named "Replays by result": Left/Right step one bar, Page Up/Down step ten, Home/End jump to the ends; a screen reader reads each step ("$30,000 to $35,000: 289 replays"). Extra detail only: everything the user needs is also in the text under the chart. (Edvard, 2026-10-16) |
| Wallet marker | S1 | Luck chart | A button on the blue line, described by the sentence "2,500 of 10,000 replays did this well or better". Pointing at it or focusing it highlights every bar from the wallet's bar rightwards and shows the chart tail label; the marker and the label are one hover area, so moving onto the label keeps it. Click or Enter pins the highlight (for touch screens too) and announces "Highlight on"; a second click, Esc, or moving the slider unpins it and announces "Highlight off". The number is the exact count of Simulations with PnL at or above the Real PnL, the same count the p-value uses (FR-5), never rounded and never summed from the bars (the wallet's bar is only partly above its result). If no Simulation reached it, no bars light up and the sentence reads "No replay did this well or better"; if every Simulation did, all bars light up and it reads "All 10,000 replays did this well or better". (Edvard, 2026-10-16) |
| Chart build-up | S1 | Luck chart | The first time the chart scrolls into view: bars grow into the curve, then the marker drops in, under a second in all. Skipped entirely with *reduce motion*, and the chart is complete without JavaScript. |
| About this chart | S1 | Chart card, top right | A disclosure (opens in place, no pop-up), closed by default, with three plain sentences: what one replay is, what the bars count, what the blue line labelled "This Wallet" is ("this Wallet's Real PnL: what it made on the 212 bets it held to resolution"), and that the numbers show by pointing or with the arrow keys. |
| Chart text alternative | S1 | Under the luck chart | Always visible: "This Wallet made $40,180 on 212 resolved bets. In 10,000 replays with no edge, a result this good came up about 1 time in 4." States the Real PnL and the FR-8 odds phrase (PRD §8). |
| Honesty notes card | S1 | Verdict page | "What this test can't see", in three columns: the share of the Real PnL from the largest bet (with the edge cases in *Voice and Tone*); "N of M positions held to resolution" and "Shares sold before resolution: −$3,150 (Exit PnL)"; the fixed limits note; "This is not financial advice." Always shown, never collapsed (FR-11). Under the three columns, a "Left out of the test" line with a count per reason (sold before resolution, split or merged, not explained by the activity, Polymarket's two lists disagree, unclear resolution, not fully read), the fees not counted with their recorded total, and, when they apply, the plain sentences of FR-11: more than 10% left out ("Only part of this Wallet's activity was judged: 31% of its bets were left out."), linked bets the app could not detect, and the window line ("Based on the latest 2,000 of 8,412 bets"). Last, in small text, the set and Seed the result was computed on: "Computed on the latest 2,000 bets · Seed 44" (architecture, 2026-10-21). |
| Back link | S1, S2 | Verdict page | Shown only when the page was opened from a Watchlist or a Copy Test: "← Back to Watchlist (Cut-off Date …)" or "← Back to Copy Test (Cut-off Date …)". It returns to that page. |
| Flag | S3 | Verdict card, under the odds phrase | "⚠ Likely market maker (heuristic, may be wrong)". Never changes the Verdict (FR-22). |
| Explanation | S3 | Directly under the Verdict card | At most 60 words (FR-23). Whenever template text is shown (Mock LLM Mode, or a replacement under FR-24), it carries the info tag "Template text". |
| Domain table | S3 | Verdict page, after the honesty notes card | One row per Domain: Domain, Resolved bets, Domain Verdict (Verdict pill) (FR-21). Note under it: "Each Domain's odds are adjusted for testing several Domains." (FR-20). An info tag above the table names where the Domain labels came from: "Labels: Claude Haiku 5.5" or "Labels: keyword rules" (FR-15, FR-19; architecture, 2026-10-21). |
| New Scan form | S2 | Scans | Cut-off Date (date field) and Number of Wallets (number field, default 200), button "Start Scan". Rules in *State Patterns*. In Offline Mode the date is fixed to the Sample Dataset's default Cut-off Date and the number is the whole Sample Dataset, both read-only, with an info box saying so. |
| Scan list | S2 | Scans | Earlier Scans, newest first: run date, Cut-off Date, Wallets, Watchlist size, status. A finished Scan links to its Watchlist. A stopped Scan has a button named "Resume Scan (Cut-off Date 1 May 2026)". A failed Scan (an unexpected error) shows "Failed" and no Resume button; so does a Scan whose stored data was rebuilt ("Data rebuilt, cannot resume"). Results of a Scan that has not finished are not shown. |
| Scan progress bar | S2 | Scans | A progress bar whose text names the current step: "Reading Markets: 34 of 100", "Fetching Wallets: 84 of 600", "Ranking", "Hold-up Test", "Copy Test: 1,200 of 18,000 prices", updated as the Scan runs (architecture, 2026-10-21: the Scan runs these steps in order). The user may leave the page; the Scan keeps running while the app runs, and the Scan list shows it as running. |
| Scan progress in the tab | S2 | Browser tab | While a Scan runs, the Scans page's tab title counts Wallets ("84/200 · Scan · LiquidOracle") and the favicon's ring fills clockwise from the top (Edvard, 2026-10-16). When the Scan finishes or stops, both go back to normal. Other pages keep their normal title. Screen readers get progress from the page, not from the tab. |
| Watchlist table | S2 | Watchlist | Data table titled "Wallets rated Skilled (high confidence)". Columns: Wallet (in-app link), Verdict (pill), Odds (with no edge), Resolved bets, Real PnL. No rank column (Edvard, 2026-10-16). A Wallet whose history could not be read in full carries the info tag "Not fully read" in its Wallet cell, here and in every table it appears in (Edvard, 2026-10-21). Caption: "Sorted by p-value, smallest first. A smaller p-value means stronger evidence of skill, not a bigger edge." (FR-16). Above it, in an info box, the Minimum Luck Passes sentence. |
| Hold-up group cards | S2 | Hold-up Test | *Before-Cut-off Passers* and *Comparison Group*. Each shows the Verdict on the after part, the odds phrase, resolved bets counted, Real PnL, Wallets in the group, Wallets dropped for too few bets after the Cut-off Date, and Wallets not fully read (FR-17). Under the cards: "Each Wallet's bets after the Cut-off Date are capped at its first 2,000. Bets in the same Market are simulated together, not as separate evidence."  The dropped-Wallets warning appears above both cards when triggered. |
| Copy Test layout | S2 | Copy Test | Top: the Random Group Check at the Main Copy Delay (5 min): Copy Verdict pill and the Copy p-value phrase. Below: the per-Wallet table with Follower PnL and Follower Return at 1, 5 and 30 min next to the Wallet's own Real PnL. Caption above it: "These per-Wallet numbers are not luck-checked. Only the Random Group Check above is." The 1- and 30-min columns carry the info tag "Extra information" (FR-18). Under the table: positions left out per delay, and "Follower PnL ignores the spread and the follower's own price impact, so it is an upper bound." Under the Random Group Check: "N of the Passers' Markets are shared by two or more Passers." and how many Pool Wallets are not fully read (FR-18; architecture, 2026-10-21). |
| Scan tabs | S2 | Scan pages | Links in a navigation region named "Scan"; the current one is marked as the current page. Not an ARIA tab list. |

## State Patterns

| State | Surface | Treatment | PRD |
|---|---|---|---|
| Empty address | Lookup | Error under the field: "Enter a wallet address." | FR-1 |
| Wrong address format | Lookup | Error under the field: "This is not a valid wallet address. It should start with 0x and have 42 characters." Nothing is fetched. | FR-1 |
| Not available offline | Lookup (or Verdict page if opened directly) | "Not available offline. In Offline Mode only the Sample Wallets below can be checked." | FR-14 |
| Fetching | Verdict page | In place of the Verdict card: the heading "Checking 0x7c3a…d3f5", the fetching indicator and "Fetching trades from Polymarket…". The page title already names the Wallet. When the Verdict arrives, it replaces this block and focus moves to the Verdict heading. | FR-2 |
| Stored data used | Verdict page | Normal page; the "Data stored …" line shows when the data is from. | FR-2 |
| No Polymarket history | Verdict page | Heading "No Polymarket history found", the sentence "No Polymarket history found for this address.", and a link back to *Check a wallet*. No card, no chart. | FR-1, UJ-1 |
| Polymarket not answering | Verdict page | Heading "Polymarket did not answer". If stored data exists for this same view (the same set of bets): button "Show stored data from 15 Oct, 14:02". If not: "Try again in a few minutes." Stored data for a different view, such as a Scan's window, is never offered here (architecture, 2026-10-21). | FR-2 |
| *Not enough data* | Verdict page | Dashed Verdict hero; "12 resolved bets; at least 30 are needed for a Verdict (18 more)"; no odds phrase, no chart. Honesty notes still shown. | FR-10, UJ-2 |
| Exit PnL below zero | Verdict card | Warning box beside the stats: "Positions this Wallet sold before resolution lost money in total. This Verdict covers only bets held to resolution." | FR-11 |
| p-value above 0.5 | Verdict page | Odds phrase "more than half the time". | FR-8 |
| Real PnL beyond all Simulations | Luck chart | Axis stretched to include it; marker label "above all 10,000 Simulations" (or "below"); the wallet marker behaves as in *Component Patterns*. | FR-9 |
| Page not found | Any bad address | Heading "Page not found" and a link to *Check a wallet*. | — |
| No Scans yet | Scans | "No Scans yet. A Scan checks the top Wallets by profit made before a date you choose." and the form. | FR-16 |
| Cut-off Date missing | New Scan form | Error: "Choose a Cut-off Date." Nothing starts. | FR-16 |
| Cut-off Date today or later | New Scan form | Error: "The Cut-off Date must be in the past." Nothing starts. | FR-16 |
| No bets after the Cut-off Date | New Scan form | Warning before starting: "Very few bets were resolved after this date, so the Hold-up Test and Copy Test may have too little to test." The user can still start. | FR-17 |
| Number of Wallets out of range | New Scan form | Error: "Enter a whole number from 10 to 500." Nothing starts. `[ASSUMPTION: 10 to 500 is the AI's guess; revisit after the data spike]` | FR-16 |
| A Scan is already running | Scans | The form shows "A Scan is running (84 of 200). You can start a new one when it finishes." in an info box, and "Start Scan" is unavailable. | FR-16 |
| Scan stopped | Scans | If the app was closed mid-Scan: "Interrupted at 120 of 200". If Polymarket stopped answering: "Stopped at 120 of 200: Polymarket did not answer". Both get a Resume button; finished Wallets are not fetched again. | FR-16 |
| Market not used | Scan header | A Market whose list could not be read in full counts against "N of 100 Markets used"; a details disclosure under the lede lists those Markets as "not used: partial". | FR-16 |
| Wallet not fully read | Every table and group card that counts the Wallet | The info tag "Not fully read", with the tooltip "Polymarket's data for this Wallet could not be read in full; the unread bets are left out." | FR-16 |
| Empty Watchlist | Watchlist | "No Wallet in this Scan was rated *Skilled (high confidence)*." A valid result, stated plainly, not as an error (SM-C2). | FR-16 |
| No Before-Cut-off Passers | Hold-up Test, Copy Test | "No Wallet passed on its bets before the Cut-off Date, so the Hold-up Test and Copy Test have nothing to test." | FR-17, FR-18 |
| Empty Comparison Group | Hold-up Test | That card says "No Wallets in this group: every scanned Wallet passed or had *Not enough data* before the Cut-off Date." | FR-17 |
| Group too small | Hold-up Test | That group's card shows *Not enough data* with its count of resolved bets after the Cut-off Date. | FR-17 |
| Dropped share differs by > 20 pp | Hold-up Test | Warning box with the FR-17 text above the two group cards. | FR-17 |
| Copy Verdict *Not enough data* | Copy Test | With the reason: "No Passer has enough priced bets after the Cut-off Date." or "Only 20 possible groups; at least 1,000 are needed." The per-Wallet table is still shown. | FR-18 |
| Positions with no recorded price | Copy Test | Under the table: "3 positions left out at 5 min, 1 at 30 min: no recorded price." | FR-18 |
| Domain under 30 bets | Domain table | Row shows *Not enough data*. | FR-20 |
| Language model not answering (key set) | Verdict page | The Explanation falls back to the template with its "Template text" tag; the Domain table is replaced by "Domains are not available: the language model did not answer." | FR-15, FR-24 |
| Mock LLM Mode | Explanation | "Template text" info tag. | FR-15 |

## Interaction Primitives

- **Mouse and keyboard equally.** Everything clickable is a real link or button, reachable with Tab and activated with Enter (and Space for buttons).
- **Feedback on everything clickable, nothing else** (Edvard, 2026-10-16). Links, buttons, clickable table rows, Sample Wallets items, the chart bars and the wallet marker react to hover; cards, numbers and text never do. Keyboard focus gives the same feedback as hover, plus the focus ring. Visual specs: `DESIGN.md` › Interaction states.
- **Quick and calm.** Feedback within 120 ms; the chart build-up under a second, once per view. With *reduce motion* set in the system, nothing moves; colour feedback stays.
- **Whole-row click** on Watchlist and Copy Test rows, but the Wallet address inside the row is the actual link, so keyboard and screen-reader users get one stop per row.
- **Browser back** always works (each surface has its own URL).
- **Long work never freezes the page.** Lookups show the fetching state; Scans show progress and can be left running. Buttons are never disabled in a way that drops keyboard focus; an unavailable button stays focusable and says why.
- **Banned:** modals and pop-ups, hover-only information (a hover label may add detail, never hold something the user needs that is not also on the page, and must also work by keyboard), auto-playing animation, infinite scroll, sound, any button that sends anything to Polymarket or anywhere else (the app is read-only, PRD §5).

## Accessibility Floor

Target: **WCAG 2.1 AA**, the level commonly required for public websites in Norway (Edvard to confirm the exact rule before citing it). The app runs locally, so this is a chosen standard, not a legal duty. Visual contrast is handled in `DESIGN.md` › Colors (ratio table).

- **Verdict never by colour alone** (PRD §8): the Verdict is always text; dots and tint are extras. Dots are hidden from screen readers.
- **Chart text alternative** (PRD §8): visible under the luck chart, stating the Real PnL and the FR-8 odds phrase. The bars and axes are hidden from screen readers; the text alternative says it once.
- **Chart exploring by keyboard:** the bars are a slider with a spoken value per bar; the wallet marker is a button described by its sentence, with "Highlight on" / "Highlight off" announced on pin and unpin. Focus rings and tooltips never cover the marker's label. Hover labels follow WCAG 1.4.13: they can be dismissed (Esc), hovered and stay put.
- **Verdict heading:** the page's main heading is the Verdict itself, read as "Verdict: No evidence of skill". Every error or empty state has its own main heading ("No Polymarket history found", "Page not found").
- **Page changes:** every page change, including one made by the frontend without a full reload, updates the tab title and moves focus to the main heading.
- **Theme toggle:** a toggle button named "Dark theme" with a pressed state; both themes meet the same contrast rules.
- **Keyboard:** every action works without a mouse; Tab order follows reading order; the focus ring (`DESIGN.md` › `focus-ring`) on every focusable element; "Skip to content" as the first Tab stop.
- **Page titles** (the browser tab), one per surface, page name first so tabs are easy to tell apart (Edvard, 2026-10-16):

  | Surface | Tab title |
  |---|---|
  | Lookup | Check a wallet · LiquidOracle |
  | Verdict page | Verdict · 0x7c3a…d3f5 · LiquidOracle |
  | Scans | Scans · LiquidOracle |
  | Scans, while a Scan runs | 84/200 · Scan · LiquidOracle |
  | Watchlist | Watchlist · 1 Jun 2026 · LiquidOracle |
  | Hold-up Test | Hold-up Test · 1 Jun 2026 · LiquidOracle |
  | Copy Test | Copy Test · 1 Jun 2026 · LiquidOracle |
  | Page not found | Page not found · LiquidOracle |

  The short address and the Cut-off Date tell two open tabs of the same page apart.
- **Headings** in order: one main heading, then section titles (Simulated results, What this test can't see, Domains …), so screen-reader users can jump by heading.
- **Forms:** every field has a visible label tied to it; an error sentence sits under its field, is tied to the field as its description, marks the field invalid, and is read with a hidden "Error:" in front; the ✕ icon is hidden. On submit with errors, focus moves to the first field in error. Buttons that repeat in a list get unique names ("Resume Scan (Cut-off Date 1 May 2026)").
- **Warnings** are read with a hidden "Warning:" in front; the ⚠ icon is hidden.
- **Live updates:** polite announcements only. Scan progress at most every 10% and once when finished, not on every Wallet. The fetching state and "Address copied" / "Copy failed …" are announced. The Scan progress bar is a real progress bar whose value is read as "84 of 200 Wallets checked".
- **Tables:** real header cells; sort order stated in the caption. A table that can scroll sideways sits in a focusable, named scroll area, so it can be scrolled by keyboard.
- **Zoom and reflow:** usable at 200% zoom and in a 320 px wide window without sideways page scrolling (wide tables scroll inside their card).
- **Motion:** with *reduce motion* on, there is no fetching animation, no button lift, no chart build-up and no marker drop. The chart is shown complete.
- **Windows High Contrast:** the chart bars, evidence dots and progress fill stay visible in system colours (`DESIGN.md` › Colors).
- **Language:** the page declares English.

## Responsive & Platform

Breakpoints are the three in `DESIGN.md` (`bp-stack` 900 px, `bp-phone` 640 px, `bp-small` 400 px).

| Width | Behaviour |
|---|---|
| ≥ 900 px (laptop) | Main layout. The Verdict card in two columns; Hold-up group cards side by side; honesty notes in three columns. |
| 640–899 px | Two-column parts stack: the address card under the Verdict hero, the warning under the stats, the honesty notes in one column. Tables still fit. |
| 400–639 px | Phone sizes: smaller Verdict and titles, short chart axis labels, the "Check wallet" button under the field; tables scroll sideways inside their card; the top bar's tools move to their own row. |
| < 400 px | Smallest Verdict size; the chart's end labels are hidden. |

No phone-specific design: the user is at a laptop (UJ-1, UJ-3), but nothing breaks on a narrow window.

## Inspiration & Anti-patterns

- **Lifted from statistical reports:** the answer first, then the evidence, then the limits, each in its own block.
- **Lifted from good chart practice:** every chart says its finding in a sentence beside it, so the chart supports the text rather than replacing it.
- **Rejected: leaderboards** (PRD §2.2). The Watchlist is private, only lists Wallets that passed a test, is sorted by evidence, and has no rank numbers.
- **Rejected: check marks, thumbs up and trophies** for Verdicts (Edvard, 2026-10-16): they read as "go copy this wallet". Replaced by evidence dots.
- **Rejected: green/red trading colours.** Profit and loss are numbers with a sign, not colours.
- **Rejected: "Copy" or "Follow" buttons, alerts, notifications** (PRD §5), and advice-like labels such as "Find wallets to follow".

## Key Flows

Names and numbers mirror the PRD's user journeys.

### Flow 1: Jonas checks a wallet before copying it (UJ-1, S1)

Jonas saw a wallet with $40k profit recommended on X. He is at his laptop in the evening.

1. He opens LiquidOracle. The *Check a wallet* page shows the address field with focus already in it.
2. He pastes the address and presses Enter.
3. The Verdict page opens with "Checking 0x7c3a…d3f5" and "Fetching trades from Polymarket…" for a few seconds.
4. The Verdict card appears: `○○○` *No evidence of skill*; under it: "a trader with no edge would do this well about 1 time in 4"; 212 resolved bets; Real PnL $40,180.
5. The luck chart shows the marker well inside the bars; the sentence under it says the same in words.
6. **Climax:** In "What this test can't see" he reads "70% of the Real PnL came from the single largest bet." Most of the $40k rests on one bet, and the test finds no evidence of skill. He decides not to copy the wallet.

Edge: the address has never traded on Polymarket. The page says "No Polymarket history found for this address" instead of an empty Verdict.

### Flow 2: Jonas looks up a new wallet with few bets (UJ-2, S1)

1. Jonas pastes another address.
2. The Verdict page shows the dashed *Not enough data* hero: "12 resolved bets; at least 30 are needed for a Verdict (18 more)".
3. **Climax:** No chart, no odds, no false precision. He knows the honest answer is "too early to tell" and comes back later.

### Flow 3: The examiner runs the app offline (UJ-3, S1)

1. The examiner follows the README, starts the app in Offline Mode, and opens the page in a browser.
2. The top bar shows "Offline Mode · sample data only" on every page.
3. Under the address field is the Sample Wallets list. They click "Sharp trader" (tagged synthetic).
4. The Verdict page shows `●●●` *Skilled (high confidence)*; with the Sample Dataset's fixed Seed the odds read "fewer than 1 time in 10,000" and the marker is labelled "above all 10,000 Simulations".
5. They go back and pick a coin-flipper Wallet that the tests expect not to pass: `○○○` *No evidence of skill*.
6. They paste an address not in the sample: "Not available offline …".
7. **Climax:** The Verdicts match what the tests expect, with no network and no keys. Then they run the test suite from the README and it passes.

### Flow 4: Jonas looks for wallets worth following (UJ-4, S2)

1. Jonas clicks *Scan wallets*. The Scans page shows the form and his earlier Scans.
2. He sets the Cut-off Date to 1 June, leaves 200 Wallets, and clicks "Start Scan".
3. The progress bar fills: "84 of 200 Wallets checked". He closes the app by mistake; when he starts it again the Scan shows "Interrupted at 84 of 200", and he clicks "Resume". It continues from 84.
4. The Watchlist opens: 7 Wallets rated *Skilled (high confidence)*, under the note "At least about 2 of 200 would pass by luck alone, probably more …".
5. He opens *Hold-up Test*: the Passers card reads *Skilled (high confidence)* on 640 resolved bets after the Cut-off Date; the Comparison Group card reads *No evidence of skill*.
6. He opens *Copy Test*: *Beat random picks*, "random groups did as well in 0.4% of draws". In the per-Wallet table, 5 Wallets keep a positive Follower PnL at 5 min; 2 drop to zero already at 1 min. The caption says these per-Wallet numbers are not luck-checked.
7. He clicks one of the 2 Wallets. Its Verdict page opens, with "← Back to Copy Test (Cut-off Date 1 Jun 2026)" at the top.
8. **Climax:** He returns and keeps only the 5 forecasters on his list, knowing which numbers were tested against luck and which were not.

### Flow 5: Jonas sees where the edge is (UJ-5, S3)

1. Jonas opens a Wallet with 352 resolved bets.
2. Directly under the Verdict card is a 45-word Explanation; further down, the Domain table: crypto *Skilled (high confidence)* on 180 bets, sports *No evidence of skill* on 150, politics *Not enough data* on 22.
3. **Climax:** He sees that the edge is only in crypto, so "skilled" is not one blended number.
4. On another Wallet, the warning "⚠ Likely market maker (heuristic, may be wrong)" sits under the odds phrase, and the Verdict is unchanged.

## Open Questions for UX

1. ~~The mechanism for setting Offline Mode and Mock LLM Mode at start~~ **Settled in architecture (2026-10-21):** a start-command flag or the same setting in `.env` (see *Modes* above).
2. The Sample Dataset's default Cut-off Date (used by the offline Scan): set after the data spike (PRD §9 Q6). Edvard picks it in the next session, with the 10 real Wallets (2026-10-21).
3. The Number of Wallets range (10 to 500) and the "very few bets after this date" threshold: revisit after the data spike, when fetch times and rate limits are known.
