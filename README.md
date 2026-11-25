# LiquidOracle

A local web app that tells whether a Polymarket wallet's results show **skill or luck**. It compares the wallet's real profit with 10,000 replays of pure luck and says how often a trader with no edge would do as well.

The app only reads public data. It never places orders, holds keys or touches a wallet's funds, and it is not financial advice.

Course project in **IBE160 Programmering med KI** at Høgskolen i Molde, autumn 2026. Group G44: Edvard Tokle.

> **Status: stage 1 done (25 November 2026).** Every stage 1 feature works, offline and live, and all tests pass. Next is stage 2 (plan: [`_bmad-output/planning-artifacts/epics.md`](_bmad-output/planning-artifacts/epics.md)).

What stage 1 does (FR-1 to FR-14 in the PRD):

- Look up a Wallet by address, with plain errors for a bad address or one with no Polymarket history (FR-1).
- Fetch its public data from Polymarket, store it and reuse it for 24 hours, and offer the stored data when Polymarket does not answer (FR-2).
- Turn its trades into bets, leaving out the ones the test cannot judge and saying why (FR-3), and work out its Real PnL (FR-4).
- Replay its resolved bets 10,000 times with no edge to get the odds (FR-5), and give a Verdict, or *Not enough data* below 30 resolved bets (FR-6, FR-10), the same every time for the same data and Seed (FR-7).
- Show it on a Verdict card (FR-8) with the luck chart and its text alternative (FR-9) and the honesty notes, "What this test can't see" (FR-11).
- Run with no network in Offline Mode (FR-14) on the committed Sample Dataset: 10 real Polymarket Wallets (FR-12) and the Synthetic Wallets, made-up Wallets whose right answers are known (FR-13).
- Work in the dark or light theme, by keyboard, without JavaScript, and on screens from 320 px wide.

How the success metrics were checked: [`docs/stage-1-check.md`](docs/stage-1-check.md). The accessibility check: [`docs/accessibility-check.md`](docs/accessibility-check.md).

## Prerequisites

- **uv 0.13 or newer**. uv installs the right Python (3.12 or newer) and all packages by itself, so you don't need Python installed first.
  - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - macOS and Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Check it with `uv --version`. If it's older than 0.13, run `uv self update`.
- **git**, to clone the repository.
- **Google Chrome or Microsoft Edge**, only for the browser tests (see *Tests*). The app itself works in any modern browser.

## Install and run

```sh
git clone https://github.com/IBE160-2026/G44-tokle.git
cd G44-tokle
```

Then the three commands, from the repository folder:

```sh
uv sync
uv run liquidoracle load-sample
uv run liquidoracle run --offline
```

1. `uv sync` installs Python and the packages.
2. `uv run liquidoracle load-sample` loads the Sample Dataset into the database `instance/offline.db` (about 110 MB, never committed). It regenerates the 1,000 coin-flipper Wallets in `instance/synthetic/coin-flippers/`, then loads them, the other Synthetic Wallets and the 10 real Wallets (1,015 in all). It takes about 20 to 40 seconds. It always writes `instance/offline.db`, never the live database, and running it again replaces each Wallet's stored data. After pulling a newer version, run it again if the app says the Sample Dataset is not loaded: a change to the database layout empties `instance/offline.db`.
3. `uv run liquidoracle run --offline` starts the app in Offline Mode: sample data only, no network.

Then open **http://127.0.0.1:8044** in your browser. Under *Sample Wallets*, the *Real Wallets* group lists 10 real Polymarket Wallets by short address; click one to see its Verdict card (what each one shows, and why, is in [`docs/real-wallets.md`](docs/real-wallets.md)). Under *Synthetic Wallets*, pick **Sharp trader**: its Verdict card says *Skilled (high confidence)*. The thin wallet shows *Not enough data*, and a coin-flipper shows *No evidence of skill*. The list shows one of the 1,000 coin-flippers; to check another, open any file in `instance/synthetic/coin-flippers/`, copy the value after `"address":` (0x and 40 characters) and paste it into the address field. Stop the app with `Ctrl+C`.

The app starts in the dark theme. The round button at the top right switches to the light theme and back, and the browser remembers your pick. Every page also works without JavaScript. The app has four small JavaScript files, in `src/liquidoracle/web/static/js/`:

