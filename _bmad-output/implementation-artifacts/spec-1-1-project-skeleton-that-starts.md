---
title: 'Story 1.1: Project skeleton that starts'
type: 'feature'
created: '2026-11-11'
status: 'in-progress'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '674e714f63ed9c9feea023ccdf0cf0292530507b'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The repository has plans but no app. An examiner cannot install or start anything, and later stories have no layout, settings, test rules or CI to build on.

**Approach:** Build the spine's Structural Seed as an installable uv project. It has one frozen settings object, a `liquidoracle` command (`run` serves a placeholder *Check a wallet* page, while `load-sample` and `make-synthetic` print "not built yet"), network-blocked tests with the import and environment rules, CI on 3 operating systems × 2 Python versions, and a README that gets someone from clone to the page.

## Boundaries & Constraints

**Always:**
- Use the spine's pinned versions exactly (`==`): Flask 3.1.3, requests 2.34.2, numpy 2.5.4, anthropic 1.17.0, python-dotenv 1.2.4, pytest 9.1.1, pytest-socket 0.8.1, and uv 0.13.4 (with `required-version`). The `uv.lock` is committed.
- `run` binds to 127.0.0.1 only, on `PORT` (default 8044), with `debug=False`, `use_reloader=False` and `load_dotenv=False`.
- Settings priority: command-line flag, then `.env`, then the default. Settings are built once and frozen. Only `__main__.py` and `settings.py` may touch `os.environ`, `os.getenv` or `dotenv`.
- The API key never appears in a `repr`, a log line or a page.
- Every test names its FR, AD, NFR or UX-DR in its docstring.

**Never:**
- No Polymarket, model, database or worker code. That belongs to Stories 1.6, 2.1 and 4.3.
- No real Lookup UI, design tokens or font. That belongs to Story 1.7.
- No README-commands CI job yet. It needs `load-sample` (Story 1.7).
- No `git add .` and no push or merge. Edvard opens the PR.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Start | `uv run liquidoracle run` | Serves `/` at 127.0.0.1:8044 with the title "Check a wallet · LiquidOracle" | N/A |
| Flag beats .env | `.env` PORT=9000, `--port 9100` | Port 9100 | N/A |
| Pace too high | `POLYMARKET_REQUESTS_PER_SECOND=6` | Exits with a non-zero code and one plain sentence naming the limit of 5 | No traceback |
| Bad value | `PORT=abc`, rate `0` or `x`, `OFFLINE=maybe` | Exits with a plain sentence naming the key | No traceback |
| Unbuilt command | `load-sample` / `make-synthetic` | Prints "not built yet" and exits 0 | N/A |
| Socket in a test | A test opens a socket | It fails with `SocketBlockedError` | N/A |
| Forbidden import | `import requests` planted in a `core` module | The rule checker reports it | N/A |

**Decisions (Edvard, 2026-11-11):** The README is rewritten in English as the LiquidOracle README, keeping the course and member line. The spec is kept whole (about 1,800 tokens, over the 1,600 soft limit). Review uses subagents.

</frozen-after-approval>

## Code Map

- `README.md` -- the Norwegian course-template text ("G44 — clude"). It is replaced in English (Decisions).
- `.gitignore` -- already ignores `.env`, `.venv/` and the caches. Add `instance/`.
- `.github/workflows/price-route-check.yml` -- existing. Leave it untouched. It shows Actions works in the org and uses action tags in `@vX.Y.Z` form.
- `spike/`, `_bmad/` -- never imported. Excluded from the rule tests.
- New: `src/liquidoracle/{__init__,__main__,settings,records}.py`, `{web,services,core,data}/__init__.py`, `tests/`.

## Tasks & Acceptance

**Execution:**
- [ ] `pyproject.toml`, `.python-version`, `uv.lock` -- the project, pinned deps, the `liquidoracle` script, the `uv_build` backend, `[tool.uv] required-version`, and pytest `addopts` (`--disable-socket`, `-m "not online"`, strict markers) with the `online` and `slow` markers -- AD-17 and the Stack.
- [ ] `src/liquidoracle/settings.py` -- a frozen dataclass and `load_settings(cli, env_file)` with validation and a `SettingsError` -- AD-13, NFR-6.
- [ ] `src/liquidoracle/__main__.py` -- argparse with the subcommands `run` (`--offline`, `--port`, `--seed`), `load-sample` and `make-synthetic`. It prints plain errors and exits 2 -- AD-23.
- [ ] `src/liquidoracle/web/__init__.py` + `templates/check.html` -- `create_app(settings)` with one placeholder route `/` -- AD-18, UX-DR8.
- [ ] Empty packages `records`, `core`, `data`, `services` with docstrings naming their layer -- AD-1.
- [ ] `.env.example` -- every key with a comment. `.gitignore` gets `+ instance/` -- NFR-5.
- [ ] `tests/conftest.py` -- the `--repetitions` option (default 100) and a `repetitions` fixture -- AD-17.
- [ ] `tests/online/conftest.py` -- marks every item there `online` -- AD-17.
- [ ] `tests/test_settings.py`, `tests/test_cli.py`, `tests/test_web.py` -- the matrix rows, the frozen object, the key hidden in `repr`, and the serving arguments passed to `app.run` (patched) -- AD-13, AD-23, NFR-6.
- [ ] `tests/test_architecture.py` -- an AST layer-import rule over `src/`, the environment-read rule, a planted-import check, socket blocking, and every test having a requirement ID -- AD-1, AD-17, NFR-7.
- [ ] `.github/workflows/tests.yml` -- matrix {ubuntu, windows, macos} × {3.12, 3.14}, `fail-fast: false`, `uv sync --locked`, `uv run pytest`. Linux 3.14 runs with `--repetitions 1000` -- NFR-2.
- [ ] `README.md` -- prerequisites (uv 0.13 or newer), install, start, the address, `.env` keys, how to run the tests -- NFR-1.

**Acceptance Criteria:**
- Given a fresh clone, when `uv sync` then `uv run liquidoracle run`, then `http://127.0.0.1:8044/` answers 200 with the placeholder page.
- Given `uv run pytest`, then every test passes with sockets blocked, and `tests/online/` is deselected.
- Given a push, then CI runs on 6 jobs, and one failing job fails the build.

## Design Notes

Choices the reader won't see, decided by the AI:
- **uv 0.13.4** everywhere. The local uv is upgraded from 0.12.15, and `required-version = ">=0.13"`. CI pins `0.13.4`, matching the spine, so no plan change is needed.
- **`.python-version` = 3.14.** That is the newest version in CI and the one installed locally.
- **`SEED` default 44** (the UX mockups show "Seed 44").
- **Process environment variables are not read.** Only flag, `.env` and default count, exactly as AD-13 says.
- Layer allowlist (beyond the standard library): `records` none; `core` numpy; `data` requests, anthropic; `services` none; `web` flask, jinja2. `settings` may be imported by every layer except `core` and `records`. `core` may not use the standard library's `socket`, `urllib`, `http`, `sqlite3` or `ssl`.

## Verification

**Commands:**
- `uv sync --locked` -- expected: no lock change
- `uv run pytest` -- expected: all pass
- `uv run liquidoracle run` + `curl http://127.0.0.1:8044/` -- expected: 200 and the page title
- `uv run liquidoracle run` with `POLYMARKET_REQUESTS_PER_SECOND=6` in `.env` -- expected: a plain message and exit 2
