# LiquidOracle

A local web app that tells whether a Polymarket wallet's results show **skill or luck**. It compares the wallet's real profit with 10,000 replays of pure luck and says how often a trader with no edge would do as well.

The app only reads public data. It never places orders, holds keys or touches a wallet's funds, and it is not financial advice.

Course project in **IBE160 Programmering med KI** at Høgskolen i Molde, autumn 2026. Group G44: Edvard Tokle.

> **Status (Story 2.5):** stage 1's core works in Offline Mode and live. Offline, you can check the Synthetic Wallets (made-up Wallets whose right answers are known). Live, you can paste any Polymarket address and get its Verdict card. The 10 real Sample Wallets come in Story 2.6; the luck chart and the honesty notes come in Epic 3 (plan: [`_bmad-output/planning-artifacts/epics.md`](_bmad-output/planning-artifacts/epics.md)).

## Prerequisites

- **uv 0.13 or newer**. uv installs the right Python (3.12 or newer) and all packages by itself, so you don't need Python installed first.
  - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - macOS and Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Check it with `uv --version`. If it's older than 0.13, run `uv self update`.
- **git**, to clone the repository.

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
2. `uv run liquidoracle load-sample` loads the Sample Dataset into the database `instance/offline.db` (about 75 MB, never committed). It regenerates the 1,000 coin-flipper Wallets in `instance/synthetic/coin-flippers/`, then loads them and the other Synthetic Wallets. It takes about 15 to 30 seconds. It always writes `instance/offline.db`, never the live database, and running it again replaces each Wallet's stored data. After pulling a newer version, run it again if the app says the Sample Dataset is not loaded: a change to the database layout empties `instance/offline.db`.
3. `uv run liquidoracle run --offline` starts the app in Offline Mode: sample data only, no network.

Then open **http://127.0.0.1:8044** in your browser. Under *Sample Wallets*, pick **Sharp trader**: its Verdict card says *Skilled (high confidence)*. The thin wallet shows *Not enough data*, and a coin-flipper shows *No evidence of skill*. The list shows one of the 1,000 coin-flippers; to check another, open any file in `instance/synthetic/coin-flippers/`, copy the value after `"address":` (0x and 40 characters) and paste it into the address field. Stop the app with `Ctrl+C`.

The app starts in the dark theme. The round button at the top right switches to the light theme and back, and the browser remembers your pick. Every page also works without JavaScript. The app has two small JavaScript files, in `src/liquidoracle/web/static/js/`:

- `theme.js`: the light and dark theme button.
- `progress.js`: while a live lookup fetches, it asks the app once a second whether the fetch is done, then shows the result in place and moves the keyboard focus to its heading. Without it, the page has a "Reload this page" link instead.

The app runs only on your own computer (it listens on 127.0.0.1, not on the network).

### Live lookups

```sh
uv run liquidoracle run
```

Without `--offline` the app reads Polymarket's public data (no key, no account, read-only, at most 5 requests a second). Paste a Wallet address: the one shown on the Wallet's Polymarket profile page, 0x and 40 characters. The page says "Checking 0x…" while a background thread fetches the Wallet's latest 2,000 resolved bets; that takes a few seconds for a small Wallet and can take a minute for a very large one. Then the Verdict card appears.

Live data is stored in `instance/live.db` (never committed). Looking up the same Wallet again within 24 hours uses the stored data and makes no network call; the card's "Data stored …" line says when it was fetched. If Polymarket does not answer, the page says so and offers the Wallet's older stored data, if there is any. An address that never traded on Polymarket gets "No Polymarket history found".

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

Checks marked `slow` repeat a whole test 100 times by default. `uv run pytest --repetitions 1000` runs them in full, as CI does on Linux with Python 3.14.

GitHub Actions runs the tests on every push on Windows, macOS and Linux with Python 3.12 and 3.14 ([`.github/workflows/tests.yml`](.github/workflows/tests.yml)). One more job runs the three commands above on a fresh checkout and checks that the sharp trader's page says *Skilled (high confidence)*.

## Project layout

```text
src/liquidoracle/   the app: __main__.py (commands), settings.py, records.py,
                    web/ (pages, templates, CSS, the bundled IBM Plex Serif font under the SIL Open Font License),
                    services/ (workflows), core/ (pure maths), data/ (outside systems)
tests/              automated tests; tests/online/ never runs in CI
sample_data/        Sample Dataset and the hand labels
spike/              data spike and architecture probes (historical, not used by the app)
_bmad-output/       the plan: brief, PRD, UX, architecture, epics, story specs
docs/ai-logs/       logs of the AI sessions
```
