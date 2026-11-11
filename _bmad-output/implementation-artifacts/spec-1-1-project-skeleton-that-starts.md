---
title: 'Story 1.1: Project skeleton that starts'
type: 'feature'
created: '2026-11-11'
status: 'in-review'
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
- [x] `pyproject.toml`, `.python-version`, `uv.lock` -- the project, pinned deps, the `liquidoracle` script, the `uv_build` backend, `[tool.uv] required-version`, and pytest `addopts` (`--disable-socket`, `-m "not online"`, strict markers) with the `online` and `slow` markers -- AD-17 and the Stack.
- [x] `src/liquidoracle/settings.py` -- a frozen dataclass and `load_settings(cli, env_file)` with validation and a `SettingsError` -- AD-13, NFR-6.
- [x] `src/liquidoracle/__main__.py` -- argparse with the subcommands `run` (`--offline`, `--port`, `--seed`), `load-sample` and `make-synthetic`. It prints plain errors and exits 2 -- AD-23.
- [x] `src/liquidoracle/web/__init__.py` + `templates/check.html` -- `create_app(settings)` with one placeholder route `/` -- AD-18, UX-DR8.
- [x] Empty packages `records`, `core`, `data`, `services` with docstrings naming their layer -- AD-1.
- [x] `.env.example` -- every key with a comment. `.gitignore` gets `+ instance/` -- NFR-5.
- [x] `tests/conftest.py` -- the `--repetitions` option (default 100) and a `repetitions` fixture -- AD-17.
- [x] `tests/online/conftest.py` -- marks every item there `online` -- AD-17.
- [x] `tests/test_settings.py`, `tests/test_cli.py`, `tests/test_web.py` -- the matrix rows, the frozen object, the key hidden in `repr`, and the serving arguments passed to `app.run` (patched) -- AD-13, AD-23, NFR-6.
- [x] `tests/test_architecture.py` -- an AST layer-import rule over `src/`, the environment-read rule, a planted-import check, socket blocking, and every test having a requirement ID -- AD-1, AD-17, NFR-7.
- [x] `.github/workflows/tests.yml` -- matrix {ubuntu, windows, macos} × {3.12, 3.14}, `fail-fast: false`, `uv sync --locked`, `uv run pytest`. Linux 3.14 runs with `--repetitions 1000` -- NFR-2.
- [x] `README.md` -- prerequisites (uv 0.13 or newer), install, start, the address, `.env` keys, how to run the tests -- NFR-1.

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

## Implementation Notes

- Implemented directly in the main session, not by an implementation subagent. Edvard had approved subagents for the review only.
- Commits: 968bb89 skeleton, f3e7849 tests, 9c0eb1f CI, plus a README commit. 70 tests pass on Python 3.14 and 3.12 locally, and a fresh clone runs `uv sync --locked`, the tests and the page.
- **Bug found in the AI's first version (smoke test):** on Windows, a second `liquidoracle run` bound the busy port 8044 without an error and reported "running", while the first copy kept getting every request. Fix: `port_in_use()` in `__main__` checks the port before starting and stops with a plain sentence. It is tested with a patched check (sockets are blocked in tests) and was verified by hand.
- Rule tests checked by planting real violations: `import requests` in `core/__init__.py` and `os.environ` in `web/__init__.py` each failed the suite, and so did turning off `--disable-socket`.
- The `os.environ` rule also refuses `dotenv` outside `__main__` and `settings`.
- `tests/online/test_online_marker.py` is a placeholder, so the "online tests are deselected" check has something to deselect until Epic 2 adds real online tests.
- The infinite pace value gets "must be a number" (found while writing the tests).

## Spec Change Log

## Review Triage Log

