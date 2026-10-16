# Spine Pair Review — LiquidOracle

Reviewer: rubric walker (Claude Code subagent), 2026-10-16. Review only; no spine was edited.
Inputs: `DESIGN.md`, `EXPERIENCE.md`, `.memlog.md`, `mockups/`, `imports/`, `.working/`, and the source PRD (`prd-LiquidOracle-2026-10-12/prd.md`).

## Overall verdict

**Adequate.** The pair is well traced: almost every decision points to an FR or a dated memlog entry, all tokens resolve, colour pairs pass AA, and all five user journeys have flows. What holds it back is the contract between the two files. The Verdict block has five different names. Three PRD-required elements (Exit PnL warning, Flag, Explanation) are placed in different spots in different sections. The S1 start page (Lookup, with the Sample Dataset list) has no layout or visual spec and no mockup. Fix those and the pair is strong.

Finding counts: critical 0 · high 4 · medium 16 · low 16.

---

## 1. Flow coverage — adequate

Checked: `sources` → PRD §2.3 lists UJ-1 to UJ-5. Each has a Key Flow with the UJ name verbatim, a named protagonist (Jonas; "the examiner" for UJ-3), numbered steps and a bold climax. Failure paths: Flow 1 (no history), Flow 3 (address not in sample), Flow 4 (interrupted Scan). Flows 2 and 5 have none, which is fine for Flow 2.

### Findings
- **medium** Flow 4 step 7 opens a Verdict page from the **Copy Test** table, then shows "← Back to Watchlist". The Back link row says it is "only shown when the page was opened from a Watchlist", and the IA "Reached from" column for the Verdict page leaves out the Copy Test. A developer cannot tell what the back link does from the Copy Test (EXPERIENCE.md › Key Flows Flow 4 step 7; Component Patterns › Back link; IA table, Verdict page row). *Fix:* define the back link per origin ("← Back to Copy Test (Cut-off Date …)"), add the Copy Test to "Reached from", and make step 7 match.
- **medium** FR-10 requires the page to show "how many more are needed". The drafted copy is "12 resolved bets; at least 30 are needed for a Verdict", followed by "(needs 18 more)" in parentheses. It is unclear whether "needs 18 more" is shown text or a reviewer note (EXPERIENCE.md › State Patterns, *Not enough data* row; Flow 2 step 2). *Fix:* put the number in the string, e.g. "12 resolved bets; at least 30 are needed for a Verdict (18 more)".
- **low** The example numbers don't agree with each other. The chart text alternative uses "$12,340 … about 1 time in 300", but the flow it serves (UJ-1) uses $40,180 and 1 in 4. The Voice table's "Do" example, "212 resolved bets; at least 30 are needed for a Verdict", contradicts itself, since 212 is more than 30 (EXPERIENCE.md › Component Patterns › Chart text alternative; Voice and Tone row 3). *Fix:* use the UJ-1 numbers in the alt-text example and "12 resolved bets" in the Voice row.
- **low** Flow 4 step 3 interrupts the Scan by "closing the laptop lid". Since the app runs on the same laptop, sleep would more likely pause the Scan than interrupt it. The spine never says what makes a Scan "interrupted" (see §4) (EXPERIENCE.md › Flow 4 step 3). *Fix:* use a trigger the app can actually detect, e.g. "he stops the app" or "Polymarket stops answering".

## 2. Token completeness — adequate

Checked: 38 colour tokens (19 light/dark pairs, all hex), 11 typography roles, 4 radii, 10 spacing tokens, and 19 component entries. All 24 distinct `{path}` references in the frontmatter and prose resolve. Contrast is stated as "all pairs checked with a script", and only the chart-bar ratios are given. I recomputed the load-bearing pairs (see Mechanical notes). All text pairs are ≥ 4.5:1 and all required graphics are ≥ 3:1.

