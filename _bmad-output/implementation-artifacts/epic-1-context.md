# Epic 1 Context: Check a synthetic Wallet offline

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

An examiner clones the repository, runs three README commands (`uv sync`, `uv run liquidoracle load-sample`, `uv run liquidoracle run --offline`), picks a Synthetic Wallet in Offline Mode and sees a correct Verdict card, while the tests pass in CI on Windows, macOS and Linux. The Skill Test is the riskiest part, so it is built and proven first on made-up Wallets whose correct answers are fixed before the test exists. Epic 1 is the base of stage 1, which must stand alone as a working app and never slips. Target dates are 5 to 10 November 2026. If the epic runs late, only the visual polish of Story 1.7 moves later.

## Stories

- Story 1.1: Project skeleton that starts
- Story 1.2: Positions from fills
- Story 1.3: Synthetic Wallets with known answers
- Story 1.4: The Skill Test
- Story 1.5: Number phrases in one place
- Story 1.6: Offline Mode and loading the Sample Dataset
- Story 1.7: Check a wallet and see its Verdict card

## Requirements & Constraints

- The app runs locally only. It is a web page served on the user's own laptop at 127.0.0.1, port 8044 by default, with debug and the reloader off. Nothing is hosted.
- It is read-only toward Polymarket: only GET requests to public endpoints, no orders, no keys and nothing that touches funds. Epic 1 makes no network calls at all.
- It is runnable from the README: from a fresh clone with uv installed, the app starts in at most three documented commands. The README lists the prerequisites, the exact commands, the address to open and how keys are set in `.env`.
- Secrets: the model key lives only in `.env`, which is never committed. `.env.example` lists every key, and the key is never logged.
- Pacing toward Polymarket is at most 5 requests per second. The setting can be turned down, and a value above 5 is refused at startup.
- The core is testable: the Skill Test code holds no network, web or model code. Every requirement with consequences has at least one automated test, and each test names the FR or AD it checks.
- Data lives in SQLite (a course requirement). Offline runs use `instance/offline.db` and live runs use `instance/live.db`. Both are git-ignored.
- Skill Test facts: Real PnL = Σ s·(o − p) − Own Fees. There are 10,000 Simulations, and p = (1 + count ≥ real) / 10,001. The Verdict thresholds are p < 0.01 *Skilled (high confidence)* and p < 0.05 *Likely skilled*, otherwise *No evidence of skill*. Below 30 Resolved Positions the Verdict is *Not enough data*. The same data and Seed always give the same result.
- Positions (Edvard, 2026-11-11): Entry Price is the share-weighted average of the BUY fills, never Polymarket's `avg_price`. A Sliver (under 1% of bought shares and fewer than 1 share held) keeps its money in Real PnL and every Simulation but is not counted as a bet, tested or left out.
- Wording: never "guaranteed", "insider" or "will win" about a Wallet, plus the UX list of avoided words. A test enforces this over every template and fixed text.

## Technical Decisions

- **Stack (pinned):** Python >= 3.12, run on 3.12 and 3.14 in CI. uv 0.13.4 with a committed `uv.lock`. Flask 3.1.3 (with Jinja2), requests 2.34.2, numpy 2.5.4, anthropic 1.17.0, python-dotenv 1.2.4, pytest 9.1.1, pytest-socket 0.8.1. GitHub Actions use setup-uv v10.3.0 and checkout v7.0.1. SQLite comes from the standard library's `sqlite3`.
- **Layout:** `src/liquidoracle/` holds `__main__.py` (flags, settings, the commands `run`, `load-sample` and `make-synthetic`), `settings.py`, `records.py`, and the packages `web/`, `services/`, `core/` and `data/`. Next to it are `sample_data/`, `tests/` (with `tests/online/`, which never runs in CI), `.github/workflows/`, `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example` and `README.md`. `spike/` is historical and never imported.
- **Layers, imports one way:** web → services → core/data → records. `core` imports only `records`, the standard library and numpy. A test parses every module and fails on any import the diagram does not allow.
- **Settings:** one frozen object, built once at startup. The priority is command-line flag, then `.env`, then the default. Nothing outside `__main__` and `settings` reads the environment. Settings are passed down, and `core` receives none.
- **Modes are swaps set at startup:** Offline Mode gives `OfflineClient` and `instance/offline.db`. Mock LLM Mode gives `TemplateModel`. No other code branches on a mode.
- **Serving:** `liquidoracle run` binds to 127.0.0.1 on `PORT`, with no debug, no reloader and `load_dotenv=False`. It is the only place the worker thread starts.
- **Tests:** `addopts = "--disable-socket"`, so every test runs network-blocked. Online tests are marked and excluded. CI runs `uv sync --locked` and `uv run pytest` on 3 operating systems × 2 Python versions, plus one job that runs the README commands. 1,000-repetition checks carry a `slow` marker: they run in full on Linux with Python 3.14 and with 100 repetitions elsewhere, set by one option. Determinism checks and a golden result run on every job.
- **Randomness:** an explicit Seed, positions sorted before drawing, and per-unit generators from `SeedSequence` with a sha256 spawn key. Never `random`, numpy's global state or `hash()`.
- **Money:** a `float` in USD, rounded only for display, and tests compare to the cent. The Skill Test's tie count alone uses whole-cent integers. The Real PnL that is shown is the exact sum.
- **Data access:** only `data/store.py` runs SQL, with WAL, a busy timeout, one connection per thread and `BEGIN IMMEDIATE`. One `schema.sql` with `PRAGMA user_version`. Snapshots carry a `fetch_id` and become visible in one final step.
- **Number phrases** all come from `core/phrases.py`.
- **Pages** are rendered on the server with Jinja2 and work without JavaScript. Plain JS files only enhance them. IBM Plex Serif is bundled, and nothing is loaded from the internet.

## UX & Interaction Patterns

- The *Check a wallet* page (`/`) has the eyebrow "SKILL OR LUCK", a title, a lede and an address field card (label "Wallet address", button "Check wallet") with focus in the field. Errors appear under the field.
- In Offline Mode, the "Offline Mode · sample data only" pill shows on every page, and a Sample Wallets list shows on the lookup page.
- The Verdict page `/wallet/0x…` has the Verdict hero as its main heading, read as "Verdict: …". It shows the odds phrase and the stats line "N resolved bets · Real PnL $X". *Not enough data* has a dashed hero and no chart.
- Every page has "Skip to content" as the first Tab stop, the top bar with the logo and *Check a wallet*, one main heading, the English language attribute, and the tab title "Check a wallet · LiquidOracle". Colours and type come from the DESIGN.md tokens.

## Cross-Story Dependencies

- 1.1 sets up the skeleton, settings, test rules and CI that every later story builds on.
- 1.3's Synthetic Wallets and expected-result fixtures come before 1.4's Skill Test, which must match them.
- 1.2's Position builder feeds 1.3's checks and 1.4.
- 1.5 comes before 1.7, because the card needs its phrases.
- 1.6 (store, OfflineClient, load-sample) is needed by 1.7's pages and by the CI README-commands job.
- Epic 2 adds the live Polymarket client behind the same client interface as `OfflineClient`.
