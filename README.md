# LiquidOracle

A local web app that tells whether a Polymarket wallet's results show **skill or luck**. It compares the wallet's real profit with 10,000 replays of pure luck and says how often a trader with no edge would do as well.

The app only reads public data. It never places orders, holds keys or touches a wallet's funds, and it is not financial advice.

Course project in **IBE160 Programmering med KI** at Høgskolen i Molde, autumn 2026. Group G44: Edvard Tokle.

> **Status: stage 1 done (25 November 2026), and the stage 2 minimum done (27 November 2026).** Every stage 1 feature works, offline and live. Of stage 2, the Scan and the Hold-up Test work offline on the Sample Dataset, and the Hold-up Test has been run on a live Scan of 200 real Wallets (27 November 2026, after a 10-Wallet trial; result under *The Hold-up Test on a live Scan* below); the Copy Test is not done yet (plan: [`_bmad-output/planning-artifacts/epics.md`](_bmad-output/planning-artifacts/epics.md)). All tests pass.

What stage 1 does (FR-1 to FR-14 in the PRD):

- Look up a Wallet by address, with plain errors for a bad address or one with no Polymarket history (FR-1).
- Fetch its public data from Polymarket, store it and reuse it for 24 hours, and offer the stored data when Polymarket does not answer (FR-2).
- Turn its trades into bets, leaving out the ones the test cannot judge and saying why (FR-3), and work out its Real PnL (FR-4).
- Replay its resolved bets 10,000 times with no edge to get the odds (FR-5), and give a Verdict, or *Not enough data* below 30 resolved bets (FR-6, FR-10), the same every time for the same data and Seed (FR-7).
- Show it on a Verdict card (FR-8) with the luck chart and its text alternative (FR-9) and the honesty notes, "What this test can't see" (FR-11).
- Run with no network in Offline Mode (FR-14) on the committed Sample Dataset: 10 real Polymarket Wallets (FR-12) and the Synthetic Wallets, made-up Wallets whose right answers are known (FR-13).
- Work in the dark or light theme, by keyboard, without JavaScript, and on screens from 320 px wide.

Stage 2 so far (FR-16 and FR-17; the Copy Test, FR-18, is not built):

- **Scan** (FR-16): *Scan wallets* in the top bar starts a Scan of the top Wallets by profit made before a Cut-off Date you choose, shows its progress, and can resume one that was stopped.
- **Watchlist** (FR-16): when a Scan has finished, its number in the Watchlist column of *Your Scans* opens its Watchlist: the Wallets rated *Skilled (high confidence)*, sorted by p-value, and how many would pass by luck alone. Click a Wallet there to see its Verdict for that Scan.
- **Hold-up Test** (FR-17): next to the Watchlist, a finished Scan has a *Hold-up Test* tab. It tests the Wallets that passed before the Cut-off Date again, as one group, on the bets they made after it, beside a Comparison Group of the Wallets that did not pass. What it shows on the Sample Dataset, and what that can and cannot tell you, is under *The Hold-up Test on the Sample Dataset* below. What it showed on a live Scan of 200 real Wallets is under *The Hold-up Test on a live Scan*.
- **In Offline Mode**, *Start Scan* scans the Sample Dataset with its Cut-off Date, 1 July 2025. It takes about a minute and puts at least the sharp trader, steady sharp, forecaster and speed trader on the Watchlist, next to the few coin-flippers that pass by luck alone (Story 4.6). It also scans 8 of the 10 real Wallets, found through the same Markets they were first picked from (Story 4.7); 0xd218e4 and 0x63d43b are left out, see *Where the real Sample Wallets come from*.

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
2. `uv run liquidoracle load-sample` loads the Sample Dataset into the database `instance/offline.db` (about 110 MB, never committed). It regenerates the 1,000 coin-flipper Wallets in `instance/synthetic/coin-flippers/`, then loads them, the other Synthetic Wallets and the 10 real Wallets (1,018 in all). It takes about 20 to 40 seconds. It always writes `instance/offline.db`, never the live database, and running it again replaces each Wallet's stored data. After pulling a newer version, run it again if the app says the Sample Dataset is not loaded: a change to the database layout empties `instance/offline.db`.
3. `uv run liquidoracle run --offline` starts the app in Offline Mode: sample data only, no network.