### Findings
- **medium** Component tokens point only at the light names (`{colors.surface-raised}`, `{colors.accent}` …). Nowhere does it say that in the dark theme each `{colors.x}` resolves to `x-dark`. Two entries break the pattern on their own ("(dark theme only)", "(light theme only)") (DESIGN.md frontmatter `components`; Colors). *Fix:* add one rule: "In the dark theme every `{colors.x}` resolves to `{colors.x-dark}`; components list exceptions."
- **medium** Several colours are described in words, with no token or hex: the primary button's hover "slightly deeper blue", the "grey 2 px underline" on nav hover, the outline of the Info tag, the Error message (it never names `{colors.error}`), the focus ring (accent, 2 px, "offset" with no value; there is no component entry), and the chart tail ("accent mixed 65% into surface-raised", with no hex). The mockup's active bar has also drifted from the spec: memlog #53 says it was "softened from pure ink", but DESIGN still says "darkens to ink" (DESIGN.md › Components › Interaction states; Info tag; Error message; EXPERIENCE.md › Accessibility Floor › Keyboard). *Fix:* add `accent-hover`(+dark), `focus-ring` (colour, width, offset) and `chart-tail` hex tokens, plus `error-message` and `info-tag` component entries, and pick one active-bar colour.
- **medium** `spacing.content-max` is 1120px, but the mockup uses 1200px. Memlog #36 says the width was raised "to fit the Verdict on one line", and memlog #38 says "1120 to 1200 px". A builder who follows the token may get a wrapped Verdict (DESIGN.md frontmatter `spacing.content-max`; Layout & Spacing; `mockups/verdict.html` `.wrap max-width: 1200px`). *Fix:* pick one value and log it.
- **medium** There are no responsive type steps. `verdict-display` (56px) and `page-title` (52px) have no smaller sizes, yet the spine promises a working 320px window. The mockup solves this on its own (40px under 640, 34px under 400) and also uses 12px text (offline pill, disclosure caret), which breaks the spine's own "No text below 13 px" rule (DESIGN.md › Typography; mockup `@media (max-width: 640px)`). *Fix:* add `verdict-display-sm` / `page-title-sm` tokens with their breakpoint, and fix the 12px text in the mockup.
- **low** Contrast targets are stated in general terms, with no table, so nobody downstream can re-check them after a token change (DESIGN.md › Colors, last two paragraphs). *Fix:* add a short ratio table for the load-bearing pairs (the recomputed values below can be pasted in). Also state that the empty dot (1.65:1 light) and accent-on-chart-bar (2.24:1) fall under 3:1 on purpose, because the text carries the meaning.
- **low** `components.interaction` is motion and shadow values, not a component. Many component values are prose strings ("3 circles, 30px, 6px ring; filled … or empty …") that a token resolver cannot flatten (DESIGN.md frontmatter `components.interaction`, `verdict-hero`, `warning-box`). *Fix:* move motion into its own `motion` group and split compound strings into separate keys where they will be consumed as tokens.

## 3. Component coverage — thin

Checked: I extracted every component name from both files. DESIGN has 22 component headings, 8 interaction-state rows and 19 frontmatter entries. EXPERIENCE has 25 Component Pattern rows plus the components named in the IA, States and Flows. For each name I checked for a visual row in DESIGN › Components and a behaviour row in EXPERIENCE › Component Patterns.

