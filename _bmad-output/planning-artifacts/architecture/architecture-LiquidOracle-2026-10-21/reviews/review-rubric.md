# Independent spine review, good-spine rubric (2026-10-21)

Reviewer: independent subagent, read-only. It did not write the spine. Inputs: `ARCHITECTURE-SPINE.md`, `.memlog.md`, PRD `prd.md` and `addendum.md`, UX `EXPERIENCE.md` and `DESIGN.md`, `spike/FINDINGS.md`, `reviews/review-inline-gate.md`.

**Verdict:** the spine is close to buildable but not ready. Most ADs are sharp and enforceable. It still leaves two places where independently built stories would silently produce wrong Verdicts: how a lookup runs, and what the cache key is. It also has one internal contradiction (core cannot see the record types), and several UX and PRD requirements are either dropped or contradicted by its own rules.

Findings are ordered critical, high, medium, low. Pending PLAN CHANGE items already in the memlog are not listed as findings.

---

## Critical

### C1. How a single-Wallet lookup runs is undecided, and three parts of the spine disagree about it
- **Where:** AD-3, AD-5, AD-18, the deployment diagram, and the Capability map row for FR-1 and FR-2.
- **Problem:** AD-5 makes jobs only of "a Scan, Hold-up Test or Copy Test". So a lookup must fetch inside the web request. AD-3 supports that reading ("a web request and the worker each thinking they are under the limit"). The deployment diagram contradicts it: only `W -->|online only| P[Polymarket public APIs]`, so only the worker calls Polymarket. The UX needs a lookup that runs in the background. EXPERIENCE › State Patterns › Fetching says "In place of the Verdict card: … 'Fetching trades from Polymarket…' … When the Verdict arrives, it replaces this block and focus moves to the Verdict heading". The Accessibility Floor says a page change "made by the frontend without a full reload" moves focus. But AD-18 lets JavaScript do only "the chart build-up, the theme toggle and job-progress polling".
- **Failure scenario:** the lookup story fetches inside the request, as AD-5 implies. The browser then shows a blank loading tab for the whole fetch, so the Fetching state never appears. During a Scan, the shared 5/s limiter is also used by the worker, so the lookup can take minutes. Another story could follow the diagram and make the lookup a job instead. That lookup then waits in the "one at a time" queue behind a 70-minute Scan.
- **Fix:** add one AD for lookups. Recommended: a lookup is a fetch that runs in the background but is not queued behind Scan jobs. It could run on its own thread, or the worker could take lookups first. The Verdict page polls the same `/jobs/<id>/progress` contract. Add "lookup progress and swapping in the result" to AD-18's list of allowed JavaScript. Make the limiter fair, or give lookups priority, so a running Scan cannot starve a lookup. Then redraw the deployment diagram to match.

### C2. The cache key ignores the fetch window, so data fetched for one window is reused for another
- **Where:** AD-4, AD-7, AD-8, and the Deferred row "Table columns in `schema.sql`".
- **Problem:** AD-4 says "a Wallet's lists (positions, activity) are fresh for 24 hours; a lookup within that time makes 0 network calls". But what gets fetched depends on the window. AD-7 says before-part fetches use "`end` = cut-off + 30 days". AD-8 uses "the latest 2,000 overall" for a lookup and 2,000 on each side of the cut-off for a Scan. AD-10 limits activity rows "to the AD-8 window". Nothing records which window a stored list covers.
- **Failure scenario:** the user looks up Wallet X, which stores its latest 2,000 Positions. An hour later a Scan with Cut-off Date 2025-06-01 reaches X, finds fresh lists and makes 0 calls. It then rates X on Positions from 2026 instead of the Positions around June 2025. The opposite also happens. After a Scan, a lookup of X shows a Verdict built on a 2024–2025 window as if it were the whole Wallet. In both cases the Verdict is wrong and nothing on screen says so.
- **Fix:** add a rule to AD-4 that each stored Wallet fetch records what it covers (side, `start`/`end`, cap, complete or not). A cache hit counts only when the stored coverage contains the requested window. One function in `store.py` answers "is this window covered and fresh". This belongs in the spine, not in the deferred schema columns.

---

## High

