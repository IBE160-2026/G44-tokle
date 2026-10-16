# Validation Report — LiquidOracle

- **DESIGN.md:** `_bmad-output/planning-artifacts/ux-designs/ux-LiquidOracle-2026-10-16/DESIGN.md`
- **EXPERIENCE.md:** `_bmad-output/planning-artifacts/ux-designs/ux-LiquidOracle-2026-10-16/EXPERIENCE.md`
- **Run at:** 2026-10-16 11:23

## Overall verdict

The spine pair rates **adequate** against the rubric, and both extra reviews pass with fixes. It is well traced to the PRD and the memlog: every token resolves, every colour pair that matters passes WCAG 2.1 AA in both themes (recomputed independently by two reviewers), and all five user journeys have flows with the PRD names word for word.
What holds it back is the contract between the two files and the parts not yet drawn: the Verdict block goes by five names; the Exit PnL warning, the Flag and the Explanation are placed differently in different sections; the stage-1 Lookup page has no visual spec; and the New Scan form has no bad-input states. The wording review adds one high finding: the section name “Find wallets to follow” reads as advice. The accessibility review finds no blockers; its medium items are in the chart's announcements and hover labels, a silent copy failure, and spec gaps for pages not mocked yet.
Totals across the three reviews: 0 critical, 5 high, 31 medium, 44 low. Several findings overlap between reviewers (Flag placement, back link from the Copy Test, replay vs Simulation, the tail-label number).

## Category verdicts

- Flow coverage — adequate
- Token completeness — adequate
- Component coverage — thin
- State coverage — adequate
- Visual reference coverage — adequate
- Bloat & overspecification — strong
- Inheritance discipline — adequate
- Shape fit — strong
- Accessibility review — good, no blockers
- Wording and honesty review — pass with fixes

## Findings by severity

### Critical (0)

### High (5)

**[Rubric: Component coverage]** The central component has five names.

The central component has five names. PRD FR-8 calls it the "Verdict card". EXPERIENCE uses "Verdict card" (IA, Explanation row, Flow 5), "Verdict header" and "Verdict badge". DESIGN uses "Verdict hero" and "Verdict pill" and never says "Verdict card". So "under the Verdict card" (FR-23 and the Explanation row) has nothing to resolve to (EXPERIENCE.md › IA Verdict page row; Component Patterns › Verdict badge, Verdict header, Explanation; DESIGN.md › Components › Verdict hero, Verdict pill).

Fix: fix the names once and use them everywhere. For example: **Verdict card** = the whole header block from FR-8 (hero + odds + stats + address card); **Verdict hero** = big dots and heading; **Verdict pill** = the small table version. Drop "badge" and "header".

**[Rubric: Component coverage]** The S1 start page has no visual spec.

The S1 start page has no visual spec. DESIGN › Layout & Spacing describes the Verdict and Scan pages only. Lookup has no layout, and the **Sample Dataset list** (S1, central to UJ-3 and to the examiner) has no DESIGN row. The **fetching indicator** ("moving dot pattern") and the **Skip to content** link also have none. No mockup or image covers Lookup (EXPERIENCE.md Open Question 3 admits it), so a builder has only the spines, and the spines don't cover it (DESIGN.md › Layout & Spacing; Components).

Fix: add a "Lookup page" paragraph to Layout, plus Components rows for the Sample Dataset list (item anatomy, "(synthetic)" label, the Offline-only heading), the fetching indicator and the skip link.

**[Rubric: State coverage]** The three PRD-required elements on the Verdict page are placed differently in different sections: Exit PnL warning: State Patterns says "right under the badge".

The three PRD-required elements on the Verdict page are placed differently in different sections: **Exit PnL warning:** State Patterns says "right under the badge". The Verdict header row says "beside" the stats. DESIGN says "to the right of the stats line … never inside the Verdict hero". **Flag:** the EXPERIENCE row says "beside the Verdict badge". The Verdict header row says "under" the odds phrase. DESIGN says "under the Verdict hero". **Explanation:** EXPERIENCE (and FR-23) say "under the Verdict card". DESIGN › Layout says the S3 additions "come after the chart card". (EXPERIENCE.md › State Patterns, Exit PnL row; Component Patterns › Verdict header, Flag, Explanation; DESIGN.md › Layout & Spacing; Components › Warning box, Flag.)

Fix: pick one place for each, write it once in DESIGN Layout, and make every other mention point there. See §7 for the PRD deviation.

**[Rubric: State coverage]** The New Scan form has no states for bad input: an empty, future or malformed Cut-off Date; a date so recent that no after part can exist; a Wallet count of 0, a negative number, a non-number or a very large number.

The New Scan form has no states for bad input: an empty, future or malformed Cut-off Date; a date so recent that no after part can exist; a Wallet count of 0, a negative number, a non-number or a very large number. The grading guide checks "stable on bad input", and the Lookup side is covered but this form is not (EXPERIENCE.md › State Patterns; Component Patterns › New Scan form).

Fix: add rows with error text, limits (min/max Wallets) and the "nothing starts" rule, mirroring the Lookup format error.

**[Wording]** The section name "Find wallets to follow" is an instruction.

The section name "Find wallets to follow" is an instruction. It tells the user the app's output is wallets they should follow, which is close to a trade signal (PRD §2.2 and §5: no trade signals, no copy-trading). It sits in the top bar on every page from stage 2, and it is already visible in the stage 1 mockup's top bar (`mockups/verdict.html` line 372), even though DESIGN.md says it is hidden until stage 2. It also clashes with the spec's own rule "Rejected: 'Copy' or 'Follow' buttons" (EXPERIENCE.md › Inspiration & Anti-patterns). The PRD job is a *question* ("find out whether following skilled wallets would actually have paid"; §4.5 title "Is Skill Worth Following?"), and a nav label should keep it a question or a neutral noun. (EXPERIENCE.md › Information Architecture, Flow 4 step 1; DESIGN.md › Top bar; verdict.html nav.)

Fix: rename the section **"Scan wallets"** (neutral, and it matches the glossary term Scan). Alternative: **"Is following worth it?"**. Update the IA table, Flow 4, DESIGN.md › Top bar and the mockup nav. Remove the link from the stage 1 mockup, or mark it "stage 2" there.

### Medium (31)

**[Rubric: Flow coverage]** Flow 4 step 7 opens a Verdict page from the Copy Test table, then shows "← Back to Watchlist".

