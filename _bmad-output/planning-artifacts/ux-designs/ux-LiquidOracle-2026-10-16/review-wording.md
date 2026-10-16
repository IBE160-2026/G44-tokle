# Wording and Honesty Review — LiquidOracle

Reviewed: `EXPERIENCE.md`, `DESIGN.md`, `.memlog.md`, `mockups/verdict.html`, `mockups/logo-and-tab.html`, against PRD `prd-LiquidOracle-2026-10-12/prd.md` (§3, FR-1, FR-8 to FR-11, FR-14, FR-16 to FR-18, FR-22 to FR-24, §8). Review only; no spec file was changed.

## Overall verdict

**Pass with fixes.** The spec is honest at its core. The banned words never appear. Every exact PRD text that the spec quotes is reproduced word for word, and the mockup chart is statistically right: it centres on $0, and about 2,499 of 10,000 replays sit at or above $40,180, which matches "about 1 time in 4". The main risks are elsewhere. One navigation label reads as advice ("Find wallets to follow"). Two words are mixed with no mapping stated (replays and Simulations; resolved bets and Resolved Positions). A few sentences claim slightly more than the test shows ("what the wallet really made", a rank column). Some edge cases of the number phrases have no rule yet.

Counts: critical 0 · high 1 · medium 8 · low 16.

## Findings

### High

- **[high]** The section name "Find wallets to follow" is an instruction. It tells the user the app's output is wallets they should follow, which is close to a trade signal (PRD §2.2 and §5: no trade signals, no copy-trading). It sits in the top bar on every page from stage 2, and it is already visible in the stage 1 mockup's top bar (`mockups/verdict.html` line 372), even though DESIGN.md says it is hidden until stage 2. It also clashes with the spec's own rule "Rejected: 'Copy' or 'Follow' buttons" (EXPERIENCE.md › Inspiration & Anti-patterns). The PRD job is a *question* ("find out whether following skilled wallets would actually have paid"; §4.5 title "Is Skill Worth Following?"), and a nav label should keep it a question or a neutral noun. (EXPERIENCE.md › Information Architecture, Flow 4 step 1; DESIGN.md › Top bar; verdict.html nav.) *Fix:* rename the section **"Scan wallets"** (neutral, and it matches the glossary term Scan). Alternative: **"Is following worth it?"**. Update the IA table, Flow 4, DESIGN.md › Top bar and the mockup nav. Remove the link from the stage 1 mockup, or mark it "stage 2" there.

### Medium

- **[medium]** "replays" and "Simulations" are mixed on one chart, and the spec never says they mean the same thing. The title, y-axis, hover label, tail label and text alternative say "replays". The FR-9 marker label must say "above all 10,000 Simulations". A user who sees both words on the same chart may think they are two different things. (EXPERIENCE.md › Luck chart, Chart explore, Wallet marker; DESIGN.md › Chart card; verdict.html.) *Fix:* add to EXPERIENCE.md › Voice and Tone: "On screen, a Simulation (PRD §3) is called a *replay*. The FR-9 marker label keeps the PRD wording 'above all 10,000 Simulations'." In About this chart, start with: "Each replay (a Simulation) keeps this wallet's 212 bets…". Or ask the PRD to allow "above all 10,000 replays" in FR-9.

- **[medium]** Four terms are used for one glossary concept, with no mapping stated: "resolved bets" (stats line, chart alt, *Not enough data*, Watchlist column), "Resolved Positions" (Hold-up cards, domain table), "positions held to resolution" (honesty card), and "later bets" (Flow 4: "640 later bets"). EXPERIENCE.md line 12 says terms are used exactly as defined, but the screens do not do that. (EXPERIENCE.md › Component Patterns, State Patterns, Flow 4; DESIGN.md › Stats line, Honesty card.) *Fix:* add to Voice and Tone: "On screen, a Resolved Position is called a *resolved bet*. A Position is a *bet*." Then use "resolved bets" in every table header and card, including the Hold-up cards and the domain table column ("Resolved bets"). For the after part, write "640 resolved bets after the Cut-off Date", not "later bets".