### H1. `core` builds Positions from record types it is forbidden to import
- **Where:** AD-1 compared with AD-2 and AD-11. Structural Seed: `data/ # records.py …`.
- **Problem:** AD-2 puts the typed records in `data/records.py`. AD-11 says "`core/positions` is the only code that builds Positions" from positions lists and activity rows. AD-1's test "fails if it imports `liquidoracle.web`, `.services` or `.data`".
- **Failure scenario:** story A imports `liquidoracle.data.records` into `core/positions.py`, and the architecture test fails. Story B copies the types into `core`, and the two versions drift apart when a v2 field changes. That brings back the problem AD-2 exists to prevent.
- **Fix:** move the record types to a module with no app dependencies, for example `liquidoracle/records.py` or `core/types.py`. Let both `data` and `core` import it, and add that edge to the diagram and to AD-1's rule.

### H2. In Offline Mode with a key set, the app calls the language model
- **Where:** AD-13. PRD Glossary *Offline Mode*: "makes no network calls". FR-14.
- **Problem:** AD-13 chooses the model only by key: "Mock LLM Mode (no `ANTHROPIC_API_KEY`, or `--mock-llm`)". Offline Mode swaps only the Polymarket client. The diagram's `-->|online, key set|` label is not backed by any rule.
- **Failure scenario:** an examiner who has an Anthropic key in `.env` starts the app with `--offline`. Domain labels and Explanations then call `api.anthropic.com`, which breaks the Offline Mode promise. Under the network-blocked test (AD-17) the app raises `ModelUnavailable` and shows "Domains are not available" instead of the expected offline result.
- **Fix:** add to AD-13: "Offline Mode also gives `TemplateModel`, or a stored-labels-only model, whatever the key." Add a test that starts the app offline with a dummy key and sockets blocked.

### H3. The spine does not say which Positions the Watchlist is rated on, or which Verdict a Watchlist row opens
- **Where:** AD-8. PRD Glossary: *Before-Cut-off Passers* says "Unlike the Watchlist (whole history)". UJ-4. EXPERIENCE says a Watchlist or Copy Test row "opens its Verdict page", with "← Back to Watchlist (Cut-off Date …)".
- **Problem:** AD-8 defines three sets of Positions: before part, after part, and a lookup with no cut-off. The Watchlist's "whole history" rating matches none of them. Scan fetches cover only a window around the cut-off (AD-7, AD-8). The PRD itself also wavers: the Scan glossary entry says "Skill Tested, on its latest 2,000" before the cut-off.
- **Failure scenario:** the Scan story rates the Watchlist on the before part, which makes the Watchlist the same as the Passers. The Verdict page story rates the same Wallet on its latest 2,000 overall. The user clicks a Watchlist row marked *Skilled (high confidence)* and lands on a Verdict page that says *No evidence of skill*.
- **Fix:** decide in AD-8 (with a PRD memlog entry) which set the Watchlist uses. Also decide what a Verdict page opened from a Scan shows: the Scan's stored result for that set, labelled with the Cut-off Date, or a fresh lookup. Both pages must name the set they show.

### H4. How the Scan gets from candidates to 200 Wallets is not fixed, and AD-10/AD-12 make ranking need an activity read for every candidate
- **Where:** AD-9, AD-10, AD-12, FR-16.
- **Problem:** AD-9 says candidates come "for each Market resolved before the cut-off". It does not say which Markets or how many. The spike found "1000 rows, 995 wallets" on a single Market. AD-9 also says "each candidate's profit comes from its own positions". AD-12 makes Own Fees come only from activity rows and counts them "in the Scan ranking". So ranking even one candidate needs that Wallet's positions lists and an activity read.
- **Failure scenario:** with 100 Markets the candidate list has tens of thousands of Wallets. Each needs about 10 to 40 requests before ranking can even start, which takes days at 5/s. One story may sum the Market-anchored `realized_pnl` rows to pre-rank. That uses v2's fee-inclusive numbers, which AD-12 rejects. Another story fetches every candidate. The two produce different Top 200 lists.
- **Fix:** add a "Scan funnel" rule. It should say how Markets are chosen (by volume, how many), what number pre-ranks candidates cheaply, and at what step full Wallet data, activity and fees are fetched. It should also say whether fees affect the ranking or only the Skill Test. Put a request budget on each step.

### H5. AD-18's list of allowed JavaScript rules out interactions the UX requires
- **Where:** AD-18: "Plain JavaScript files … add only the chart build-up, the theme toggle and job-progress polling".
- **Problem:** EXPERIENCE requires several behaviours that need JavaScript. These are Copy address (clipboard, "Copied" for 2 s, the failure path), Chart explore (tooltip, the "Replays by result" slider, Esc to hide), the Wallet marker (pin, "Highlight on/off"), the favicon progress ring and tab title, and the lookup Fetching state (C1).
- **Failure scenario:** a story builds the chart slider. The reviewer applies the rule as written and rejects it, or the story drops the slider "per AD-18". Either way the WCAG 1.4.13 and keyboard requirements in the Accessibility Floor are not met.
- **Fix:** change the rule to: "JavaScript only enhances a page that is complete without it. Allowed files: theme, chart (build-up, explore, marker), copy-address, progress (jobs, lookup, tab title and favicon)." The README lists each file.