Then open **http://127.0.0.1:8044** in your browser. Under *Sample Wallets*, the *Real Wallets* group lists 10 real Polymarket Wallets by short address; click one to see its Verdict card (what each one shows, and why, is in [`docs/real-wallets.md`](docs/real-wallets.md)). Under *Synthetic Wallets*, pick **Sharp trader**: its Verdict card says *Skilled (high confidence)*. The thin wallet shows *Not enough data*, and a coin-flipper shows *No evidence of skill*. The list shows one of the 1,000 coin-flippers; to check another, open any file in `instance/synthetic/coin-flippers/`, copy the value after `"address":` (0x and 40 characters) and paste it into the address field. Stop the app with `Ctrl+C`.

The app starts in the dark theme. The round button at the top right switches to the light theme and back, and the browser remembers your pick. Every page also works without JavaScript. The app has six small JavaScript files, in `src/liquidoracle/web/static/js/`:

- `theme.js`: the light and dark theme button.
- `copy-address.js`: the copy button next to the address on a Verdict page. It shows "Copied" for 2 seconds; if the browser refuses, it says so and selects the address, so you can press Ctrl+C (⌘C on a Mac). Without it, the button is not shown and you select the address yourself.
- `chart.js`: lets you explore the luck chart on a Verdict page. Point at a bar, or step through the bars with the arrow keys, to see its range and how many replays ended there; point at the blue *This Wallet* line, or Tab to it, to light up the replays that did as well or better. Click it or press Enter to keep that highlight on; click again or press Esc to clear it. The first time the chart comes into view, the bars grow in (not when your system is set to reduce motion). Without it, the chart and the sentence under it show the same result, just without the pointing.
- `progress.js`: while a live lookup fetches, it asks the app once a second whether the fetch is done, then shows the result in place and moves the keyboard focus to its heading. Without it, the page has a "Reload this page" link instead.
- `scans.js`: on the Scans page, it updates the rough time estimate as you change the Number of Wallets, shows the "very few bets" warning as soon as you pick a recent Cut-off Date, and, while a Scan runs, moves the progress bar and counts in the tab title ("84/200 · Scan · LiquidOracle") once a second, telling a screen reader at most every 10%. Without it, the warning shows after you press "Start Scan" (press it again to start), and you reload the page to see how far a Scan got.
- `tag-tip.js`: on a Watchlist, Esc hides the "Not fully read" tag's explanation while you point at or focus the tag. Without it, the explanation still shows on hover and focus, and a screen reader reads it with the tag.

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

For the offline Scan (Story 4.7), the same command also stores 8 of the real Wallets' bets resolved before the Cut-off Date and bought after it, and checks each file gives those two parts exactly as the capture did. It writes `sample_data/real/funnel-markets.json` from the capture's own Scan funnel: the top 100 Markets by volume resolved in the 90 days before 1 July 2025, which is how the real Wallets were picked, with these Wallets' rows on each Market as Polymarket listed them. So an offline Scan finds them the way a live one would. The command stops if any of those rows could carry something from after the Cut-off Date: every Market must have resolved before it, and the Wallet must have made no trade in it afterwards (only collecting a payout, which pays an outcome already known, may come later). 0xd218e4 and 0x63d43b stay out of the offline Scan and keep only their lookup data: their capture holds trades only from May 2025, so their bets before the Cut-off Date could not be judged anyway, and storing both of their parts would push the Sample Dataset far past its 50 MB limit (decision log, 27 November 2026).