- **[medium]** About this chart says: "The blue line is what the wallet really made." That is not true. Real PnL counts only bets held to resolution. It leaves out Exit PnL (−$3,150 on this same page) and fees, so "really made" contradicts the honesty card. (verdict.html › About this chart, 3rd paragraph.) *Fix:* "The blue line is this wallet's Real PnL: what it made on the 212 bets it held to resolution."

- **[medium]** The Watchlist's "#" rank column, together with the sort by p-value, reads as a ranking ("#1 = best wallet"). That is a leaderboard feel, which the spec itself rejects. It also misleads statistically: a smaller p-value means *stronger evidence*, not a *bigger edge*. A wallet with many bets gets a tiny p-value from a small edge. The PRD requires the sort (FR-16) but not the rank numbers. (EXPERIENCE.md › Watchlist table; DESIGN.md › Data table; verdict.html prototype table.) *Fix:* drop the "#" column, and make the caption read: "Sorted by p-value, smallest first. A smaller p-value means stronger evidence of skill, not a bigger edge."

- **[medium]** The Copy p-value phrase has no rule for its edge cases. When no random group scores as well, the Copy p-value is 1/10,001 ≈ 0.01%, so the template gives "random groups did as well in 0.01% of draws". That is false, because none did. This is the same trap FR-8 closes for the Verdict odds. The number of decimals is also not set. (EXPERIENCE.md › Number and phrase rules, Copy Test layout.) *Fix:* add a rule: "When no random group scored as well: 'no random group did as well in 10,000 draws'. Otherwise X = Copy p-value × 100, with 1 decimal under 10% and whole numbers above." Log this as a deviation from FR-18's template, or raise it in the PRD first.

- **[medium]** The per-Wallet Copy Test table carries only a two-word tag, "Not luck-checked". This table is exactly where a user would pick "which wallet to copy", and a terse tag does not say what it means. FR-18 says the per-Wallet numbers are marked as not luck-checked and only the Random Group Check is. The spec also names the upper-bound note but gives no wording for it. (EXPERIENCE.md › Copy Test layout.) *Fix:* add a caption above the table: "These per-Wallet numbers are not luck-checked. Only the Random Group Check above is." Under the table, use the exact FR-18 text: "Follower PnL ignores the spread and the follower's own price impact, so it is an upper bound."

- **[medium]** The "Also avoided" word list is too narrow for the risk. It leaves out "follow", "winner", "top", "best", "safe" and "proven", and FR-24's check and the developers will both rely on this list. (EXPERIENCE.md › Voice and Tone, Banned words.) *Fix:* "Also avoided about a Wallet: 'copy this', 'follow', 'recommended', 'winner', 'best', 'top' (except in the factual Scan definition 'top Wallets by profit'), 'safe', 'proven', 'sure thing', 'beat the market', 'genius', 'smart money'. The PRD test names (Copy Test, Follower PnL) are allowed."

- **[medium]** The FR-11 share "of the profit from the single largest bet" has no wording for wallets whose Real PnL is zero, negative or small. There it gives nonsense such as "−70%" or "310% of the profit", which misleads exactly on the wallets with *No evidence of skill*. (EXPERIENCE.md › Honesty notes; DESIGN.md › Honesty card; verdict.html "70% of the profit came from the single largest bet.") *Fix:* "If Real PnL ≤ $0, show 'Largest single bet: $X' instead of a share. If the share is over 100%, show 'More than all of the Real PnL came from the single largest bet ($X); the other bets lost money overall.'" Also say "of the Real PnL", not "of the profit".

### Low

