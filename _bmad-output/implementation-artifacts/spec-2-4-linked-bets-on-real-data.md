---
title: 'Story 2.4: Linked bets on real data'
type: 'feature'
created: '2026-11-21'
status: 'done'
baseline_commit: 'a8b129a2d6ac8988458c93f56d70c05a92a9d32a'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Skill Test draws each Market on its own, so the Markets of one negative-risk event (only one can win) can all "win" together in a Simulation, crediting a Wallet with independent evidence it does not have. The app also does not know which Markets share a Gamma event, so it cannot measure the links it does not couple. And a CONVERSION row names the event's `negRiskMarketID`, not a Market, so it is dropped from the window: on 0x091596 a converted NO bet (1,666.67 shares at $0.36) is tested as a held winner (about +$1,066).

**Approach:** Read each Market's Gamma event id and neg-risk id. In the Skill Test, the Markets of one neg-risk event share one U, each Market's win region laid end to end by price (disjoint while they fit), so each keeps its own win chance. Every result carries the share of tested Positions with an uncoupled event-mate. CONVERSION rows are kept and leave out their whole event.

## Boundaries & Constraints

**Always:** Every Position keeps a win chance equal to its Entry Price (FR-5 checks unchanged). A Wallet with no neg-risk Market draws exactly as before, so `expected.json` holds. In a neg-risk Market the Yes token wins on low draws; elsewhere the AD-20 token rule is unchanged. Win-region length of a neg-risk Market = max(p of its Yes Positions, 1 − p of its No Positions) over the test's Positions; regions laid in `condition_id` order, wrapping past 1 (overlap only when the lengths sum above 1). Plan documents changed before code. Same seed, same result.

**Never:** Card or page wording (Epic 3). Coupling across Wallets beyond what one `skill_test` call gets (Hold-up, Epic 4). Changing the Sliver, fee or share-gap rules.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Planted neg-risk event | 3 Yes Positions at 0.2, 0.3, 0.4 | in every Simulation at most one wins; each wins ≈ its price (10,000 runs) | N/A |
| No bets in a neg-risk event | No at 0.9, 0.8, 0.85 (regions 0.1, 0.2, 0.15) | at most one No loses per Simulation | N/A |
| Both sides in one neg-risk Market | Yes 0.3 and No 0.6 | region 0.4; Yes and No never both win | N/A |
| Regions sum above 1 | Yes 0.6, 0.7 | each still wins ≈ its price; overlap allowed | N/A |
| Conversion in an event | 0x091596's CONVERSION naming 0x5b32843a… | every Position in that event "split or merged", incl. the 21 conversion outputs | N/A |
| Uncoupled event-mates | 2 tested Positions in one non-neg-risk event, different Markets | both counted in the share | N/A |
| Neg-risk Market not Yes/No | `negRisk` true, outcomes not ["Yes","No"] | not coupled (counted in the share) | N/A |
| Old database | `user_version` 2 | rebuilt (fetched data only); offline needs `load-sample` again | N/A |

**Decisions (Edvard, 2026-11-21, all AI recommendations):** (1) Ladders slip, as epics.md allows: Gamma's `groupItemThreshold` is a display order, not a number, so detection would mean parsing question text; ladders are counted in the uncoupled share. (2) The 10 real Sample Wallets' share moves to Story 2.6, which first builds their Gamma records; 2.4 records it for the 5 fixture Wallets. (3) A CONVERSION leaves out every Position in its neg-risk event as "split or merged" (closes the 2.3 deferred item; the converted input cannot be told apart from the rest); Story 2.7's 0x091596 hand calculation follows. (4) Spec kept whole (about 1,750 tokens); subagents for review only.

</frozen-after-approval>

## Code Map