Flow 4 step 7 opens a Verdict page from the **Copy Test** table, then shows "← Back to Watchlist". The Back link row says it is "only shown when the page was opened from a Watchlist", and the IA "Reached from" column for the Verdict page leaves out the Copy Test. A developer cannot tell what the back link does from the Copy Test (EXPERIENCE.md › Key Flows Flow 4 step 7; Component Patterns › Back link; IA table, Verdict page row).

Fix: define the back link per origin ("← Back to Copy Test (Cut-off Date …)"), add the Copy Test to "Reached from", and make step 7 match.

**[Rubric: Flow coverage]** FR-10 requires the page to show "how many more are needed".

FR-10 requires the page to show "how many more are needed". The drafted copy is "12 resolved bets; at least 30 are needed for a Verdict", followed by "(needs 18 more)" in parentheses. It is unclear whether "needs 18 more" is shown text or a reviewer note (EXPERIENCE.md › State Patterns, *Not enough data* row; Flow 2 step 2).

Fix: put the number in the string, e.g. "12 resolved bets; at least 30 are needed for a Verdict (18 more)".

**[Rubric: Token completeness]** Component tokens point only at the light names (`{colors.surface-raised}`, `{colors.accent}` …).

Component tokens point only at the light names (`{colors.surface-raised}`, `{colors.accent}` …). Nowhere does it say that in the dark theme each `{colors.x}` resolves to `x-dark`. Two entries break the pattern on their own ("(dark theme only)", "(light theme only)") (DESIGN.md frontmatter `components`; Colors).

Fix: add one rule: "In the dark theme every `{colors.x}` resolves to `{colors.x-dark}`; components list exceptions."

**[Rubric: Token completeness]** Several colours are described in words, with no token or hex: the primary button's hover "slightly deeper blue", the "grey 2 px underline" on nav hover, the outline of the Info tag, the Error message (it never names `{colors.error}`), the focus ring (accent, 2 px, "offset" with no value; there is no component entry), and the chart tail ("accent mixed 65% into surface-raised", with no hex).

Several colours are described in words, with no token or hex: the primary button's hover "slightly deeper blue", the "grey 2 px underline" on nav hover, the outline of the Info tag, the Error message (it never names `{colors.error}`), the focus ring (accent, 2 px, "offset" with no value; there is no component entry), and the chart tail ("accent mixed 65% into surface-raised", with no hex). The mockup's active bar has also drifted from the spec: memlog #53 says it was "softened from pure ink", but DESIGN still says "darkens to ink" (DESIGN.md › Components › Interaction states; Info tag; Error message; EXPERIENCE.md › Accessibility Floor › Keyboard).

Fix: add `accent-hover`(+dark), `focus-ring` (colour, width, offset) and `chart-tail` hex tokens, plus `error-message` and `info-tag` component entries, and pick one active-bar colour.

**[Rubric: Token completeness]** `spacing.content-max` is 1120px, but the mockup uses 1200px.

`spacing.content-max` is 1120px, but the mockup uses 1200px. Memlog #36 says the width was raised "to fit the Verdict on one line", and memlog #38 says "1120 to 1200 px". A builder who follows the token may get a wrapped Verdict (DESIGN.md frontmatter `spacing.content-max`; Layout & Spacing; `mockups/verdict.html` `.wrap max-width: 1200px`).

Fix: pick one value and log it.

**[Rubric: Token completeness]** There are no responsive type steps.

There are no responsive type steps. `verdict-display` (56px) and `page-title` (52px) have no smaller sizes, yet the spine promises a working 320px window. The mockup solves this on its own (40px under 640, 34px under 400) and also uses 12px text (offline pill, disclosure caret), which breaks the spine's own "No text below 13 px" rule (DESIGN.md › Typography; mockup `@media (max-width: 640px)`).

Fix: add `verdict-display-sm` / `page-title-sm` tokens with their breakpoint, and fix the 12px text in the mockup.

**[Rubric: Component coverage]** Other names differ between the files: Offline pill / Offline Mode indicator; Honesty card / Honesty notes (the PRD says notes); Copy Verdict pill / Copy Verdict badge; Text input + button / Address field + "Check wallet"; Progress bar / Scan progress; Page header with summary card / Scan sub-navigation; Data table / Watchlist table (DESIGN.md › Components; EXPERIENCE.md › Component Patterns, IA).

Other names differ between the files: Offline pill / Offline Mode indicator; Honesty card / Honesty notes (the PRD says notes); Copy Verdict pill / Copy Verdict badge; Text input + button / Address field + "Check wallet"; Progress bar / Scan progress; Page header with summary card / Scan sub-navigation; Data table / Watchlist table (DESIGN.md › Components; EXPERIENCE.md › Component Patterns, IA).

Fix: one name per component, the same in both files. Where a row is generic (Data table), say which instances use it (Watchlist table, Copy Test table, Domain table).

**[Rubric: Component coverage]** Several S2/S3 components have behaviour but no visual spec: the New Scan form (date field and number field; DESIGN only covers the address input), the Scan list (status display, Resume button), the Hold-up group cards (six figures each), the Explanation block (S3) and the Back link (EXPERIENCE.md › Component Patterns rows; DESIGN.md › Components has no match).

Several S2/S3 components have behaviour but no visual spec: the New Scan form (date field and number field; DESIGN only covers the address input), the Scan list (status display, Resume button), the Hold-up group cards (six figures each), the Explanation block (S3) and the Back link (EXPERIENCE.md › Component Patterns rows; DESIGN.md › Components has no match).

Fix: add short DESIGN rows. Most can reuse existing tokens (card, stat-figure, button-primary).

**[Rubric: Component coverage]** The Tabs have no behaviour row.

The Tabs have no behaviour row. The IA gives each tab its own URL (`/scans/3/hold-up`), which makes them links, but they look like tabs. The keyboard model (Tab between links, or arrow keys in an ARIA tablist) and the screen-reader role are undefined (DESIGN.md › Components › Tabs; EXPERIENCE.md › IA, Scan sub-navigation).

Fix: state "Tabs are links in a `nav` with `aria-current="page"`; no tablist" (or the other choice).

**[Rubric: State coverage]** Scan failure and running Scans are not defined.

Scan failure and running Scans are not defined. "Scan progress in the tab" mentions a Scan that "fails", but there is no failed state, and the difference between "interrupted" and "failed" is not given. Also missing: Polymarket stops answering mid-Scan; the user starts a second Scan while one is running; the user opens the Watchlist, Hold-up or Copy tab of a running or interrupted Scan (EXPERIENCE.md › Component Patterns › Scan progress in the tab, Scan list; State Patterns).