### H6. The Sample Dataset and live data share one database, so Offline Mode can show Wallets that are not in the sample
- **Where:** AD-13, AD-14, AD-4. Deployment diagram: a single `instance/liquidoracle.db`.
- **Problem:** `load-sample` fills the same SQLite file that the online app uses. AD-4 then serves cache hits with "0 network calls".
- **Failure scenario:** someone runs the app online and looks up Wallet Y. Later they start it with `--offline` and look up Y again. The cache hit shows Y's Verdict, but FR-14 requires "Not available offline". The other direction also breaks. A real sample Wallet loaded today counts as fresh for 24 hours online, so an online lookup shows the frozen, windowed sample data as live. Synthetic Markets with made-up `condition_id`s also land in the shared Market cache, which "never expires" (AD-4).
- **Fix:** use one database file per mode (for example `instance/offline.db` and `instance/live.db`), chosen by settings at startup. Another option is a source column that every read filters on. State it in AD-13 or AD-14.

### H7. A fetch that fails halfway can be stored and then trusted as fresh for 24 hours
- **Where:** AD-3, AD-4, AD-6.
- **Problem:** AD-3 raises `PolymarketUnavailable` after retries. Nothing says whether pages already stored stay, or whether the freshness time is written before the fetch is complete.
- **Failure scenario:** page 3 of 5 times out after pages 1 and 2 were saved. The next lookup within 24 hours finds "fresh" data and makes 0 calls. It then shows a full-looking Verdict built on 40% of the Wallet. FR-2's "offers the stored data" makes this worse, because it presents partial data as stored data.
- **Fix:** add a rule to AD-4. A Wallet fetch commits in one transaction, or writes its coverage and freshness row last, only when every page has arrived. A fetch that is not complete is never a cache hit.

---

## Medium

### M1. The activity window and the Position windows do not line up, and the activity cap has no number
- **Where:** AD-8, AD-10 ("activity rows … `start=1`, limited to the AD-8 window"), AD-11 ("the activity read hit its cap").
- **Problem:** the before part's window is set by Market resolution time. A Position that resolved inside the window may have been bought months before it. If the activity read is cut at the window's start, those buys are missing. The after part is "the first 2,000 after it, ordered by first entry time", and AD-10 takes the first entry time from activity rows. So you need the activity read to choose the window, and the window to limit the activity read. "Its cap" is not defined anywhere, and the Deferred table says the v2 cursor depth is untested.
- **Failure scenario:** one story starts activity at the earliest resolution time in the window. It undercounts shares held for long-held Positions, and those Positions enter the Skill Test with wrong *s*. Another story reads activity from `start=1`, which never finishes for market makers.
- **Fix:** state that the activity read for a window runs from the earliest first-entry time of the Positions in that window. Fix one numeric activity cap per Wallet as a setting tagged `[ASSUMPTION]`, and say what happens when it is hit (AD-11 already covers the result).

### M2. Number and phrase formatting has no single home, but FR-24 has to match the card's phrase exactly
- **Where:** Conventions ("Dates are formatted only in templates"), the Capability map ("FR-8 to FR-11 Verdict page | `web` templates, `services/lookup`"), and the FR-24 check in `services`.
- **Problem:** FR-24 checks that an Explanation "names the same Verdict and the same odds phrase as the card". The FR-8 odds phrase, the FR-18 copy phrase ("no random group did as well in 10,000 draws"), the Minimum Luck Passes rounding and the money format with "−" are all tested rules. Nothing says where they live.
- **Failure scenario:** the template formats "about 1 time in 300" in Jinja. `services` builds its own phrase for the check, and the two differ on rounding (for example "1 time in 2.2", PRD memlog open item). Correct Explanations then get replaced. The FR-8 tests also cannot reach Jinja logic.
- **Fix:** add a convention that every user-facing number phrase comes from one pure module (for example `core/phrases.py`), used by templates, the FR-24 check and the tests. Say the same for the luck chart: `core` returns the histogram bins and the exact "count ≥ Real PnL" that the marker sentence needs ("never summed from the bars", EXPERIENCE), and `SkillResult` stores them, or stores enough with the Seed to recompute them.