- `records.py` -- `Market` + `event_id: str|None`, `neg_risk_id: str|None` (set only when `negRisk` and outcomes are Yes/No; token_ids[0] is Yes). `Position` + `event_id`, `neg_risk_id`, `yes_side: bool`. `SkillTestResult` + `uncoupled_share: float`.
- `data/polymarket.py:517` `_market` -- parse `events[0].id`, `negRisk`, `negRiskMarketID`, `outcomes`.
- `data/window.py:91` -- keep CONVERSION rows whose `condition_id` is a window Market's `neg_risk_id`.
- `data/store.py` -- two `market` columns, `SCHEMA_VERSION` 3; `finish_snapshot` accepts a row naming a stored Market's `neg_risk_id`. `data/schema.sql` same.
- `data/sample_json.py` -- new Market keys (strict reader); regenerate `sample_data/synthetic/*.json` with `make-synthetic`.
- `core/positions.py` -- copy event fields onto each Position; a CONVERSION's neg-risk id marks all Markets with it as split. Add `UNCOUPLED_NOTE_ABOVE = 0.20` [ASSUMPTION], `uncoupled_share(ps)`, `mostly_uncoupled`.
- `core/skilltest.py` `_engine` -- one column per draw unit: ("event", neg_risk_id) or ("market", condition_id), sorted; per-Market draw V = (U − offset) mod 1 for neg-risk Markets. Split out a tests-visible win-matrix helper for the matrix rows.
- `tests/fixtures/cut_from_capture.py` -- add `negRisk`, `negRiskMarketID`, `outcomes`, `events` (id only) to `GAMMA_KEYS`; re-cut (from the git-ignored raw Gamma, no network).
- Planning: AD-20 (neg-risk layout, ladders slipped, remove the stale "sibling Markets" Deferred row), AD-11 conversion line, epics 2.4 + 2.6 (share for the 10) + 2.7 (0x091596 note), memlog, deferred-work entry closed.

## Tasks & Acceptance

**Execution:**
- [x] spine, `epics.md`, `.memlog.md`, `deferred-work.md` -- decisions, plan first.
- [x] `records.py`, `data/polymarket.py`, `data/store.py`, `data/schema.sql`, `data/sample_json.py`, `data/window.py` -- event fields end to end, CONVERSION kept.
- [x] `core/positions.py`, `core/skilltest.py` -- conversion exclusion, coupling, uncoupled share.
- [x] fixture script + re-cut; synthetic files regenerated.
- [x] tests -- every matrix row; parser, store round trip, window keeps the CONVERSION; fixtures' shares recorded.

**Acceptance Criteria:**
- Given `uv run pytest` with sockets blocked, then all pass and `expected.json` holds unchanged.
- Given `uv run liquidoracle load-sample`, then all Sample Wallets load.

## Implementation Notes