`uv run liquidoracle make-synthetic` rebuilds the Synthetic Wallets: made-up Wallets whose correct answers are known in advance, used to check the Skill Test. Run it from the repository folder. It rewrites the eight small Wallets and the anchor Markets' volume list (`funnel-markets.json`, what lets an offline Scan find its Wallets) in `sample_data/synthetic/` (committed; the output is identical every time, so `git status` stays clean) and writes 1,000 coin-flipper Wallets (about 100 MB) to `instance/synthetic/coin-flippers/`, which is never committed. The generator can also make 1,000 lucky-streak Wallets: coin-flippers that keep betting after the Cut-off Date at fair odds. They exist only to check the Hold-up Test (the ones that happened to pass before the date must show no skill after it), so they are never written to disk or loaded into the app; the tests build them straight from the generator. You don't need this command to run the app or the tests.

## The Hold-up Test on the Sample Dataset

The Hold-up Test asks whether the Wallets that passed before the Cut-off Date kept it up afterwards. To see it, start the app in Offline Mode, open *Scan wallets*, press *Start Scan*, wait about a minute, click the Scan's number in the Watchlist column and then the *Hold-up Test* tab. With the default Seed (44) the Scan of the Sample Dataset gives this result, written here as it came out (27 November 2026; the tests check every number in the table):

| Group | Verdict on the bets after the date | A trader with no edge would do this well | Resolved bets counted | Real PnL | Wallets in the group | Wallets dropped | Wallets not fully read |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Before-Cut-off Passers | *Skilled (high confidence)* | fewer than 1 time in 10,000 | 300 | $6,000 | 10 | 7 | 0 |
| Comparison Group | *No evidence of skill* | more than half the time | 409 | −$19,217 | 999 | 996 | 0 |

The Passers are the Wallets rated *Skilled (high confidence)* on their bets before the date. The Comparison Group is the Wallets rated *Likely skilled* or *No evidence of skill* on the same bets. A Wallet is dropped when it has fewer than 10 resolved bets after the date; each Wallet's bets after the date are capped at its first 2,000.

What this result can and cannot tell you:

- **It is not a finding about real traders.** No real Wallet is among the Passers: none was rated *Skilled (high confidence)* before the date. The 10 Passers are the sharp trader, steady sharp, forecaster, speed trader and 6 coin-flippers that passed by luck. Only three of them have bets after the date and are tested, and all three (steady sharp, forecaster, speed trader) are made-up Wallets built to keep winning. So "the skill held up" shows only that the test finds skill that was put there. In Offline Mode the page says so above the cards, and a test fails if a real Wallet ever becomes a Passer.
- **Only 8 real Wallets, and they were picked.** They were chosen for the Sample Dataset, so this is not a full Scan of Polymarket. 0xd218e4 and 0x63d43b stay outside the offline Scan (see *Where the real Sample Wallets come from* above). Three of the 8 had *Not enough data* before the date and are in neither group; the other 5 are in the Comparison Group.
- **The Comparison Group's result rests on 3 real Wallets.** Two of its 5 real Wallets are dropped (9 and 4 bets after the date), and 307 of its 409 bets come from one Wallet, 0xd3a6e5. It says little about Wallets in general.
- **Why the page shows a warning.** The 1,000 coin-flippers have no bets after the Cut-off Date (their last bets resolve in June 2025), so all 1,000 are dropped: 6 of them are Passers and 994 are in the Comparison Group. With the sharp trader and the two real Wallets that are dropped too, that makes 7 of the 10 Passers (70%) against 996 of the 999 Wallets in the Comparison Group. The page then warns that more Wallets were dropped in one group than in the other. The warning is right, because those Wallets did stop betting. The rule is not changed to hide it (decision log, 27 November 2026), and in Offline Mode the page gives this reason under the warning.
- **A limit of testing a group as one.** Bets in the same Market are replayed together, so Wallets holding the same bet do not count as separate evidence. Two Wallets on opposite sides of one Market each keep their own price as their chance of winning, though, so when the two prices add up to more than 1, some replays let both win.

## The Hold-up Test on a live Scan