### M3. Domain labels are cached without recording their source, so keyword labels and model labels mix
- **Where:** AD-13, AD-16 ("Each label is stored with model ID and date and reused"). Memlog line 54: "the Sample Dataset ships its labels".
- **Problem:** the spine does not say whether a cache lookup matches on the model ID, or how keyword-rule labels are stored.
- **Failure scenario:** the app first runs without a key, so keyword labels are stored. Later a key is set, and AD-16 "reused, never silently redone" keeps the keyword labels forever. In the other direction, offline Mock mode shows the shipped Haiku labels under the "Keyword rules" tag, which is false.
- **Fix:** the label cache key is (Market, label source), where the source is a model ID or `keyword-rules`. The tag on the Domain table names the source of the labels actually shown.

### M4. Job states have no "failed" state, and the spine does not say what starts the Hold-up and Copy Tests
- **Where:** AD-5 (states `queued, running, done, interrupted, stopped`). DESIGN › Scan list shows status "Failed". EXPERIENCE gives the Hold-up and Copy Test pages no start button.
- **Failure scenario:** a bug (say a `KeyError`) inside the worker is not `PolymarketUnavailable`. The job stays `running`, and the next startup turns it into `interrupted`. Resume then repeats the crash forever, and the UI's "Failed" status has no state to come from. Separately, AD-5 speaks of "starting a … Hold-up Test or Copy Test". One story adds buttons the UX does not have. Another chains them after the Scan. Then it is unclear whether a Scan counts as "finished" (EXPERIENCE: "Results of a Scan that has not finished are not shown") before or after the 70-minute Copy Test.
- **Fix:** add a `failed` state (with the error logged and a message for the user) and say that Resume is not offered for it. State that a Scan job runs ranking, Skill Tests, Hold-up and Copy Test as phases of one job, or that they are chained jobs. Say which phase ends "finished", and what the progress `total` counts in each phase.

### M5. Departures from the PRD and UX that are not marked PLAN CHANGE in the memlog
- **AD-11 exclusions** (split/merge Markets, tokens found only in activity rows, incomplete share counts) change PRD FR-3. FR-3 says "A Position in a resolved Market … from either source is a Resolved Position", and only fully sold Positions are left out. Memlog lines 36, 41 and 45 have no PLAN CHANGE tag for FR-3.
- **AD-12** "The flagged fee counts as 0 in Real PnL" changes the Glossary's *Own Fees* ("as Polymarket recorded them") and FR-4. Memlog line 69 says it is "pending Edvard", but the spine states it as settled. AD-10, AD-11 and AD-12 also have no `[ADOPTED]` tag, while all the other ADs do.
- **New Verdict card content:** AD-11 says "The Verdict card shows each count". AD-12 says "how many fees were left out and their recorded total". AD-15 says the Seed is shown "on every results page". AD-9 says partial coverage "is shown". EXPERIENCE and DESIGN fix the honesty notes card as three columns with set contents. Only the "Keyword rules" tag is marked PLAN CHANGE for EXPERIENCE.md.
- **FR-3 resolution-time source:** AD-7 uses Gamma, but FR-3 says "the closed list's own timestamp". The memlog records the finding (line 26) but has no PLAN CHANGE tag for FR-3.
- **Fix:** add PLAN CHANGE memlog lines for FR-3, Glossary/FR-4 and EXPERIENCE/DESIGN (honesty notes card, Seed, coverage). Mark AD-12 `[ASSUMPTION]` until Edvard confirms it, and tag AD-10 and AD-11 `[ADOPTED]` if he already accepted them.

### M6. AD-11 does not say whether a Position with a share gap above 1% stays in the Skill Test
- **Where:** AD-11: "A positions-vs-activity share gap above 1% is stored as its size, not as a flag". Memlog line 39: "a share-count gap above 1% marks it, and the Verdict's honesty notes show the count".
- **Failure scenario:** the lookup story keeps such Positions, while the Hold-up story reads "data quality" as a reason to leave them out. Both call `core/positions`, but with different options, so the before and after parts differ.
- **Fix:** add one line saying it stays in the test or is left out, and which *s* is used (positions-list or activity count).