### Findings
- **high** The central component has five names. PRD FR-8 calls it the "Verdict card". EXPERIENCE uses "Verdict card" (IA, Explanation row, Flow 5), "Verdict header" and "Verdict badge". DESIGN uses "Verdict hero" and "Verdict pill" and never says "Verdict card". So "under the Verdict card" (FR-23 and the Explanation row) has nothing to resolve to (EXPERIENCE.md › IA Verdict page row; Component Patterns › Verdict badge, Verdict header, Explanation; DESIGN.md › Components › Verdict hero, Verdict pill). *Fix:* fix the names once and use them everywhere. For example: **Verdict card** = the whole header block from FR-8 (hero + odds + stats + address card); **Verdict hero** = big dots and heading; **Verdict pill** = the small table version. Drop "badge" and "header".
- **high** The S1 start page has no visual spec. DESIGN › Layout & Spacing describes the Verdict and Scan pages only. Lookup has no layout, and the **Sample Dataset list** (S1, central to UJ-3 and to the examiner) has no DESIGN row. The **fetching indicator** ("moving dot pattern") and the **Skip to content** link also have none. No mockup or image covers Lookup (EXPERIENCE.md Open Question 3 admits it), so a builder has only the spines, and the spines don't cover it (DESIGN.md › Layout & Spacing; Components). *Fix:* add a "Lookup page" paragraph to Layout, plus Components rows for the Sample Dataset list (item anatomy, "(synthetic)" label, the Offline-only heading), the fetching indicator and the skip link.
- **medium** Other names differ between the files: Offline pill / Offline Mode indicator; Honesty card / Honesty notes (the PRD says notes); Copy Verdict pill / Copy Verdict badge; Text input + button / Address field + "Check wallet"; Progress bar / Scan progress; Page header with summary card / Scan sub-navigation; Data table / Watchlist table (DESIGN.md › Components; EXPERIENCE.md › Component Patterns, IA). *Fix:* one name per component, the same in both files. Where a row is generic (Data table), say which instances use it (Watchlist table, Copy Test table, Domain table).
- **medium** Several S2/S3 components have behaviour but no visual spec: the New Scan form (date field and number field; DESIGN only covers the address input), the Scan list (status display, Resume button), the Hold-up group cards (six figures each), the Explanation block (S3) and the Back link (EXPERIENCE.md › Component Patterns rows; DESIGN.md › Components has no match). *Fix:* add short DESIGN rows. Most can reuse existing tokens (card, stat-figure, button-primary).
- **medium** The Tabs have no behaviour row. The IA gives each tab its own URL (`/scans/3/hold-up`), which makes them links, but they look like tabs. The keyboard model (Tab between links, or arrow keys in an ARIA tablist) and the screen-reader role are undefined (DESIGN.md › Components › Tabs; EXPERIENCE.md › IA, Scan sub-navigation). *Fix:* state "Tabs are links in a `nav` with `aria-current="page"`; no tablist" (or the other choice).
- **low** These DESIGN components have no EXPERIENCE behaviour row: Info box, Info tag, Warning box, Error message, Logo. Their behaviour is partly covered in State Patterns and Accessibility (EXPERIENCE.md › Component Patterns). *Fix:* add one-line rows, or a note that these are static and their states live in State Patterns.

## 4. State coverage — adequate

Checked: the six IA surfaces (Lookup, Verdict page, Scans, Watchlist, Hold-up Test, Copy Test) against empty, loading/cold-load, focus, error, offline and bad input. Permission-denied doesn't apply (no login). Verdict-page states are well covered (FR-1, FR-2, FR-8 to FR-11, FR-14). Gaps are mostly on the Scan side and at deep links.

### Findings
- **high** The three PRD-required elements on the Verdict page are placed differently in different sections:
  - **Exit PnL warning:** State Patterns says "right under the badge". The Verdict header row says "beside" the stats. DESIGN says "to the right of the stats line … never inside the Verdict hero".
  - **Flag:** the EXPERIENCE row says "beside the Verdict badge". The Verdict header row says "under" the odds phrase. DESIGN says "under the Verdict hero".
  - **Explanation:** EXPERIENCE (and FR-23) say "under the Verdict card". DESIGN › Layout says the S3 additions "come after the chart card".

  (EXPERIENCE.md › State Patterns, Exit PnL row; Component Patterns › Verdict header, Flag, Explanation; DESIGN.md › Layout & Spacing; Components › Warning box, Flag.) *Fix:* pick one place for each, write it once in DESIGN Layout, and make every other mention point there. See §7 for the PRD deviation.