On 27 November 2026 the app was run online and scanned real Polymarket Wallets (Story 5.3 in the plan). Which Scan would count was decided before anything was run: 200 Wallets, Cut-off Date 1 July 2025, Seed 44, with a trial Scan of 10 Wallets first and no other run with another size, date or Seed. That plan was committed on the author's PC at 16:43:41 (commit `bbca83f`), 16 seconds before the trial was started, and pushed afterwards together with the result, so the commit's own time is the only proof of the order. This is the 200-Wallet Scan's result, written here as it came out. The numbers were read from the stored Scan by a script and checked against the Hold-up Test page.

| Group | Verdict on the bets after the date | A trader with no edge would do this well | Resolved bets counted | Real PnL | Wallets in the group | Wallets dropped | Wallets not fully read |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Before-Cut-off Passers | *Skilled (high confidence)* | fewer than 1 time in 10,000 | 4,161 | $3,439,086 | 9 | 2 | 1 |
| Comparison Group | *No evidence of skill* | about 1 time in 20 | 26,431 | $3,096,636 | 62 | 10 | 3 |

So the Wallets that passed on their bets before 1 July 2025 (the 7 of the 9 that kept betting) were, as one group, still rated *Skilled (high confidence)* on the bets they made after it. The Wallets rated *Likely skilled* or *No evidence of skill* before the date (the 52 of the 62 that kept betting) were not, by a very small margin.

The Scan behind it:

- **Markets:** the top 100 by volume that resolved in the 90 days before the Cut-off Date. 77 were used. 23 are marked "not used: partial", because the app does not use a Market it has not read whole; the usual cause is a list of the Market's Wallet positions that reaches the app's limit of 15,000 rows. The 23 hold about 40% of the 100 Markets' volume ($1.56 billion) and include 4 of the 5 largest. The 77 gave 189,086 Wallets to choose from.
- **Wallets:** a shortlist of 600 by a quick profit estimate. One was a Polymarket contract address and was dropped. The other 599 were read and ranked on their Real PnL before the date, and the top 200 were tested. Only 258 of the 599 had made any profit before the date, so the 200 run from $819,053 down to less than one cent: the 100th has $5,585, and 53 have under $100. 15 of the 599 could not be read in full. 7 of those ended on a Real PnL of $0 and so outside the 200, among them 0xd218e4, the Wallet with the highest profit estimate on the shortlist ($1.0 million). Of the 200 tested, 7 were not fully read.
- **Before the date:** 9 Wallets rated *Skilled (high confidence)* (the Passers), 14 *Likely skilled* and 48 *No evidence of skill* (together the Comparison Group), and 129 *Not enough data* (fewer than 30 resolved bets; they are in neither group). By the rule behind the Watchlist page's luck line (1 in 100 Wallets with a Verdict), about 1 of these 71 would pass by luck alone, so not all 9 Passers need be skilled.
- **Watchlist:** 10 Wallets rated *Skilled (high confidence)* on their whole history. 8 of them are also Passers. The Watchlist page says: "At least about 1 of the 114 Wallets with a Verdict would pass by luck alone, probably more, because these Wallets were picked for high profit."
- **Time:** started 19:24, finished 22:08 (Norwegian time): 2 hours 44 minutes in one run. Polymarket did not stop it. 19 minutes went to the Markets, 1 hour 53 minutes to the Wallets' bets before the date, 32 minutes to their bets after it, and about 10 seconds to the Hold-up Test itself. A small script outside the repository stood by to press *Resume Scan* if Polymarket stopped the Scan overnight; it never had to. The Scan reused 39 stored Wallet parts that the trial had fetched a few hours earlier (the app reuses data under 24 hours old), 0xd218e4's among them. Fetching those took the trial about 80 minutes, not counting a failed attempt, so a Scan from nothing would take about that much longer.
- **The trial before it** (10 Wallets, same date and Seed, run to see that the app worked on live data): 2 hours 20 minutes, stopped once by Polymarket (three 503 answers, 39 minutes into reading 0xd218e4, whose reading was lost) and resumed; no Wallet rated *Skilled (high confidence)*, so no Passers, and a Comparison Group of 7 Wallets rated *No evidence of skill* (about 1 time in 9, 2,072 bets).

