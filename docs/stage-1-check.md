# Stage 1 check: SM-1 and SM-2

Stage 1 (FR-1 to FR-14) closes with Story 3.5 (epics.md: "SM-1 and SM-2 are checked and noted", NFR-12). This note maps the PRD's two primary success metrics (PRD §7) to the tests and CI jobs that check them. Every test named here runs in `uv run pytest`, with the network blocked.

## SM-1: the Skill Test correctness tests pass

> All Skill Test correctness tests pass (hand-check, coin-flipper, sharp trader, favourite-buyer, thin wallet, reproducibility, independently calculated Real PnL). Validates FR-4 to FR-7.

| Named check | Test (file › test) | What it checks |
| --- | --- | --- |
| Hand-check | `tests/test_synthetic.py` › `test_hand_check_exact_p_is_one_in_1024`; `tests/test_skilltest.py` › `test_hand_check_p_value_on_the_engine` | The hand-check Wallet's exact p-value (1 in 1,024, worked out by hand) and the engine's p-value for it, within the range set in `sample_data/synthetic/expected.json`. |
| Coin-flipper | `tests/test_skilltest.py` › `test_coin_flippers_rarely_look_skilled` (marked `slow`: 100 repetitions, 1,000 on CI's Linux / Python 3.14 job) | Over the coin-flippers (100 resolved bets each, at prices from 10¢ to 90¢, with no edge), at most 7% may get p < 0.05 (*Likely skilled* or better) and at most 2% may get p < 0.01 (*Skilled (high confidence)*). The limits are in `sample_data/synthetic/expected.json` (`coin_flippers`); about 5% is expected by design. |
| Sharp trader | `tests/test_skilltest.py` › `test_synthetic_wallets_get_their_expected_verdict[sharp-trader]` | *Skilled (high confidence)*, p below the bound in `expected.json`. |
| Favourite-buyer | `tests/test_skilltest.py` › `test_synthetic_wallets_get_their_expected_verdict[favourite-buyer]` | *No evidence of skill*: buying favourites at fair prices is not skill. |
| Thin wallet | `tests/test_skilltest.py` › `test_synthetic_wallets_get_their_expected_verdict[thin-wallet]` and `test_29_resolved_positions_give_not_enough_data_and_30_a_verdict` | 29 resolved bets give *Not enough data*; 30 give a Verdict (FR-6, FR-10). |
| Reproducibility | `tests/test_skilltest.py` › `test_same_data_and_seed_give_the_identical_result`, `test_position_order_does_not_change_the_result`, `test_golden_count_is_reproduced`, `test_two_hash_seeds_give_identical_results` | The same data and Seed give the identical p-value and Verdict, whatever the order of the bets or Python's hash seed (FR-7). |
| Independently calculated Real PnL | `tests/test_skilltest.py` › `test_real_pnl_matches_the_hand_values`; `tests/test_reference_pnl.py` › `test_app_real_pnl_equals_the_independent_reference_to_the_cent`, `test_app_counts_and_own_fees_equal_the_independent_reference` | Real PnL equals the hand values for the Synthetic Wallets, and equals, to the cent, the result of reference scripts that import only Python's standard library (never the app) for real Wallets (FR-4). |

Result: all of them pass in the full run of 25 November 2026 (see *The run* below).

## SM-2: the app and the tests run from the README with no network and no keys

> The examiner can run the app and the tests from the README with no network and no keys. Validates FR-12 to FR-14.

- **No network in the tests.** `pyproject.toml` runs every test with `--disable-socket` (pytest-socket), so a test that tried to reach the network would fail. The browser tests open sockets to 127.0.0.1 only (`tests/browser/conftest.py`), and any request a page makes elsewhere is blocked and fails the test (`tests/browser/pages.py`). Tests that need the real network live in `tests/online/` and never run unless asked for.
- **No network in the app.** Offline Mode reads only the committed Sample Dataset and the local database (FR-12, FR-14): `tests/test_offline.py` and `tests/test_architecture.py` › `test_nothing_else_branches_on_the_mode`.
- **The README's commands, exactly as written.** The CI job *README commands · Offline Mode* (`.github/workflows/tests.yml`, job `readme`) runs `uv sync`, `uv run liquidoracle load-sample` and `uv run liquidoracle run --offline` on a fresh checkout, then opens the sharp trader's Verdict page and checks that it says *Skilled (high confidence)*.
- **No keys.** No test and no stage 1 feature needs a key: `.env` is optional, and the only key, `ANTHROPIC_API_KEY`, is for stage 3 (README › Settings and keys). CI runs with no secrets set. `tests/test_settings.py` checks that `.env.example` lists every key and that the key never shows in the settings' printout.

## The run

- **Locally (Windows 11, Python 3.14, Chrome), 25 November 2026:** `CI=true uv run pytest -rs`: 1,207 tests passed, none skipped.
- **CI (Windows, macOS and Linux × Python 3.12 and 3.14, plus the README job):** runs on the push of the Story 3.5 part B branch; the run is linked from its pull request. Stage 1 counts as closed when all seven jobs are green.