- **high** The New Scan form has no states for bad input: an empty, future or malformed Cut-off Date; a date so recent that no after part can exist; a Wallet count of 0, a negative number, a non-number or a very large number. The grading guide checks "stable on bad input", and the Lookup side is covered but this form is not (EXPERIENCE.md › State Patterns; Component Patterns › New Scan form). *Fix:* add rows with error text, limits (min/max Wallets) and the "nothing starts" rule, mirroring the Lookup format error.
- **medium** Scan failure and running Scans are not defined. "Scan progress in the tab" mentions a Scan that "fails", but there is no failed state, and the difference between "interrupted" and "failed" is not given. Also missing: Polymarket stops answering mid-Scan; the user starts a second Scan while one is running; the user opens the Watchlist, Hold-up or Copy tab of a running or interrupted Scan (EXPERIENCE.md › Component Patterns › Scan progress in the tab, Scan list; State Patterns). *Fix:* add rows for "Scan failed (Polymarket not answering)", "Scan already running" and "results of an unfinished Scan" (hidden, or partial with a note), and define what interrupts a Scan (the app stops).
- **medium** Deep links and cold loads are not covered, although every surface has its own URL (Interaction Primitives). Missing: `/wallet/<malformed>`, an unknown Scan id, and a bookmarked Verdict URL for a Wallet not stored yet (does the fetch run on the Verdict page?). "Polymarket not answering" and "No history" are placed on the Verdict page while "Fetching" is placed on Lookup, so where the user lands when a fetch fails is unclear (EXPERIENCE.md › IA › Addresses in the URL; State Patterns rows 2–4). *Fix:* add a "Not found" state for bad URLs, and say which surface shows the fetch states when the page is opened directly.
- **medium** Edge cases of the wallet marker are missing, and its number source is loosely worded. When Real PnL is above all Simulations, the highlight would read "0 of 10,000 replays did this well or better", and it is not said whether the marker is still interactive. "The number comes from the p-value" invites p × 10,000, which gives 2,499.x for p = 0.25 because of the +1 terms in the formula (EXPERIENCE.md › Component Patterns › Wallet marker). *Fix:* say the label uses the count of Simulations with PnL ≥ Real PnL that the Skill Test stores, and define the 0 and 10,000 cases (e.g. no highlight; the FR-9 label carries it).
- **medium** There is no format rule for the Copy p-value as a percent ("0.4% of draws"): how many decimals, and what happens at the floor (1/10,001 ≈ 0.01%). FR-8 has such a rule for the odds phrase, and the spine copies it, but not this one (EXPERIENCE.md › Voice and Tone › Number and phrase rules, last bullet). *Fix:* add e.g. "one significant figure below 1%; at the floor say 'in fewer than 0.01% of draws'", and log it in the PRD memlog if it changes FR-18.
- **low** These smaller states are missing: an empty Comparison Group (every scanned Wallet passed or had *Not enough data*); the second *Not enough data* reason for the Copy Verdict ("no Passer in the Copy Pool"; only the "<1,000 groups" text is drafted); a model that fails with a key set (S3 Explanation and Domain labels); submitting an empty address field (EXPERIENCE.md › State Patterns). *Fix:* add one row each.
- **low** For a Scan in Offline Mode, the date is fixed, but the meaning of the Wallet-count field (default 200) against a Sample Dataset of about 10 real Wallets plus the synthetic ones is not stated (EXPERIENCE.md › Component Patterns › New Scan form). *Fix:* say the count is fixed or hidden in Offline Mode and the Scan uses the whole Sample Dataset.

## 5. Visual reference coverage — adequate

Inventory (16 files). `mockups/verdict.html`, `mockups/logo-and-tab.html`, `mockups/logo/liquidoracle-logo.svg` and `mockups/logo/favicon.svg` are all linked inline with what they show. The four `imports/round-2-images/*.webp` files are named in DESIGN › Brand & Style. `imports/round-3-logo/logo-reference.webp` is named in DESIGN › Brand & Style › Logo. `imports/round-1-html/` (4 HTML files + `chatgpt-notes.md`) is referenced as a folder and marked "not used". Each spine states once that the spines win on conflict. Not referenced from either spine: `.working/chatgpt-prototype-prompt.md` and `.working/logo-variants.png`.