### M7. A Gamma 403 is not treated as retryable
- **Where:** AD-3 retries "Timeouts, 429 and 5xx". Memlog line 30: "Gamma /markets returned 403 (CloudFront) once; it worked earlier the same day."
- **Failure scenario:** a short CloudFront 403 in the middle of a Scan raises an exception that is not classified. That makes a raw error page (against the Conventions' "Pages never show a raw exception"), or a crashed job (M4).
- **Fix:** list how each HTTP status is handled. For example, 403 from Gamma or CloudFront is retried a few times and then becomes `PolymarketUnavailable`, and any other 4xx becomes a typed `PolymarketBadRequest` that is logged.

### M8. Negative-risk Markets are deferred, but they can make the stories disagree on shares held
- **Where:** Deferred: "How negative-risk (multi-outcome) Markets are represented". AD-10 lists activity types "TRADE, REDEEM, SPLIT, MERGE".
- **Problem:** v2 rows carry `negative_risk` (memlog line 26). Neg-risk Markets can create tokens through conversions, which are not buys. The Data API's activity types are reported to include a conversion type. AD-10's type list would not see it.
- **Failure scenario:** shares received by conversion have no BUY row. The shares-held count then disagrees with the positions list, so some stories exclude those Positions (AD-11, activity-only tokens) and others keep them with the wrong *s*.
- **Fix:** until the data story decides, state in AD-11 that a Position in a Market where the Wallet has any activity type other than TRADE or REDEEM is left out like split/merge, and counted.

### M9. Serving rules are missing: port 5000, binding and debug mode
- **Where:** deployment diagram `http://127.0.0.1:5000`. No AD covers serving.
- **Failure scenario:** on recent macOS, the AirPlay Receiver uses port 5000. An examiner following the README then gets "address in use" or a 403 page that does not come from the app. Separately, a story enables `debug=True` for convenience. The Werkzeug debugger allows code to be run from the browser, and AD-5 already notes that the reloader starts the app twice.
- **Fix:** add a serving rule. Bind only to 127.0.0.1, keep debug and the reloader off in `liquidoracle run`, and make the port a setting with a default that avoids 5000. Start the worker in the `run` command, not in the app factory, so tests that create the app do not start worker threads (see L3).

---

## Low

- **L1. AD-3 lets the pace go above the PRD's limit.** PRD s8 says "no more than 5 per second", but `POLYMARKET_REQUESTS_PER_SECOND` takes any value. Fix: reject values above 5 at startup.
- **L2. AD-1's test checks only `core`.** Its Prevents line also covers "two layers importing each other", but `web` importing `data` directly goes untested. Fix: the same test checks every layer's imports against the diagram.
- **L3. The spine does not say where the worker starts.** AD-5 says "the serving process" without naming the code. If the worker starts in the Flask app factory, every test that builds the app starts a worker that touches SQLite. Fix: name `__main__ run` as the only place it starts.
- **L4. Cut-off Date timezone.** Time is "UTC epoch seconds", but the form gives a local date, and "must be in the past" depends on the timezone. Fix: the Cut-off Date means 00:00 UTC on that date, and the form converts it in exactly one place.
- **L5. Gaps in the Capability map.** The PRD s8 row leaves out AD-6 (Database) and the Wording convention. FR-21 (Domain table) has no `web` entry. FR-22's inputs (buys of both outcomes, sells, buy-to-sell time) are missing from AD-10's table. The FR-13 Synthetic Wallet generator has no code location (`sample_data/` holds data, not code).
- **L6. The ER diagram is missing stored things the PRD needs.** These are the Hold-up group results, Copy Test results and Copy Sample, the Explanation, and the FR-24 replacement count (SM-7: "Each replacement is counted"). It also has a SCAN–JOB link but no link from a job to its Hold-up or Copy Test. Fix: add the entities. Columns can still be left to the stories.
- **L7. The banned-words list is unclear.** The convention says "One list in `services`" and cites PRD s8, which bans three words. EXPERIENCE adds an "also avoided" list ("top", "follow", "best" …) with exceptions ("top Wallets by profit", the Copy Test names). A test that scans every template would either miss those words or fail on the allowed exceptions. Fix: say which list the test enforces and how exceptions are written.
- **L8. Schema version mismatch.** `PRAGMA user_version` is fixed, but nothing says what happens when an older database meets a newer schema between stages: migrate, or drop the cache but keep Scans and Watchlists.
- **L9. FR-19 in Mock LLM Mode.** FR-15 says FR-19's tests pass with no key. If that includes the 80% hand-label check, the keyword rules can be tuned against the 50 hand labels. AD-16 prevents exactly that for the model. Fix: say that the 80% gate applies only to a real model, and that keyword rules are checked on different Markets.