- **[low]** "That is how a trader with no edge would have done." A single replay is one *possible* result, not *the* result. (verdict.html › About this chart, 1st paragraph.) *Fix:* "…That is one way a trader with no edge could have done."
- **[low]** "Positions sold early: −$3,150 (Exit PnL)". Exit PnL also includes shares sold from positions that were partly kept to resolution, so "positions" undercounts. (verdict.html › honesty card, column 2.) *Fix:* "Shares sold before resolution: −$3,150 (Exit PnL)."
- **[low]** "Long shots tend to be overpriced." stands alone, and a non-statistician cannot see why it limits the test. The PRD lists it as content, not as exact text, so a clause can be added. (verdict.html › limits text.) *Fix:* "Long shots tend to be overpriced, so a Wallet that mostly buys favourites can beat the odds from that known pattern alone."
- **[low]** This one is in the PRD, not the spec. With FR-8's two-significant-figures rule, p-values between about 0.2 and 0.5 give phrases like "about 1 time in 2.2" or "about 1 time in 3.3", which read oddly. (EXPERIENCE.md › Number and phrase rules.) *Fix:* raise it in the PRD memlog. For example, round N to a whole number when N < 10 ("about 1 time in 3"). Do not change the rule silently in the build.
- **[low]** The spec says the tail label's number "comes from the p-value". It should be the exact count of Simulations with PnL ≥ Real PnL (= p × 10,001 − 1), never rounded. The spec should also cover the ends: "0 of 10,000…" and "10,000 of 10,000…". (EXPERIENCE.md › Wallet marker.) *Fix:* "The number is the exact count of Simulations with PnL at or above the Real PnL (the same count the p-value uses), not rounded and not summed from the bars."
- **[low]** In the mockup, the first and last bars hold the overflow (5 replays each, against 2 next to them), but the hover label says "$195,000 to $200,000: 5 replays". (verdict.html BINS.) *Fix:* label the end bars "$195,000 or more" and "−$195,000 or less", and state that rule in Chart explore.
- **[low]** "so the marker's distance from the middle is the evidence" is not quite right. The evidence is the share of replays at or beyond the marker. Real luck distributions with long shots are skewed, and the same distance can mean very different odds. (EXPERIENCE.md › Luck chart.) *Fix:* "…so the user sees how much of the luck curve lies at or beyond the marker. That share is the evidence."
- **[low]** A Mock-LLM Explanation gets a "Template text" tag "so it is never mistaken for model output". A model Explanation that FR-24 replaced with the template is shown with no tag, so it *will* be mistaken for model output. (EXPERIENCE.md › Explanation.) *Fix:* "Whenever the template text is shown (Mock LLM Mode or a replacement under FR-24), it carries the 'Template text' tag."
- **[low]** Flow 3 presents "fewer than 1 time in 10,000" and "above all 10,000 Simulations" as the expected result for the Sharp trader. The PRD only guarantees p < 0.01 (exact p ≈ 0.00004, so a Simulation can tie it). The same applies to the sample coin-flipper, since up to 7% of coin-flippers pass. (EXPERIENCE.md › Flow 3 steps 4–5.) *Fix:* "…shows ●●● *Skilled (high confidence)* (with the Sample Dataset's fixed Seed, 'fewer than 1 time in 10,000')". Make sure the sample coin-flipper is one that does not pass.
- **[low]** Flow 1 climax: "The $40k now looks like one lucky bet, not a skill." *No evidence of skill* is not proof of luck. (EXPERIENCE.md › Flow 1 step 6.) *Fix:* "Most of the $40k rests on one bet, and the test finds no evidence of skill."
- **[low]** "…so there is nothing to hold up or copy." The bare "copy" can read as copying the wallet. (EXPERIENCE.md › State Patterns, No Before-Cut-off Passers.) *Fix:* "No Wallet passed on its bets before the Cut-off Date, so the Hold-up Test and Copy Test have nothing to test."
- **[low]** "Wallet" is capitalised inconsistently on the same page: "This wallet made…" and "This wallet: $40,180" next to "Positions this Wallet sold…" and "make a Wallet look better". (verdict.html; EXPERIENCE.md.) *Fix:* add one rule to Voice and Tone. Simplest: capitalise glossary terms (Wallet, Verdict, Real PnL, Simulation) everywhere on screen, because the exact PRD texts already do.
- **[low]** *Not enough data*: "(needs 18 more)" is in brackets, so it is unclear whether it is shown. FR-10 requires showing how many more are needed. (EXPERIENCE.md › State Patterns, Flow 2.) *Fix:* show "12 resolved bets; at least 30 are needed for a Verdict (18 more)."
- **[low]** The Flag position contradicts itself. EXPERIENCE says "beside the Verdict badge" (Flag) and "under the odds phrase" (Verdict header); DESIGN says "under the Verdict hero". FR-22 says "beside the Verdict". (EXPERIENCE.md › Flag, Verdict header; DESIGN.md › Flag.) *Fix:* pick one, for example "directly under the odds phrase, outside the Verdict heading", and say it meets FR-22's "beside".
- **[low]** The Minimum Luck Passes sentence has no rule for Scan sizes other than 200. For example, 150 × 0.01 = 1.5, and 50 × 0.01 = 0.5. (EXPERIENCE.md › Watchlist table.) *Fix:* "'at least about {n × 0.01, rounded to 1 decimal if under 2} of {n} would pass by luck alone, probably more, because these Wallets were picked for high profit'". The 200 case stays as in FR-16.
- **[low]** In Flow 4, step 7 opens a Wallet from the Copy Test table and shows "← Back to Watchlist", but the Back link rule says it appears only when the page was opened from a Watchlist. (EXPERIENCE.md › Flow 4, Back link.) *Fix:* "← Back to Copy Test (Cut-off Date …)" when opened from the Copy Test. Update the Back link rule to match.