### Findings
- **medium** The spines disagree with each other on breakpoints, and the mockup follows a third set. DESIGN stacks the header and honesty columns "under 900 px" and everything "below 640 px". EXPERIENCE › Responsive uses ≥ 960 / 640–959 / < 640. The mockup uses 900 / 640 / 400. Since "spines win" only works when the spines agree, a builder cannot settle this (DESIGN.md › Layout & Spacing, Components › Honesty card; EXPERIENCE.md › Responsive & Platform; `mockups/verdict.html` media queries). *Fix:* pick one breakpoint set, put it in DESIGN (as tokens if possible), and make EXPERIENCE refer to it.
- **low** The round-2 images are cited only in Brand & Style, not at the components they show. `watchlist-light/dark.webp` is the only visual for the Watchlist, page header, tabs and Data table, but those rows don't link it (DESIGN.md › Components › Page header with summary card, Tabs, Data table). *Fix:* add "(see `imports/round-2-images/watchlist-light.webp`)" at those rows.
- **low** `.working/` holds two pieces of decision evidence (the ChatGPT prompt Edvard ran, and the three logo-marker variants he chose from) that the spines don't link. If the folder is committed, they are orphans; if it isn't, the memlog points to missing files (`.working/`; `.memlog.md` #18, #47). *Fix:* link them from DESIGN › Logo and EXPERIENCE Open Question 3, or move them to `imports/` / `docs/ai-logs/` before committing.

## 6. Bloat & overspecification — strong

Checked for restated PRD content, pixel values where tokens exist, prose that should be a table, and sections nobody downstream would read. Both files are lean. The "(Edvard, date)" tags are worth keeping: they are the course's traceability evidence, not decoration.

### Findings
- **low** Behaviour is repeated in DESIGN › Components and Interaction states: "Copied" for 2 s, the theme toggle's screen-reader names, the dots hidden from screen readers, the chart hover and marker behaviour, the build-up timings. All of this is also in EXPERIENCE › Component Patterns. One case has already drifted (the active bar colour, §2) (DESIGN.md › Components › Theme toggle, Address card, Verdict hero; Interaction states). *Fix:* keep visual values in DESIGN and point to EXPERIENCE for behaviour.
- **low** "Open Questions for UX" holds two settled decisions and one history note, not open questions (EXPERIENCE.md › Open Questions 1–3). *Fix:* keep only what is truly open (the mechanism for setting Offline Mode; the default Cut-off Date value) and drop Q3, which DESIGN › Brand & Style already covers.
- **low** Some pixel values have tokens available: "24 px side margins (16 px on a phone)" = `{spacing.5}` / `{spacing.4}` (DESIGN.md › Layout & Spacing). *Fix:* use the token names.

## 7. Inheritance discipline — adequate

Checked: `sources` resolves to the final PRD. UJ names are verbatim. Verdict and Copy Verdict labels are verbatim. FR IDs on IA and state rows are correct. Glossary terms are used with PRD capitalisation. EXPERIENCE refers to no `{tokens}` by path.

### Findings
- **medium** UI words and glossary terms are mixed with no stated mapping. The chart card says "10,000 replays with no edge", while the FR-9 marker label on the same chart must say "above all 10,000 Simulations". Stats and table columns say "resolved bets", while the Verdict header row says "Resolved Positions". A developer may "fix" one side to match the other (EXPERIENCE.md › Component Patterns › Luck chart, Verdict header, Watchlist table; DESIGN.md › Components › Chart card, Stats line). *Fix:* add a short mapping in Voice and Tone: "UI says *replay* for Simulation and *resolved bet* for Resolved Position, except where the PRD fixes the wording (FR-9 label)". Or use "Simulations" in the chart title too.
- **medium** The PRD deviation is not logged. FR-11 asks for the Exit PnL warning "next to the Verdict", and FR-22 asks for the Flag "beside the Verdict". DESIGN moves the warning to the stats row and the Flag under the hero. Memlog #30 records the chosen look but not that it moves a PRD-required element, and the PRD memlog has no entry (DESIGN.md › Components › Warning box, Flag; PRD FR-11, FR-22). *Fix:* after settling the §4 placement, either keep both "next to the Verdict" or write the deviation and its reason into the PRD memlog with `memlog.py`.
- **low** Some items have no memlog or PRD basis: the Back link (memlog #8 covers the Watchlist → Verdict link, not the return link) and the Domain-table note "Each domain's odds are adjusted for testing several domains." (new copy; FR-20 supports it, but no decision is recorded) (EXPERIENCE.md › Component Patterns › Back link, Domain table). *Fix:* one memlog line each.
- **low** The Accessibility Floor says AA was chosen "as the level Norwegian rules for public websites point to". Memlog #12 says Edvard still has to check Lovdata/Uutilsynet before citing it (EXPERIENCE.md › Accessibility Floor, first paragraph). *Fix:* soften to "the level commonly required for public websites in Norway (to be confirmed)" until checked.
- **low** EXPERIENCE names colours in plain words: "Red error", "a yellow '⚠ Likely market maker'", "accent, 2 px". *Fix:* use `{colors.error}`, "warning box" and the new `focus-ring` token, so the references resolve by name.

## 8. Shape fit — strong

DESIGN sections are in canonical order (Brand & Style → Colors → Typography → Layout & Spacing → Elevation & Depth → Shapes → Components → Do's and Don'ts). The "Interaction states" sub-section inside Components is a good fit. EXPERIENCE has every required section (Foundation, IA, Voice and Tone, Component Patterns, State Patterns, Interaction Primitives, Accessibility Floor, Key Flows) plus Responsive & Platform and Inspiration & Anti-patterns, as in the examples. The extra PRD/Stage columns on the IA and State tables earn their place for traceability.

### Findings
- **low** "Open Questions for UX" is an invented section that mostly holds closed items (see §6). The frontmatter `components.interaction` is a motion group placed under components (see §2). *Fix:* as in §2 and §6.

---

## Mechanical notes

**Sources and journeys.** `sources` → `_bmad-output/planning-artifacts/prds/prd-LiquidOracle-2026-10-12/prd.md` (exists, status final). UJ-1 … UJ-5 → Flows 1 … 5, names verbatim.

**Tokens.** Colours: 19 light + 19 dark, all hex, all paired. Typography: brand, verdict-display, page-title, lede, section-title, stat-figure, eyebrow, body, body-strong, small, number. Rounded: sm, md, lg, full. Spacing: 1–8, content-max, top-bar-height. Components: 19 entries. All `{…}` references resolve. Defined but referenced by no component: `colors.error`, `colors.surface`, `typography.body`, `typography.lede`, `spacing.content-max` (prose only).

**Contrast, recomputed (WCAG 2.x formula).**

| Pair | Light | Dark |
|---|---|---|
| ink-muted on neutral-tint (table head) | 5.58 | 6.83 |
| ink-muted on surface | 5.83 | — |
| accent on accent-tint ("Copied", pills) | 5.90 | 5.41 |
| accent on accent-tint-soft (row hover) | 6.19 | 6.50 |
| accent on surface / surface-raised | 6.32 | 7.07 |
| on-accent on accent (primary button) | 6.78 | 7.65 |
| warning-ink on warning-bg | 10.11 | 10.26 |
| warning-border stripe on warning-bg | 3.68 | 6.36 |
| error on surface-raised | 6.57 | 7.32 |
| on-pill on pill | 16.37 | 15.67 |
| pill on top bar (surface-raised) | 16.37 | 1.08 (border-strong outline carries it) |
| border-strong on surface-raised | 3.35 | 3.75 |
| chart-bar on surface-raised | 3.02 | 3.05 |
| chart-tail (accent 65% mix) on surface-raised | 3.14 | 3.72 |
| chart-tooltip text | 17.62 | 14.48 |
| dot-empty on surface-raised (decorative) | 1.65 | 2.24 |
| accent marker vs chart-bar (adjacent) | 2.24 | 2.32 |

No failure on a load-bearing pair. The two sub-3:1 graphic pairs are acceptable only because the Verdict text and the chart text alternative carry the meaning. Say so in DESIGN.

**Component name map (as found).** Verdict card / Verdict header / Verdict hero / Verdict badge / Verdict pill · Offline pill / Offline Mode indicator · Honesty card / Honesty notes · Copy Verdict pill / Copy Verdict badge · Text input + button / Address field + "Check wallet" · Progress bar / Scan progress · Page header with summary card / Scan sub-navigation · Data table / Watchlist table, Domain table, per-Wallet table.

**Visual files.** 4 mockup files (all linked), 10 import files (round 2 and 3 named; round 1 by folder), 2 working files (not linked). Spines-win-on-conflict: stated in DESIGN › Brand & Style and EXPERIENCE › Foundation.

**Mockup vs spine drift** (spines win, but these should be fixed in one or the other): content width 1200 vs 1120; breakpoints 900/640/400 vs 960/640; 12px text vs the 13px floor; responsive Verdict size 40/34px not in the spines; active bar "softened" vs "ink".