Fix: add rows for "Scan failed (Polymarket not answering)", "Scan already running" and "results of an unfinished Scan" (hidden, or partial with a note), and define what interrupts a Scan (the app stops).

**[Rubric: State coverage]** Deep links and cold loads are not covered, although every surface has its own URL (Interaction Primitives).

Deep links and cold loads are not covered, although every surface has its own URL (Interaction Primitives). Missing: `/wallet/<malformed>`, an unknown Scan id, and a bookmarked Verdict URL for a Wallet not stored yet (does the fetch run on the Verdict page?). "Polymarket not answering" and "No history" are placed on the Verdict page while "Fetching" is placed on Lookup, so where the user lands when a fetch fails is unclear (EXPERIENCE.md › IA › Addresses in the URL; State Patterns rows 2–4).

Fix: add a "Not found" state for bad URLs, and say which surface shows the fetch states when the page is opened directly.

**[Rubric: State coverage]** Edge cases of the wallet marker are missing, and its number source is loosely worded.

Edge cases of the wallet marker are missing, and its number source is loosely worded. When Real PnL is above all Simulations, the highlight would read "0 of 10,000 replays did this well or better", and it is not said whether the marker is still interactive. "The number comes from the p-value" invites p × 10,000, which gives 2,499.x for p = 0.25 because of the +1 terms in the formula (EXPERIENCE.md › Component Patterns › Wallet marker).

Fix: say the label uses the count of Simulations with PnL ≥ Real PnL that the Skill Test stores, and define the 0 and 10,000 cases (e.g. no highlight; the FR-9 label carries it).

**[Rubric: State coverage]** There is no format rule for the Copy p-value as a percent ("0.4% of draws"): how many decimals, and what happens at the floor (1/10,001 ≈ 0.01%).

There is no format rule for the Copy p-value as a percent ("0.4% of draws"): how many decimals, and what happens at the floor (1/10,001 ≈ 0.01%). FR-8 has such a rule for the odds phrase, and the spine copies it, but not this one (EXPERIENCE.md › Voice and Tone › Number and phrase rules, last bullet).

Fix: add e.g. "one significant figure below 1%; at the floor say 'in fewer than 0.01% of draws'", and log it in the PRD memlog if it changes FR-18.

**[Rubric: Visual reference coverage]** The spines disagree with each other on breakpoints, and the mockup follows a third set.

The spines disagree with each other on breakpoints, and the mockup follows a third set. DESIGN stacks the header and honesty columns "under 900 px" and everything "below 640 px". EXPERIENCE › Responsive uses ≥ 960 / 640–959 / < 640. The mockup uses 900 / 640 / 400. Since "spines win" only works when the spines agree, a builder cannot settle this (DESIGN.md › Layout & Spacing, Components › Honesty card; EXPERIENCE.md › Responsive & Platform; `mockups/verdict.html` media queries).

Fix: pick one breakpoint set, put it in DESIGN (as tokens if possible), and make EXPERIENCE refer to it.

**[Rubric: Inheritance discipline]** UI words and glossary terms are mixed with no stated mapping.

UI words and glossary terms are mixed with no stated mapping. The chart card says "10,000 replays with no edge", while the FR-9 marker label on the same chart must say "above all 10,000 Simulations". Stats and table columns say "resolved bets", while the Verdict header row says "Resolved Positions". A developer may "fix" one side to match the other (EXPERIENCE.md › Component Patterns › Luck chart, Verdict header, Watchlist table; DESIGN.md › Components › Chart card, Stats line).

Fix: add a short mapping in Voice and Tone: "UI says *replay* for Simulation and *resolved bet* for Resolved Position, except where the PRD fixes the wording (FR-9 label)". Or use "Simulations" in the chart title too.

**[Rubric: Inheritance discipline]** The PRD deviation is not logged.

The PRD deviation is not logged. FR-11 asks for the Exit PnL warning "next to the Verdict", and FR-22 asks for the Flag "beside the Verdict". DESIGN moves the warning to the stats row and the Flag under the hero. Memlog #30 records the chosen look but not that it moves a PRD-required element, and the PRD memlog has no entry (DESIGN.md › Components › Warning box, Flag; PRD FR-11, FR-22).

Fix: after settling the §4 placement, either keep both "next to the Verdict" or write the deviation and its reason into the PRD memlog with `memlog.py`.

**[Accessibility]** [prototype] The wallet marker's announcements are doubled, stale or missing.

[prototype] The wallet marker's announcements are doubled, stale or missing.** (verdict.html, script "The wallet marker", 4.1.3 Status Messages) On focus, the live region gets "2,500 of 10,000 replays did this well or better." at the same moment the screen reader reads the button's name and "toggle button, not pressed", so the two can talk over each other. Pressing Enter writes the same sentence again, so it is likely read twice. Esc sets `aria-pressed="false"` but leaves the old sentence in the live region, so nothing says the highlight was cleared. Confirmed in Chrome: after Esc the live text is unchanged. Arrow keys on the slider also unpin the marker without telling anyone. Because blur never clears the live region, focusing the marker again may be silent.

Fix: Point the button's `aria-describedby` at the sentence. The tail label can carry it if it is not `aria-hidden`. Then drop the live update on focus. Use the live region only for pin and unpin, with different text each time: "Highlight on: 2,500 of 10,000 …" and "Highlight off". Announce "Highlight off" on Esc and on an unpin caused by the slider too.

**[Accessibility]** [prototype] Hover labels vanish when you move the pointer onto them.

[prototype] Hover labels vanish when you move the pointer onto them.** (verdict.html `.tail-label`, `.chart-tip`, 1.4.13 Content on Hover or Focus, "hoverable") The tail label sits 14 px right of the 28 px marker button and has `pointer-events: none`. Moving the pointer towards it fires `pointerleave` on the button, and the label disappears. The bar label works the same way. Moving onto it changes it to another bar's label, or hides it once the pointer leaves the slider area at the top. Esc does dismiss both labels, and they stay put while the pointer is still. So only "hoverable" fails. Screen-magnifier users are hit hardest, because they have to move to read.

Fix: Treat the marker button and the tail label as one hover area: give the label pointer events and hide it only when the pointer leaves both. Alternatively, hide after a 300 ms delay that is cancelled when the pointer re-enters. For bar labels, keep the label while the pointer is over the label itself. Add the rule to EXPERIENCE.md › Chart explore so the build keeps it.