## Checked and fine

- **Banned words** ("guaranteed", "insider", "will win") appear nowhere about a Wallet, in either spec or mockup. "recommended" appears only in Flow 1's story, describing a post on X, not in the UI.
- **Exact PRD texts**, reproduced word for word:
  - FR-1: "No Polymarket history found for this address".
  - FR-11: the Exit PnL warning, and the limits note (all three points plus "This is not financial advice.").
  - FR-14: "Not available offline" (followed by an extra helpful sentence).
  - FR-16: the Minimum Luck Passes sentence (capitalised, with a full stop).
  - FR-22: the Flag text "Likely market maker (heuristic, may be wrong)".
  - FR-9: "above all 10,000 Simulations" and "below…".
  - The Copy Verdict values, and the FR-18 phrase "random groups did as well in 0.4% of draws".
  - The Copy Pool reason, "only 20 possible groups; at least 1,000 are needed".
- **FR-8 examples are correct**:
  - "about 1 time in 300", "about 1 time in 4" and "about 1 time in 2,500" (p = 0.0004).
  - "fewer than 1 time in 10,000" is used for the no-Simulation case.
  - "more than half the time" is used for p > 0.5.
- **The mockup chart is statistically right**:
  - The 80 bars sum to exactly 10,000, the mean is $0 and the spread is about $59k.
  - About 2,499 replays lie at or above $40,180 (z ≈ 0.68), which is a quarter, matching "about 1 time in 4" and the label "2,500 of 10,000 replays did this well or better".
  - The bars from the wallet's bar rightwards sum to 2,508. The spec correctly says not to use that sum.
- **"On average, luck alone lands at $0" is true.** Each outcome is drawn at its Entry Price, so E[s·(o − p)] = 0 per bet.
- **"The further it sits to the right of the bars, the harder it is to explain by luck" is true** for a given Wallet: further right means fewer Simulations at or above it, so a smaller p-value.
- **The chart text alternative** states the Real PnL and the FR-8 odds phrase (PRD §8).
- **The logo note** ("two thirds of a spread right of the middle, as at odds of about 1 in 4") matches a normal tail of about 25%.
- **Nothing is celebratory (SM-C3).** Check marks, trophies and green/red were rejected with reasons, and evidence dots are hidden from screen readers so the text carries the Verdict. The chart build-up is under a second and once per view, the empty Watchlist is stated as a valid result, and DESIGN.md › Brand & Style says plainly that a strong Verdict is evidence, not a recommendation.
- **"Copy wallet address" / "Copied"** clearly copies text to the clipboard. It does not read as copy-trading.
- **The Voice and Tone Do/Don't table** ("7 Wallets rated *Skilled (high confidence)*" vs "7 winners to copy") is exactly right in spirit.