- Written by the main session directly (subagents for review only, Edvard's call). 766 tests pass (725 before), 1 online test deselected. `load-sample`: 1,005 Wallets in 18 s. `git diff` of `sample_data/synthetic/expected.json`: none; golden counts unchanged.
- Plan first: AD-11 (CONVERSION names its event), AD-20 (neg-risk layout, ladders slipped, stale "sibling Markets" Deferred row replaced), epics 2.4 + 2.6 + 2.7, two memlog entries, deferred-work item marked resolved, Epic 2 context updated. First commit a8b129a: Story 2.3 `done` (and the real `last_updated` time).
- **Deviation from the Code Map:** `uncoupled_share`, `mostly_uncoupled` and `UNCOUPLED_NOTE_ABOVE` live in `core/skilltest.py`, not `core/positions.py`: "coupled" is the Skill Test's draw rule, so the share is defined next to it, and `skill_test` stores it on the result.
- Real results on the fixtures (before -> after): 0x091596 tested 17 -> 14, Real PnL -$48,618.97 -> -$49,571.39, p 0.9404 -> 0.9873, the 21 share gaps + 1 "not explained" + 3 tested in the Romania event -> 25 "split or merged"; left out 36% -> 41%. Uncoupled share: 0x29306d 0/18, 0x091596 2/14 (Spain vs. Argentina O/U + Team to Advance), 0x0f4b0a 3/11 (three "The Boys" Markets, not neg-risk), 0x94884d 0/9, 0x729806 none tested. p moved slightly where neg-risk Markets are tested (0x29306d 0.4325 -> 0.4206): a different draw, same win chances.
- The CONVERSION row also had to pass the store's "every row names a stored Market" check: now accepted when it names a stored Market's `neg_risk_id`, refused otherwise (tested), and only for CONVERSION rows.
- Database schema 3 (two `market` columns + index): a version-2 file is rebuilt, so offline users run `load-sample` once more (tested with a Story 2.2 schema).
- Deliberate-break check before review: 21 changes, one per new rule. The first run missed two: "region = sum of a Market's two sides" (the both-sides test had room to spare) and "the window keeps any row naming an event". A test was added for each; all 21 now fail a test.
- AI slip: a bash heredoc with a long Python edit script broke on quoting (as the handoff warned); the edits were redone with the Edit tool.

## Spec Change Log

## Review Triage Log

Pass 1 (2026-11-21). Three reviewers: blind hunter (BH), edge-case hunter (EC), verification gap (VG). The diff left out the regenerated fixture and synthetic JSON (additions only; readable in the repo) and this spec (edge-case hunter only). 20 findings: 9 fix groups patched, 1 deferred, the rest rejected. No loopback.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| VG1 | No golden count for the coupled draw: a change of layout order or column order passes every test | medium | Pre-verified gap: GOLDEN had no linked Wallet; the linked tests are statistical | patch (group with BH7): golden `linked-event` = 3906 through `_engine` (two events, both sides, sum above 1, one uncoupled bet); breaking the region order or column order now fails it |
| BH7 | The coupling tests run `_simulated_wins`, a copy of the engine's ordering and generator setup | low | Confirmed: the sort key and generator call were repeated | patch (VG1 group): `_ordered` and `_generator` shared by both |
| VG-o1 | CONVERSION matching depends on the Yes/No coupling filter | maybe-false | 108 of 108 negRisk Markets in the raw Gamma data are Yes/No; whether any other shape exists is not shown | defer (group, unverified medium): settle in Story 2.6 on the 10 real Wallets' Gamma records |
| BH1 | Same as VG-o1 | maybe-false | Same | defer (VG-o1 group) |
| EC1 | Same as VG-o1 | maybe-false | Same | defer (VG-o1 group) |
| EC8 | Claim "CONVERSION rows are kept" holds only for coupled events | maybe-false | Same root | defer (VG-o1 group) |
| BH2 | A malformed `negRisk` / `negRiskMarketID` silently turns coupling and conversion handling off | low | Confirmed: returned None with no trace | patch (group with EC4): a negRisk Market left uncoupled is logged as a warning (raising would fail the whole lookup) |
| EC4 | Same as BH2 (non-text `negRiskMarketID`) | low | Same | patch (BH2 group) |
| EC3 | Yes/No outcomes with three token ids would take `token_ids[0]` as Yes | low | Confirmed reachable only on odd input; the fix is one condition | patch: coupled only with exactly two tokens; parser test case |
| BH5 | The builder lets a SPLIT or MERGE whose id equals an event id mark the whole event | low | Confirmed in `core/positions.py`: any Market-row id matched `neg_risk_id` (the window filters such rows, the core did not) | patch: a separate `conversion_events` set; new test |
| BH3 | `uncoupled_share` used a plain-string unit, `_Draws` the typed key | low | Confirmed: two definitions of "coupled" | patch: both use `_unit_key`; `_unit` removed |
| BH8 | The spine's AD-20 parent line still states the ladder rule as current | low | Confirmed | patch: "would share ... (slipped, see below)" |
| BH9 | The schema comment for `neg_risk_id` is incomplete | low | Confirmed | patch: says it is set only for Yes/No negRisk Markets and is the draw key |
| BH10 | The 27% fixture (over the 20% note) is not called out; the split-merge row only tests the empty case | low | Confirmed | patch: test comment; Implementation Notes already record the shares |
| BH4 | The uncoupled share ignores Slivers, which are simulated | low | True, but AD-20 defines the share over tested Positions, and a Sliver holds under 1 share (at most $1): its independent draw cannot move the Verdict | reject: adds a branch for a negligible case |
| EC6 | Same as BH4 | low | Same | reject |
| BH6 | `_check` does not check `yes_side` per Market | low | Not reachable: `yes_side` is set only by the builder from Gamma's token order, one token per Position | reject: guard for unseen input |
| EC5 | Same as BH6 | low | Same | reject |
| EC2 | `_yes_side` raises IndexError on a Market with no token ids | false | The Gamma parser refuses fewer than two tokens, and the Sample JSON files come only from our serializer; it would fail loudly, not silently | reject |
| EC7 | The store accepts a CONVERSION naming an event of a Market stored by another snapshot | false | `positions_near` keeps a CONVERSION only when one of its own window Markets has that `neg_risk_id`, so a snapshot's CONVERSION always names one of its own Markets | reject |

After the patches: 769 tests pass, 1 online test deselected; `load-sample` 1,005 Wallets (20 s); `expected.json` unchanged. Deliberate-break check rerun with 25 changes (4 new: any Market row marks an event, regions in reverse order, event columns after Markets, three-token Market coupled): all fail a test.

## Verification

**Commands:**
- `uv run pytest` -- expected: all pass (725 before, 769 after review).
- `uv run liquidoracle load-sample` -- expected: 1,005 Sample Wallets loaded.