- `theme.js`: the light and dark theme button.
- `copy-address.js`: the copy button next to the address on a Verdict page. It shows "Copied" for 2 seconds; if the browser refuses, it says so and selects the address, so you can press Ctrl+C (⌘C on a Mac). Without it, the button is not shown and you select the address yourself.
- `chart.js`: lets you explore the luck chart on a Verdict page. Point at a bar, or step through the bars with the arrow keys, to see its range and how many replays ended there; point at the blue *This Wallet* line, or Tab to it, to light up the replays that did as well or better. Click it or press Enter to keep that highlight on; click again or press Esc to clear it. The first time the chart comes into view, the bars grow in (not when your system is set to reduce motion). Without it, the chart and the sentence under it show the same result, just without the pointing.
- `progress.js`: while a live lookup fetches, it asks the app once a second whether the fetch is done, then shows the result in place and moves the keyboard focus to its heading. Without it, the page has a "Reload this page" link instead.

The app runs only on your own computer (it listens on 127.0.0.1, not on the network).

### Live lookups

```sh
uv run liquidoracle run
```

Without `--offline` the app reads Polymarket's public data (no key, no account, read-only, at most 5 requests a second). Paste a Wallet address: the one shown on the Wallet's Polymarket profile page, 0x and 40 characters. The page says "Checking 0x…" while a background thread fetches the Wallet's latest 2,000 resolved bets; that takes a few seconds for a small Wallet and can take a minute for a very large one. Then the Verdict card appears.

Live data is stored in `instance/live.db` (never committed). Looking up the same Wallet again within 24 hours uses the stored data and makes no network call; the card's "Data stored …" line says when it was fetched. If Polymarket does not answer, the page says so and offers the Wallet's older stored data, if there is any. An address that never traded on Polymarket gets "No Polymarket history found".

### Where the real Sample Wallets come from

The 10 real Wallets in `sample_data/real/` were built by one command from a raw capture of Polymarket's public data (23 October 2026, about 175 MB) that is **not in the repository**: it is kept outside it, with a SHA-256 file to prove it has not changed. The capture holds no market records (Gamma) and only the oldest 60,000 closed positions of one very large Wallet, so those were fetched once on 23 November 2026, read-only, into an additions file kept next to the capture with its own SHA-256 file. The command checks both files, runs the app's own rules on each Wallet, keeps only the rows those rules read, and checks that each written file gives exactly the same result. Running it twice gives identical files; nothing in `sample_data/` is edited by hand.

```sh
uv run liquidoracle build-sample <folder>/sample-capture-cutoff-2025-07-01.zip
```

You cannot run it without the capture, and you don't need it to run the app or the tests. `sample_data/real/dataset.json` records the default Cut-off Date (1 July 2025), both files' SHA-256 and how the set was built. Where the capture stopped reading a Wallet's trades (it read at most 150,000 rows each way from the Cut-off Date), the bets it cannot fully see are left out as "not fully read", as in a live lookup that hits the limit. For three of the 10 (0xd218e4, 0x63d43b and 0x729806) that is every bet, so their Verdict card shows *Not enough data*; [`docs/real-wallets.md`](docs/real-wallets.md) explains why.

`uv run liquidoracle make-synthetic` rebuilds the Synthetic Wallets: made-up Wallets whose correct answers are known in advance, used to check the Skill Test. Run it from the repository folder. It rewrites the five small Wallets in `sample_data/synthetic/` (committed; the output is identical every time, so `git status` stays clean) and writes 1,000 coin-flipper Wallets (about 90 MB) to `instance/synthetic/coin-flippers/`, which is never committed. You don't need it to run the app or the tests.

## Settings and keys

Settings come from three places. A command-line flag wins over `.env`, and `.env` wins over the default.

To change a setting, copy `.env.example` to `.env` in the project folder and edit it. `.env` is git-ignored and never committed.

```sh
cp .env.example .env              # macOS and Linux
Copy-Item .env.example .env       # Windows PowerShell
```

The app reads `.env` from the folder you start it in, so run the commands from the project folder. At start it prints which `.env` it read. Unknown keys get a warning and are ignored.