Review pass 1 (2026-11-11). Three subagent reviewers: blind (B), edge-case (E) and verification-gap (V). The diff excluded `uv.lock` and `_bmad-output/`.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| 1 | E: a real bind failure never reaches `except OSError` around `app.run` | medium | werkzeug/serving.py:765-786 catches OSError, prints its own plain message and calls `sys.exit(1)`, so the branch and its test (a faked `Flask.run` raising) were dead | patch: dead branch and test removed, comment added |
| 2 | B: `.env` `${VAR}` is filled in from the process environment | medium | Verified: `PORT=${PORT}` with process PORT=7000 gave 7000 | patch: `interpolate=False` + test |
| 3 | E: a non-UTF-8 `.env` gives a traceback | medium | Verified: a Latin-1 byte raised UnicodeDecodeError out of `load_settings` | patch: becomes a SettingsError + test |
| 4 | E: a `.env` with a UTF-8 BOM loses its first key | false | Verified: a BOM file with PORT=9000 gave 9000 | rejected |
| 5 | V: `--offline`/`--seed` never tested through `main()` | medium | `test_cli` passed only `--port`; a `store_true` regression would pass | patch: 2 tests through `main()` |
| 6 | V, B: `port_in_use` itself never runs in a test | medium | All 3 uses patch it out | patch: tests patching `socket.create_connection` |
| 7 | V: the installed `liquidoracle` command is never checked | low | The entry point is only exercised by hand | patch: CI step `uv run liquidoracle --help` |
| 8 | E, B: unknown `.env` keys are silently ignored | low | `POTR=9000` kept the default with no message | patch: warning naming the keys + test |
| 9 | E, B: `.env` is read from the current folder | low | True; the README cds into the project | patch: start logs which `.env` was read; README says so |
| 10 | E: check-then-bind race window | low | Needs a second program in the same half second | rejected for code; comment states the limit |
| 11 | E: a tiny pace like 1e-300 is accepted | low | Nothing uses the pace until Story 2.1's limiter | rejected (absurd input; the limiter story handles it) |
| 12 | E, B: `int()` accepts `8_044` and non-ASCII digits | low | Harmless: the result is the intended number | rejected |
| 13 | E: an unknown top-level module gives a KeyError or a silent pass | low | A stdlib-only module with an unknown layer passed | patch: reported as "unknown layer" + planted test |
| 14 | E: web/services may import sqlite3/socket | medium | `services` with `import sqlite3` passed; AD-2 and AD-6 keep I/O in `data` | patch: I/O stdlib only in `data` and `__main__`; list widened; planted tests |
| 15 | E, B: `importlib`, an aliased `os` or `getattr` bypass the rules | low | Needs deliberate evasion | rejected |
| 16 | E, B: the hard-coded "1 deselected" breaks when Epic 2 adds online tests | low | True | patch: regex + "no online test selected" |
| 17 | B: `--mock-llm` (AD-13) is missing | false for this story | Mock LLM Mode is FR-15, stage 3 (Epic 7); Story 1.1's acceptance criteria list only PORT, SEED, the pace, OFFLINE and the key | rejected (Epic 7) |
| 18 | B, V: the online placeholder test asserts True; the repetitions test is circular | low | True | patch: the placeholder checks its marker; new test checks the default of 100 and that 0, -1 and abc are refused |
| 19 | B: no `slow` test exists, so `--repetitions 1000` does nothing yet | low | True, but the first slow check is Story 1.4's | rejected (Story 1.4) |
| 20 | B: requirement IDs only checked for format | low | Checking them against the plan adds parsing of plan files | rejected |
| 21 | B: no AI log or memlog entries for the AI's choices | low | AI log and memlog are written at session end | handled at session end (not code) |
| 22 | B: CI runs twice per PR, no cache | low | True | patch: concurrency group, `enable-cache` |
| 23 | B: README lacks the copy command, the OFFLINE spellings and `--repetitions` | low | True | patch |
| 24 | B: unused `app.config` entry; `main()` treats any command as `run` | low | True | patch: entry removed, explicit `run` check |
| 25 | V: the `data` docstring disagrees with the rule (settings allowed) | low | True | patch: docstring |
| 26 | B: "cannot start" wording covers errors after start | low | Same root as #1; the branch is gone | patch (with #1) |

After the patches: 84 passed, 1 deselected (also with `--repetitions 1000`). The online test passes when selected. `uv sync --locked` is clean. The page answers 200. A pace of 6 and a busy port each exit 2 with a plain sentence.