What this result can and cannot tell you:

- **It is one Scan.** One Cut-off Date, one Seed, one day's data. Apart from the trial nothing else was run, on purpose, so that the result could not be picked. Another date could come out differently.
- **The Comparison Group's label is a coin toss.** Its p-value was 0.0503, and *Likely skilled* starts below 0.05: 502 of the 10,000 replays did at least as well as the group, and with 499 the label would have been *Likely skilled*. The replays are random, and another Seed moves that count by about 20 either way. What the result does show is the distance between the groups: the Comparison Group sits on the line, and no replay at all did as well as the Passers. The Comparison Group's Real PnL was positive too, $3.1 million on about six times as many bets.
- **It is one test of the group, not of each Wallet.** The 7 tested Passers' 4,161 bets are replayed together (the other 2 have no counted bets after the date). The result does not say that each of the 7 kept winning. The bets are spread, with 1,377 from the largest, 0x68c24b, but the money is not: two Wallets, 0xbaa2bc and 0x614dc8, made $2.27 million of the $3.44 million on 567 bets. (These per-Wallet figures are each Wallet's whole-history figure minus its figure before the date; the app does not show them.)
- **The Wallets were picked for profit, from a limited pool.** They are the best 200 of the 599 shortlisted in 77 large Markets, and many of them made little. Wallets that made their money in the 23 Markets left out can be missing, and so can the very largest Wallets, which the app could not read in full. This is not a sample of all Polymarket traders.
- **Most of the 200 could not be tested.** 129 of them had fewer than 30 resolved bets before the date that the test could count, so they got *Not enough data* and are in neither group. The result says nothing about them.
- **Some Wallets were cut short.** A Wallet's bets before the date are capped at the latest 2,000 (8 of the 200 reached that, 1 Passer among them) and its bets after the date at the first 2,000. 4 Wallets in the two groups were not fully read (1 Passer, 3 in the Comparison Group).
- **"Skilled" means "unlikely to be luck at the prices paid".** It does not say why a Wallet wins (see "What this test can't see" on every Verdict card), it does not say the Wallet will keep winning, and it does not say that copying it would have made money: that is the Copy Test (FR-18), which is not built. It is not financial advice.

To run a Scan like it yourself, start the app with `uv run liquidoracle run` and keep that terminal open, open *Scan wallets*, set the Cut-off Date to 1 July 2025 (the number of Wallets is already 200) and press *Start Scan*. Expect hours, and about 1.1 GB of disk for `instance/live.db`. If Polymarket stops answering, the Scan stops, and *Resume Scan* on the same page carries on. Do not trust the page's time estimate: it said about 10 minutes for the trial that took 2 hours 20 minutes, and then, going by that trial, about 25 hours for the Scan that took 2 hours 44 minutes. Polymarket's data changes, so your numbers will not match these exactly. The Scan above is kept in the author's `instance/live.db`, which is never committed; a copy with a SHA-256 checksum is kept outside the repository.

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

- **What they cover:** the copy button; that no page scrolls sideways at 320, 360, 600 and 900 px; that buttons do not move when your system is set to reduce motion; the Windows High Contrast (forced colours) rules; `chart.js` (`test_chart_script.py`: the chart's keys, the tooltip, the marker's highlight, the build-up, and the chart without the script); `progress.js` (`test_progress_script.py`: a live lookup polling, swapping in the Verdict or the matching message page, and giving up after 30 failed polls in a row); the Hold-up Test page (`test_holdup_cards.py`: the two group cards side by side only from 900 px, the Scan tabs by keyboard, and what a screen reader is given); and the accessibility checklist (`test_checklist.py`: the 12 items walked with the keyboard only, reading the role, name, state and reading order a screen reader is given, plus every page with JavaScript off). What the checklist found, failures included, and what it cannot prove are in [`docs/accessibility-check.md`](docs/accessibility-check.md).
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