**[Accessibility]** [prototype + spec] A failed copy is silent, and "Copied" is not part of the button's name.

[prototype + spec] A failed copy is silent, and "Copied" is not part of the button's name.** (verdict.html copy script; EXPERIENCE.md › Copy address; 4.1.3, 3.3.1, 2.5.3 Label in Name) If `navigator.clipboard` is missing or the copy is refused, nothing happens. This was confirmed with a refused write. The user then pastes whatever was on the clipboard before. The spec only says the address stays selectable, but nobody is told to select it. While "Copied" is visible, the name is still "Copy wallet address". A speech-input user who says "click Copied" gets nothing. That part is minor.

Fix: When copying fails, show and announce "Copy failed. Select the address and press Ctrl+C", and select the address text. Put the status in a live region *outside* the button: some screen readers ignore live regions inside a named button. Write the failure state into EXPERIENCE.md › Copy address.

**[Accessibility]** [spec] Page changes, the Fetching state and how a new Verdict is announced are not specified.

[spec] Page changes, the Fetching state and how a new Verdict is announced are not specified.** (EXPERIENCE.md › State Patterns "Fetching", Accessibility Floor "Live updates", 2.4.3 Focus Order, 4.1.3) The spec says "the arrival of a Verdict is announced", but not how. If the frontend turns out to be a single-page app, a screen-reader user will hear nothing when the Verdict page loads. "Button disabled" while fetching takes focus off the button the user just pressed. In Chrome, focus falls back to the page. The `logo-and-tab.html` demo has the same issue: its button is disabled while the demo Scan runs. The *No Polymarket history* state has no main heading defined.

Fix: Add three rules to the Accessibility Floor. 1. On every page change, including a client-side route change, update the tab title and move focus to the `h1`, or to a "Skip to content" target that holds it. 2. While fetching, keep the button focusable with `aria-disabled="true"`, or move focus to the status line, and put "Fetching trades from Polymarket…" in a polite live region. 3. Each error or empty state has its own `h1`, for example "No Polymarket history found".

**[Accessibility]** [spec] The form and error rules are not concrete enough to build or test.

[spec] The form and error rules are not concrete enough to build or test.** (EXPERIENCE.md › Accessibility Floor "Forms", Component Patterns "Address field", "New Scan form", "Scan list"; 3.3.1, 3.3.2, 1.3.1, 2.4.6) "Linked to it" does not say how. The visible label of the address field is never named. The New Scan form has no error states: no date, a date in the future or outside the data, a Wallet count that is not a number or is out of range. The "✕" in error messages may be read as "multiplication sign". Several "Resume" buttons in the Scan list would all have the same name.

Fix: Write the mechanism down: the visible label "Wallet address" on a `<label for>` the error sentence with `aria-describedby` and `aria-invalid="true"`, starting with hidden text "Error:" and with the ✕ `aria-hidden` allowed ranges and error texts for both New Scan fields button names like "Resume Scan (Cut-off Date 1 Jun 2026)"

**[Accessibility]** [spec + prototype] Tables that scroll sideways can't always be scrolled by keyboard.

[spec + prototype] Tables that scroll sideways can't always be scrolled by keyboard.** (DESIGN.md › Layout "Wide tables scroll inside their card"; verdict.html `.table-card`; 2.1.1 Keyboard, 1.4.10 Reflow) The mockup's scroll container has `tabindex -1`, no role and no name. The Watchlist can get away with it, because its row links take focus and the browser scrolls to them. The S3 domain table, the Hold-up group figures and any table without links can't be scrolled by keyboard. At 200% zoom (640 CSS px) the right-hand columns, such as Real PnL, are cut off.