| Key | Default | What it does |
| --- | --- | --- |
| `PORT` | `8044` | Port the app serves on. Flag: `--port` |
| `SEED` | `44` | Random Seed for the Skill Test. The same Seed and data always give the same result. Flag: `--seed` |
| `POLYMARKET_REQUESTS_PER_SECOND` | `5` | Most requests per second sent to Polymarket. Above 5 is refused. |
| `OFFLINE` | `false` | Offline Mode: sample data only, no network. `true`/`false` (also `1`/`0`, `yes`/`no`, `on`/`off`). Flag: `--offline` |
| `ANTHROPIC_API_KEY` | empty | Key for the language model (stage 3, optional). Without it, template text is used. |

No key is needed to run the app or the tests. A bad value, such as a pace above 5, stops the start with a sentence that says what to fix.

## Tests

```sh
uv run pytest
```

Every test runs with the network blocked. Tests that need the real network live in `tests/online/` and are skipped unless you ask for them: `uv run pytest -m online --force-enable-socket tests/online`. Today that is two smoke tests, three requests in all (more if Polymarket is busy; no key): one reads the first page of one Sample Wallet's closed positions, the other checks that a random, never-used address gets empty lists rather than an error.

The browser tests in `tests/browser/` open the real pages in the Chrome or Edge already on your computer and check what only a browser can show. To run only them:

```sh
uv run pytest tests/browser
```

- **What they cover:** the copy button; that no page scrolls sideways at 320, 360, 600 and 900 px; that buttons do not move when your system is set to reduce motion; the Windows High Contrast (forced colours) rules; `chart.js` (`test_chart_script.py`: the chart's keys, the tooltip, the marker's highlight, the build-up, and the chart without the script); `progress.js` (`test_progress_script.py`: a live lookup polling, swapping in the Verdict or the matching message page, and giving up after 30 failed polls in a row); and the accessibility checklist (`test_checklist.py`: the 12 items walked with the keyboard only, reading the role, name, state and reading order a screen reader is given, plus every page with JavaScript off). What the checklist found, failures included, and what it cannot prove are in [`docs/accessibility-check.md`](docs/accessibility-check.md).
- **What they need:** Google Chrome or Microsoft Edge. Playwright for Python drives it; it is a test-only package that `uv sync` installs (about 40 MB, with its own small Node.js helper inside), and no browser is downloaded. Without Chrome or Edge the tests are skipped and the test summary says why; on GitHub Actions (where `CI` is set) a browser that cannot start fails the run instead, so a green check means they ran.
- **No network:** they start the app on 127.0.0.1 only, and any request a page makes to anywhere else is blocked and fails the test. The live-lookup tests run the app with its real job queue and worker in front of a stand-in Polymarket that serves the Synthetic Wallets from files.
- **Time:** each live-lookup test takes a few seconds; the slowest ones move the page's clock through 30 or more failed polls.

Checks marked `slow` repeat a whole test 100 times by default. `uv run pytest --repetitions 1000` runs them in full, as CI does on Linux with Python 3.14.

GitHub Actions runs the tests on every push on Windows, macOS and Linux with Python 3.12 and 3.14 ([`.github/workflows/tests.yml`](.github/workflows/tests.yml)). One more job runs the three commands above on a fresh checkout and checks that the sharp trader's page says *Skilled (high confidence)*. Which tests check the PRD's success metrics SM-1 and SM-2 is in [`docs/stage-1-check.md`](docs/stage-1-check.md).

## Project layout

```text
src/liquidoracle/   the app: __main__.py (commands), settings.py, records.py,
                    web/ (pages, templates, CSS, the bundled IBM Plex Serif font under the SIL Open Font License),
                    services/ (workflows), core/ (pure maths), data/ (outside systems)
tests/              automated tests; tests/browser/ drives Chrome or Edge, tests/online/ never runs in CI
sample_data/        Sample Dataset: real/ (10 real Wallets), synthetic/, and the hand labels
spike/              data spike and architecture probes (historical, not used by the app)
_bmad-output/       the plan: brief, PRD, UX, architecture, epics, story specs
docs/               the accessibility check, the stage 1 check, the real Wallets explained
docs/ai-logs/       logs of the AI sessions
```
