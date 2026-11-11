# LiquidOracle

A local web app that tells whether a Polymarket wallet's results show **skill or luck**. It compares the wallet's real profit with 10,000 replays of pure luck and says how often a trader with no edge would do as well.

The app only reads public data. It never places orders, holds keys or touches a wallet's funds, and it is not financial advice.

Course project in **IBE160 Programmering med KI** at Høgskolen i Molde, autumn 2026. Group G44: Edvard Tokle.

> **Status (Story 1.1):** the project skeleton. The app starts and shows a placeholder *Check a wallet* page. The wallet check itself is built in the next stories (plan: [`_bmad-output/planning-artifacts/epics.md`](_bmad-output/planning-artifacts/epics.md)).

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
uv sync
uv run liquidoracle run
```

Then open **http://127.0.0.1:8044** in your browser. Stop the app with `Ctrl+C`.

The app runs only on your own computer (it listens on 127.0.0.1, not on the network). Two more commands exist but aren't built yet: `uv run liquidoracle load-sample` (the Sample Dataset) and `uv run liquidoracle make-synthetic` (the Synthetic Wallets).

## Settings and keys

Settings come from three places. A command-line flag wins over `.env`, and `.env` wins over the default.

To change a setting, copy `.env.example` to `.env` in the project folder and edit it. `.env` is git-ignored and never committed.

| Key | Default | What it does |
| --- | --- | --- |
| `PORT` | `8044` | Port the app serves on. Flag: `--port` |
| `SEED` | `44` | Random Seed for the Skill Test. The same Seed and data always give the same result. Flag: `--seed` |
| `POLYMARKET_REQUESTS_PER_SECOND` | `5` | Most requests per second sent to Polymarket. Above 5 is refused. |
| `OFFLINE` | `false` | Offline Mode: sample data only, no network. Flag: `--offline` |
| `ANTHROPIC_API_KEY` | empty | Key for the language model (stage 3, optional). Without it, template text is used. |

No key is needed to run the app or the tests. A bad value, such as a pace above 5, stops the start with a sentence that says what to fix.

## Tests

```sh
uv run pytest
```

Every test runs with the network blocked. Tests that need the real network live in `tests/online/` and are skipped unless you ask for them: `uv run pytest -m online --force-enable-socket tests/online`.

GitHub Actions runs the tests on every push on Windows, macOS and Linux with Python 3.12 and 3.14 ([`.github/workflows/tests.yml`](.github/workflows/tests.yml)).

## Project layout

```text
src/liquidoracle/   the app: __main__.py (commands), settings.py, records.py,
                    web/ (pages), services/ (workflows), core/ (pure maths), data/ (outside systems)
tests/              automated tests; tests/online/ never runs in CI
sample_data/        Sample Dataset and the hand labels
spike/              data spike and architecture probes (historical, not used by the app)
_bmad-output/       the plan: brief, PRD, UX, architecture, epics, story specs
docs/ai-logs/       logs of the AI sessions
```