Fix: Specify that every table container that can scroll gets `tabindex="0"`, `role="region"` and `aria-label` (the table's caption), plus the normal focus ring. Do the same in the mockup.

**[Accessibility]** [prototype; advisory, beyond 2.1 AA] In Windows High Contrast (forced colours) the chart's bars disappear.

[prototype; advisory, beyond 2.1 AA] In Windows High Contrast (forced colours) the chart's bars disappear.** (verdict.html `.bar`, `.dot.is-filled`; 1.4.11 in spirit) Bars and filled dots are drawn as backgrounds, and forced colours removes backgrounds. Verified: the chart showed only gridlines and the marker, and the filled and empty dots looked the same. The text alternative and the Verdict text still carry the meaning, so this is not a strict 2.1 AA failure. It does hit real Windows users, and the examiner runs Windows.

Fix: Add `@media (forced-colors: active) { .bar { forced-color-adjust: none; background: CanvasText; } .bar.is-tail, .bar.is-active { background: Highlight; } .dot.is-filled { forced-color-adjust: none; background: CanvasText; } }`, or draw bars with borders or SVG. Add one line to DESIGN.md.

**[Wording]** "replays" and "Simulations" are mixed on one chart, and the spec never says they mean the same thing.

"replays" and "Simulations" are mixed on one chart, and the spec never says they mean the same thing. The title, y-axis, hover label, tail label and text alternative say "replays". The FR-9 marker label must say "above all 10,000 Simulations". A user who sees both words on the same chart may think they are two different things. (EXPERIENCE.md › Luck chart, Chart explore, Wallet marker; DESIGN.md › Chart card; verdict.html.)

Fix: add to EXPERIENCE.md › Voice and Tone: "On screen, a Simulation (PRD §3) is called a *replay*. The FR-9 marker label keeps the PRD wording 'above all 10,000 Simulations'." In About this chart, start with: "Each replay (a Simulation) keeps this wallet's 212 bets…". Or ask the PRD to allow "above all 10,000 replays" in FR-9.

**[Wording]** Four terms are used for one glossary concept, with no mapping stated: "resolved bets" (stats line, chart alt, *Not enough data*, Watchlist column), "Resolved Positions" (Hold-up cards, domain table), "positions held to resolution" (honesty card), and "later bets" (Flow 4: "640 later bets").

Four terms are used for one glossary concept, with no mapping stated: "resolved bets" (stats line, chart alt, *Not enough data*, Watchlist column), "Resolved Positions" (Hold-up cards, domain table), "positions held to resolution" (honesty card), and "later bets" (Flow 4: "640 later bets"). EXPERIENCE.md line 12 says terms are used exactly as defined, but the screens do not do that. (EXPERIENCE.md › Component Patterns, State Patterns, Flow 4; DESIGN.md › Stats line, Honesty card.)

Fix: add to Voice and Tone: "On screen, a Resolved Position is called a *resolved bet*. A Position is a *bet*." Then use "resolved bets" in every table header and card, including the Hold-up cards and the domain table column ("Resolved bets"). For the after part, write "640 resolved bets after the Cut-off Date", not "later bets".

**[Wording]** About this chart says: "The blue line is what the wallet really made." That is not true.

About this chart says: "The blue line is what the wallet really made." That is not true. Real PnL counts only bets held to resolution. It leaves out Exit PnL (−$3,150 on this same page) and fees, so "really made" contradicts the honesty card. (verdict.html › About this chart, 3rd paragraph.)

Fix: "The blue line is this wallet's Real PnL: what it made on the 212 bets it held to resolution."

**[Wording]** The Watchlist's "#" rank column, together with the sort by p-value, reads as a ranking ("#1 = best wallet").

The Watchlist's "#" rank column, together with the sort by p-value, reads as a ranking ("#1 = best wallet"). That is a leaderboard feel, which the spec itself rejects. It also misleads statistically: a smaller p-value means *stronger evidence*, not a *bigger edge*. A wallet with many bets gets a tiny p-value from a small edge. The PRD requires the sort (FR-16) but not the rank numbers. (EXPERIENCE.md › Watchlist table; DESIGN.md › Data table; verdict.html prototype table.)

Fix: drop the "#" column, and make the caption read: "Sorted by p-value, smallest first. A smaller p-value means stronger evidence of skill, not a bigger edge."

**[Wording]** The Copy p-value phrase has no rule for its edge cases.

The Copy p-value phrase has no rule for its edge cases. When no random group scores as well, the Copy p-value is 1/10,001 ≈ 0.01%, so the template gives "random groups did as well in 0.01% of draws". That is false, because none did. This is the same trap FR-8 closes for the Verdict odds. The number of decimals is also not set. (EXPERIENCE.md › Number and phrase rules, Copy Test layout.)

Fix: add a rule: "When no random group scored as well: 'no random group did as well in 10,000 draws'. Otherwise X = Copy p-value × 100, with 1 decimal under 10% and whole numbers above." Log this as a deviation from FR-18's template, or raise it in the PRD first.

**[Wording]** The per-Wallet Copy Test table carries only a two-word tag, "Not luck-checked".

The per-Wallet Copy Test table carries only a two-word tag, "Not luck-checked". This table is exactly where a user would pick "which wallet to copy", and a terse tag does not say what it means. FR-18 says the per-Wallet numbers are marked as not luck-checked and only the Random Group Check is. The spec also names the upper-bound note but gives no wording for it. (EXPERIENCE.md › Copy Test layout.)

Fix: add a caption above the table: "These per-Wallet numbers are not luck-checked. Only the Random Group Check above is." Under the table, use the exact FR-18 text: "Follower PnL ignores the spread and the follower's own price impact, so it is an upper bound."

**[Wording]** The "Also avoided" word list is too narrow for the risk.

The "Also avoided" word list is too narrow for the risk. It leaves out "follow", "winner", "top", "best", "safe" and "proven", and FR-24's check and the developers will both rely on this list. (EXPERIENCE.md › Voice and Tone, Banned words.)

Fix: "Also avoided about a Wallet: 'copy this', 'follow', 'recommended', 'winner', 'best', 'top' (except in the factual Scan definition 'top Wallets by profit'), 'safe', 'proven', 'sure thing', 'beat the market', 'genius', 'smart money'. The PRD test names (Copy Test, Follower PnL) are allowed."

**[Wording]** The FR-11 share "of the profit from the single largest bet" has no wording for wallets whose Real PnL is zero, negative or small.

The FR-11 share "of the profit from the single largest bet" has no wording for wallets whose Real PnL is zero, negative or small. There it gives nonsense such as "−70%" or "310% of the profit", which misleads exactly on the wallets with *No evidence of skill*. (EXPERIENCE.md › Honesty notes; DESIGN.md › Honesty card; verdict.html "70% of the profit came from the single largest bet.")

Fix: "If Real PnL ≤ $0, show 'Largest single bet: $X' instead of a share. If the share is over 100%, show 'More than all of the Real PnL came from the single largest bet ($X); the other bets lost money overall.'" Also say "of the Real PnL", not "of the profit".

### Low (44)

**[Rubric: Flow coverage]** The example numbers don't agree with each other.

The example numbers don't agree with each other. The chart text alternative uses "$12,340 … about 1 time in 300", but the flow it serves (UJ-1) uses $40,180 and 1 in 4. The Voice table's "Do" example, "212 resolved bets; at least 30 are needed for a Verdict", contradicts itself, since 212 is more than 30 (EXPERIENCE.md › Component Patterns › Chart text alternative; Voice and Tone row 3).

Fix: use the UJ-1 numbers in the alt-text example and "12 resolved bets" in the Voice row.

**[Rubric: Flow coverage]** Flow 4 step 3 interrupts the Scan by "closing the laptop lid".

Flow 4 step 3 interrupts the Scan by "closing the laptop lid". Since the app runs on the same laptop, sleep would more likely pause the Scan than interrupt it. The spine never says what makes a Scan "interrupted" (see §4) (EXPERIENCE.md › Flow 4 step 3).

Fix: use a trigger the app can actually detect, e.g. "he stops the app" or "Polymarket stops answering".

**[Rubric: Token completeness]** Contrast targets are stated in general terms, with no table, so nobody downstream can re-check them after a token change (DESIGN.md › Colors, last two paragraphs).

Contrast targets are stated in general terms, with no table, so nobody downstream can re-check them after a token change (DESIGN.md › Colors, last two paragraphs).

Fix: add a short ratio table for the load-bearing pairs (the recomputed values below can be pasted in). Also state that the empty dot (1.65:1 light) and accent-on-chart-bar (2.24:1) fall under 3:1 on purpose, because the text carries the meaning.

**[Rubric: Token completeness]** `components.interaction` is motion and shadow values, not a component.

`components.interaction` is motion and shadow values, not a component. Many component values are prose strings ("3 circles, 30px, 6px ring; filled … or empty …") that a token resolver cannot flatten (DESIGN.md frontmatter `components.interaction`, `verdict-hero`, `warning-box`).

Fix: move motion into its own `motion` group and split compound strings into separate keys where they will be consumed as tokens.

**[Rubric: Component coverage]** These DESIGN components have no EXPERIENCE behaviour row: Info box, Info tag, Warning box, Error message, Logo.

These DESIGN components have no EXPERIENCE behaviour row: Info box, Info tag, Warning box, Error message, Logo. Their behaviour is partly covered in State Patterns and Accessibility (EXPERIENCE.md › Component Patterns).

Fix: add one-line rows, or a note that these are static and their states live in State Patterns.

**[Rubric: State coverage]** These smaller states are missing: an empty Comparison Group (every scanned Wallet passed or had *Not enough data*); the second *Not enough data* reason for the Copy Verdict ("no Passer in the Copy Pool"; only the "<1,000 groups" text is drafted); a model that fails with a key set (S3 Explanation and Domain labels); submitting an empty address field (EXPERIENCE.md › State Patterns).

These smaller states are missing: an empty Comparison Group (every scanned Wallet passed or had *Not enough data*); the second *Not enough data* reason for the Copy Verdict ("no Passer in the Copy Pool"; only the "<1,000 groups" text is drafted); a model that fails with a key set (S3 Explanation and Domain labels); submitting an empty address field (EXPERIENCE.md › State Patterns).

Fix: add one row each.

**[Rubric: State coverage]** For a Scan in Offline Mode, the date is fixed, but the meaning of the Wallet-count field (default 200) against a Sample Dataset of about 10 real Wallets plus the synthetic ones is not stated (EXPERIENCE.md › Component Patterns › New Scan form).

For a Scan in Offline Mode, the date is fixed, but the meaning of the Wallet-count field (default 200) against a Sample Dataset of about 10 real Wallets plus the synthetic ones is not stated (EXPERIENCE.md › Component Patterns › New Scan form).

Fix: say the count is fixed or hidden in Offline Mode and the Scan uses the whole Sample Dataset.

**[Rubric: Visual reference coverage]** The round-2 images are cited only in Brand & Style, not at the components they show.

The round-2 images are cited only in Brand & Style, not at the components they show. `watchlist-light/dark.webp` is the only visual for the Watchlist, page header, tabs and Data table, but those rows don't link it (DESIGN.md › Components › Page header with summary card, Tabs, Data table).

Fix: add "(see `imports/round-2-images/watchlist-light.webp`)" at those rows.

**[Rubric: Visual reference coverage]** `.working/` holds two pieces of decision evidence (the ChatGPT prompt Edvard ran, and the three logo-marker variants he chose from) that the spines don't link.

`.working/` holds two pieces of decision evidence (the ChatGPT prompt Edvard ran, and the three logo-marker variants he chose from) that the spines don't link. If the folder is committed, they are orphans; if it isn't, the memlog points to missing files (`.working/`; `.memlog.md` #18, #47).

Fix: link them from DESIGN › Logo and EXPERIENCE Open Question 3, or move them to `imports/` / `docs/ai-logs/` before committing.

**[Rubric: Bloat & overspecification]** Behaviour is repeated in DESIGN › Components and Interaction states: "Copied" for 2 s, the theme toggle's screen-reader names, the dots hidden from screen readers, the chart hover and marker behaviour, the build-up timings.

Behaviour is repeated in DESIGN › Components and Interaction states: "Copied" for 2 s, the theme toggle's screen-reader names, the dots hidden from screen readers, the chart hover and marker behaviour, the build-up timings. All of this is also in EXPERIENCE › Component Patterns. One case has already drifted (the active bar colour, §2) (DESIGN.md › Components › Theme toggle, Address card, Verdict hero; Interaction states).

Fix: keep visual values in DESIGN and point to EXPERIENCE for behaviour.

**[Rubric: Bloat & overspecification]** "Open Questions for UX" holds two settled decisions and one history note, not open questions (EXPERIENCE.md › Open Questions 1–3).

"Open Questions for UX" holds two settled decisions and one history note, not open questions (EXPERIENCE.md › Open Questions 1–3).

Fix: keep only what is truly open (the mechanism for setting Offline Mode; the default Cut-off Date value) and drop Q3, which DESIGN › Brand & Style already covers.

**[Rubric: Bloat & overspecification]** Some pixel values have tokens available: "24 px side margins (16 px on a phone)" = `{spacing.5}` / `{spacing.4}` (DESIGN.md › Layout & Spacing).

Some pixel values have tokens available: "24 px side margins (16 px on a phone)" = `{spacing.5}` / `{spacing.4}` (DESIGN.md › Layout & Spacing).

Fix: use the token names.

**[Rubric: Inheritance discipline]** Some items have no memlog or PRD basis: the Back link (memlog #8 covers the Watchlist → Verdict link, not the return link) and the Domain-table note "Each domain's odds are adjusted for testing several domains." (new copy; FR-20 supports it, but no decision is recorded) (EXPERIENCE.md › Component Patterns › Back link, Domain table).

Some items have no memlog or PRD basis: the Back link (memlog #8 covers the Watchlist → Verdict link, not the return link) and the Domain-table note "Each domain's odds are adjusted for testing several domains." (new copy; FR-20 supports it, but no decision is recorded) (EXPERIENCE.md › Component Patterns › Back link, Domain table).

Fix: one memlog line each.

**[Rubric: Inheritance discipline]** The Accessibility Floor says AA was chosen "as the level Norwegian rules for public websites point to".

The Accessibility Floor says AA was chosen "as the level Norwegian rules for public websites point to". Memlog #12 says Edvard still has to check Lovdata/Uutilsynet before citing it (EXPERIENCE.md › Accessibility Floor, first paragraph).

Fix: soften to "the level commonly required for public websites in Norway (to be confirmed)" until checked.

**[Rubric: Inheritance discipline]** EXPERIENCE names colours in plain words: "Red error", "a yellow '⚠ Likely market maker'", "accent, 2 px".

EXPERIENCE names colours in plain words: "Red error", "a yellow '⚠ Likely market maker'", "accent, 2 px".

Fix: use `{colors.error}`, "warning box" and the new `focus-ring` token, so the references resolve by name.

**[Rubric: Shape fit]** "Open Questions for UX" is an invented section that mostly holds closed items (see §6).

"Open Questions for UX" is an invented section that mostly holds closed items (see §6). The frontmatter `components.interaction` is a motion group placed under components (see §2).

Fix: as in §2 and §6.

**[Accessibility]** [prototype + spec] Warnings and errors are marked only by look.

[prototype + spec] Warnings and errors are marked only by look.** (verdict.html `.warning`; DESIGN.md › Warning box, Error message; 1.3.1 Info and Relationships) The ⚠ icon is `aria-hidden` and `role="note"` says nothing about caution, so a screen reader reads the sentence with no hint that it is a warning.

Fix: Start the text with hidden "Warning:" (and "Error:" for error messages). Write this into DESIGN.md's Warning box and Error message entries.

**[Accessibility]** [prototype] The stats line runs together for screen readers.

[prototype] The stats line runs together for screen readers.** (verdict.html `.stats .line`; 1.3.1) The `aria-hidden` "•" leaves no space, and Chrome's tree reads "212 resolved betsReal PnL $40,180".

Fix: Put spaces outside the hidden separator, or use a hidden ", ".

**[Accessibility]** [prototype + spec] The tail highlight is a change of hue only.

[prototype + spec] The tail highlight is a change of hue only.** (verdict.html `.bar.is-tail`; DESIGN.md › chart-tail; 1.4.1, 1.4.11) Tail bars vs normal bars measure 1.04:1 in light and 1.22:1 in dark. The marker line vs the tail bars is 2.16:1 in light and 1.90:1 in dark. Without colour vision, nothing changes on hover. It passes WCAG only because the tail label states the number. DESIGN.md's "checked with a script" list doesn't cover the state colours: tail, active bar, tooltip and row hover. All of these pass against the card. Results: tail 3.14 / 3.72, active bar 9.33 / 9.58, tooltip text 17.6 / 14.5.

Fix: Make tail bars clearly darker than normal bars (e.g. accent 85% instead of 65%) so there is also a change in lightness. Add the state colours to the contrast script and to DESIGN.md.

**[Accessibility]** [prototype] The bar label covers the marker dot.

[prototype] The bar label covers the marker dot.** (verdict.html `setActive`; 2.4.7, readability) When the slider gets focus it starts on the marker's bar. The dark label then sits over the marker's dot and the top of its line (seen in Chrome at 1280 px).

Fix: Start the label at the marker bar's right edge for that bar, or move it to the side.

**[Accessibility]** [prototype] The theme toggle changes its own name.

[prototype] The theme toggle changes its own name.** (verdict.html `#theme-toggle`; 4.1.2) Swapping the `aria-label` on click is allowed, but many screen readers don't read the new name, so the user hears no result.

Fix: Optional. Keep the current name and add a short polite live message ("Dark theme on"). Or use a fixed name, "Dark theme", with `aria-pressed`.

**[Accessibility]** [prototype] `aria-labelledby` on `<code>` is ignored.

[prototype] `aria-labelledby` on `<code>` is ignored.** (verdict.html `#wallet-address`; 4.1.2) The `code` role can't be named, and Chrome drops the label. No harm is done, because the visible label comes right before it.

Fix: Remove the attribute.

**[Accessibility]** [prototype] The disclosure arrow is read aloud, and the help text assumes a mouse and colour vision.

[prototype] The disclosure arrow is read aloud, and the help text assumes a mouse and colour vision.** (verdict.html `.about summary::after`, About text; 1.3.3 Sensory Characteristics) The "▾" / "▴" made in CSS is read as "down-pointing small triangle". "The blue line is …" and "Point at a bar or at the line" lean on colour and a mouse.

Fix: Use `content: " ▾" / ""`. Change the text to "The blue line labelled 'This wallet' …" and add "or use the arrow keys".

**[Accessibility]** [prototype] Text below the spec's minimum.

[prototype] Text below the spec's minimum.** (verdict.html `.offline-pill` at ≤ 640 px is 12 px; DESIGN.md › Typography "No text below 13 px") This is not a WCAG failure, but it breaks the project's own rule.

Fix: Keep 13 px and let the pill wrap, or shorten it.

**[Accessibility]** [prototype] The theme toggle shrinks under text spacing at 320 px.

[prototype] The theme toggle shrinks under text spacing at 320 px.** (verdict.html `.theme-toggle`; 1.4.12 Text Spacing) With the 1.4.12 text spacing on, the `nowrap` Offline pill grows and the toggle (flex-shrink 1) gets narrower than 40 px.

Fix: Give `.theme-toggle` `flex: none`, and let the pill wrap.

**[Accessibility]** [prototype] The chart is empty without JavaScript.

[prototype] The chart is empty without JavaScript.** (verdict.html `.plot.pre-build` in the markup) The bars and marker start at scale 0 or opacity 0 in the HTML. If the script fails, the chart stays empty. The text alternative is still there.

Fix: Add `pre-build` from the script, not in the HTML.

**[Accessibility]** [spec] The full address in the table link's name clashes with Label in Name.

[spec] The full address in the table link's name clashes with Label in Name.** (DESIGN.md › Data table "full address … in the link's accessible name"; 2.5.3) The visible text is "0x1a2b…9f0e". A name that holds only the full 42-character address doesn't contain that text. The full address is also tiring to listen to in every row.

Fix: The mockup's approach is better: "Open Verdict for wallet 0x1a2b…9f0e". Put the full address in `aria-describedby` or the `title` if needed, and update DESIGN.md to match.

**[Accessibility]** [spec] Semantics of the Scan pages that aren't mocked yet.

[spec] Semantics of the Scan pages that aren't mocked yet.** (EXPERIENCE.md › Scan sub-navigation, Scan progress; DESIGN.md › Tabs, Progress bar; 1.3.1, 4.1.2) The Watchlist, Hold-up Test and Copy Test "tabs" are separate pages with their own URLs. A builder could wrongly use ARIA `tablist`. The progress bar has no defined role or value.

Fix: State that the tabs are a `<nav aria-label="Scan">` with links and `aria-current="page"`. State that the bar is a `<progress>` or `role="progressbar"` with `aria-valuetext="84 of 200 Wallets checked"`, next to the polite 10% live region already in the spec.

**[Wording]** "That is how a trader with no edge would have done." A single replay is one *possible* result, not *the* result.

"That is how a trader with no edge would have done." A single replay is one *possible* result, not *the* result. (verdict.html › About this chart, 1st paragraph.)

Fix: "…That is one way a trader with no edge could have done."

**[Wording]** "Positions sold early: −$3,150 (Exit PnL)".

"Positions sold early: −$3,150 (Exit PnL)". Exit PnL also includes shares sold from positions that were partly kept to resolution, so "positions" undercounts. (verdict.html › honesty card, column 2.)

Fix: "Shares sold before resolution: −$3,150 (Exit PnL)."

**[Wording]** "Long shots tend to be overpriced." stands alone, and a non-statistician cannot see why it limits the test.

"Long shots tend to be overpriced." stands alone, and a non-statistician cannot see why it limits the test. The PRD lists it as content, not as exact text, so a clause can be added. (verdict.html › limits text.)

Fix: "Long shots tend to be overpriced, so a Wallet that mostly buys favourites can beat the odds from that known pattern alone."

**[Wording]** This one is in the PRD, not the spec.

This one is in the PRD, not the spec. With FR-8's two-significant-figures rule, p-values between about 0.2 and 0.5 give phrases like "about 1 time in 2.2" or "about 1 time in 3.3", which read oddly. (EXPERIENCE.md › Number and phrase rules.)

Fix: raise it in the PRD memlog. For example, round N to a whole number when N < 10 ("about 1 time in 3"). Do not change the rule silently in the build.

**[Wording]** The spec says the tail label's number "comes from the p-value".

The spec says the tail label's number "comes from the p-value". It should be the exact count of Simulations with PnL ≥ Real PnL (= p × 10,001 − 1), never rounded. The spec should also cover the ends: "0 of 10,000…" and "10,000 of 10,000…". (EXPERIENCE.md › Wallet marker.)

Fix: "The number is the exact count of Simulations with PnL at or above the Real PnL (the same count the p-value uses), not rounded and not summed from the bars."

**[Wording]** In the mockup, the first and last bars hold the overflow (5 replays each, against 2 next to them), but the hover label says "$195,000 to $200,000: 5 replays".

In the mockup, the first and last bars hold the overflow (5 replays each, against 2 next to them), but the hover label says "$195,000 to $200,000: 5 replays". (verdict.html BINS.)

Fix: label the end bars "$195,000 or more" and "−$195,000 or less", and state that rule in Chart explore.

**[Wording]** "so the marker's distance from the middle is the evidence" is not quite right.

"so the marker's distance from the middle is the evidence" is not quite right. The evidence is the share of replays at or beyond the marker. Real luck distributions with long shots are skewed, and the same distance can mean very different odds. (EXPERIENCE.md › Luck chart.)

Fix: "…so the user sees how much of the luck curve lies at or beyond the marker. That share is the evidence."

**[Wording]** A Mock-LLM Explanation gets a "Template text" tag "so it is never mistaken for model output".

A Mock-LLM Explanation gets a "Template text" tag "so it is never mistaken for model output". A model Explanation that FR-24 replaced with the template is shown with no tag, so it *will* be mistaken for model output. (EXPERIENCE.md › Explanation.)

Fix: "Whenever the template text is shown (Mock LLM Mode or a replacement under FR-24), it carries the 'Template text' tag."

**[Wording]** Flow 3 presents "fewer than 1 time in 10,000" and "above all 10,000 Simulations" as the expected result for the Sharp trader.

Flow 3 presents "fewer than 1 time in 10,000" and "above all 10,000 Simulations" as the expected result for the Sharp trader. The PRD only guarantees p < 0.01 (exact p ≈ 0.00004, so a Simulation can tie it). The same applies to the sample coin-flipper, since up to 7% of coin-flippers pass. (EXPERIENCE.md › Flow 3 steps 4–5.)

Fix: "…shows ●●● *Skilled (high confidence)* (with the Sample Dataset's fixed Seed, 'fewer than 1 time in 10,000')". Make sure the sample coin-flipper is one that does not pass.

**[Wording]** Flow 1 climax: "The $40k now looks like one lucky bet, not a skill." *No evidence of skill* is not proof of luck.

Flow 1 climax: "The $40k now looks like one lucky bet, not a skill." *No evidence of skill* is not proof of luck. (EXPERIENCE.md › Flow 1 step 6.)

Fix: "Most of the $40k rests on one bet, and the test finds no evidence of skill."

**[Wording]** "…so there is nothing to hold up or copy." The bare "copy" can read as copying the wallet.

"…so there is nothing to hold up or copy." The bare "copy" can read as copying the wallet. (EXPERIENCE.md › State Patterns, No Before-Cut-off Passers.)

Fix: "No Wallet passed on its bets before the Cut-off Date, so the Hold-up Test and Copy Test have nothing to test."

**[Wording]** "Wallet" is capitalised inconsistently on the same page: "This wallet made…" and "This wallet: $40,180" next to "Positions this Wallet sold…" and "make a Wallet look better".

"Wallet" is capitalised inconsistently on the same page: "This wallet made…" and "This wallet: $40,180" next to "Positions this Wallet sold…" and "make a Wallet look better". (verdict.html; EXPERIENCE.md.)

Fix: add one rule to Voice and Tone. Simplest: capitalise glossary terms (Wallet, Verdict, Real PnL, Simulation) everywhere on screen, because the exact PRD texts already do.

**[Wording]** *Not enough data*: "(needs 18 more)" is in brackets, so it is unclear whether it is shown.

*Not enough data*: "(needs 18 more)" is in brackets, so it is unclear whether it is shown. FR-10 requires showing how many more are needed. (EXPERIENCE.md › State Patterns, Flow 2.)

Fix: show "12 resolved bets; at least 30 are needed for a Verdict (18 more)."

**[Wording]** The Flag position contradicts itself.

The Flag position contradicts itself. EXPERIENCE says "beside the Verdict badge" (Flag) and "under the odds phrase" (Verdict header); DESIGN says "under the Verdict hero". FR-22 says "beside the Verdict". (EXPERIENCE.md › Flag, Verdict header; DESIGN.md › Flag.)

Fix: pick one, for example "directly under the odds phrase, outside the Verdict heading", and say it meets FR-22's "beside".

**[Wording]** The Minimum Luck Passes sentence has no rule for Scan sizes other than 200.

The Minimum Luck Passes sentence has no rule for Scan sizes other than 200. For example, 150 × 0.01 = 1.5, and 50 × 0.01 = 0.5. (EXPERIENCE.md › Watchlist table.)

Fix: "'at least about {n × 0.01, rounded to 1 decimal if under 2} of {n} would pass by luck alone, probably more, because these Wallets were picked for high profit'". The 200 case stays as in FR-16.

**[Wording]** In Flow 4, step 7 opens a Wallet from the Copy Test table and shows "← Back to Watchlist", but the Back link rule says it appears only when the page was opened from a Watchlist.

In Flow 4, step 7 opens a Wallet from the Copy Test table and shows "← Back to Watchlist", but the Back link rule says it appears only when the page was opened from a Watchlist. (EXPERIENCE.md › Flow 4, Back link.)

Fix: "← Back to Copy Test (Cut-off Date …)" when opened from the Copy Test. Update the Back link rule to match.

## Reviewer files

- `review-rubric.md`
- `review-accessibility.md`
- `review-wording.md`
