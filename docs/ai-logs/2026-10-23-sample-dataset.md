# AI session log, 2026-10-21 to 2026-10-23: Sample Dataset Wallets, Cut-off Date and price capture

- **Tool**: Claude Code (model Claude Opus 5.5) in the VS Code extension.
- **Student**: Edvard Tokle (G44).
- **What this covers**: PRD §9 Q5 (which 10 real Wallets go into the Sample Dataset) and Q6 (the default Cut-off Date), a leak-free way to pick them, and the urgent capture of one-minute price windows while Polymarket's old price route still answers (spine AD-24). The epics step comes next, in the same chat.
- **Result**: `spike/sample_pick.py`, `sample_sold.py`, `sample_table.py`, `sample_capture.py`; the section *Sample Dataset pick and price capture* in `spike/FINDINGS.md`; PRD §9 Q2, Q5, Q6 and FR-12 changed; spine AD-7 and AD-14 changed; 10 PRD memlog entries and 2 architecture memlog entries; branch `sample-dataset`. The raw capture (about 1 GB) is git-ignored and backed up outside the repository.

## 1. The prompt

> "first job is the urgent one: i pick the 10 sample dataset wallets n the default cutoff date, so give me a shortlist of 15-20 in a table with the numbers i need to choose, n one line each on what it would cover. pick the candidates on what they looked like before the cutoff only, never on how well they did after, n tell me what the 10 together should cover so its not just winners. the cutoff has to be after july 2023 n nothing in the picking can use data after it. flag anything that would leak later info. once theyre picked run the price window capture straight away while the old route still answers. then epics"

## 2. How the AI built a leak-free shortlist

The handoff note and PRD §9 Q2 said Polymarket's leaderboard was fine for picking sample Wallets. **The AI flagged that this conflicts with the student's rule**: the leaderboard ranks on today's profit, which includes everything after the Cut-off Date. Instead it used the same funnel as the app's Scan (FR-16, AD-21):

- **Cut-off Date recommended: 1 July 2025**, fixed before any Wallet was looked at. Reasons were coverage only: about 2 years before and 16 months after; all after-part buys inside the range where one-minute prices exist; and a funnel window (Markets resolved April to June 2025) with a normal mix of Markets instead of the 2024 US election.
- **Candidates**: Markets resolved in the 90 days before the date, top 100 by volume; every Wallet in their position lists. 77 of 100 Markets were read in full, giving 189,085 Wallets.
- **A seeded draw of 100**: top earners on those Markets, active, losing, mid-size and random Wallets. 98 were profiled on the before part only, with a rough Skill Test estimate.
- **Shortlist of 19** with numbers (Positions, estimated Verdict and p-value, PnL, entry prices, domain, unredeemed losers, splits) and one line on what each would cover.
- **Addresses only, no names.** Recognising a name would be later knowledge.
- **Six leak flags were listed for the student**, e.g. the two after-the-date columns are activity counts only (needed for FR-12 and FR-4), and the Market cache also holds later outcomes, which are never used.

## 3. Problems found on the way

| Found | By | What happened |
|---|---|---|
| A "top Wallet" was Polymarket's own contract | The run crashed | v2 refuses a protocol contract as a user. The Scan must drop these (for the epics). |
| Gamma down for about 2 minutes | The run crashed | Every route returned an empty 404. The AI fetched the Data API rows while waiting, then added a retry. The app's client needs the same. |
| **Bug in the AI's own p-value estimate** | AI, from a result that looked wrong | A Wallet with $27 profit on near-certain bets came out "Skilled, p 0.0002". Cause: Python's `sum()` and `+=` round differently, so an exact tie never counted. The true p was about 0.74. Fixed by comparing whole cents; the real Skill Test needs the same (for the epics). |
| **The AI's first estimate counted sold bets as held** | AI, comparing with the data source's own PnL | One Wallet showed −$21M against +$2M in the source. In the median Wallet only about half the bets were held to the end. Re-estimated on held bets only, which matches the PRD's rules. |
| Only one "Skilled" and no "Likely skilled" in 59 | AI | The AI drew 40 more on before-the-date numbers only. The student had this logged as a choice (leak flag 4). |

## 4. The student's decisions

> "yes to 1 july 2025, n your 10 is fine. two things before the capture. you say the 10 needs 3 small clean wallets for the hand calculation but dc5378 is the reserve, so check the 10 has 3 without it n swap one in if not. n while the old price route still answers, capture dc5378, 091596 n 29306d as spares too, cuz once that route dies i cant add anyone later. the sample dataset is still the 10, the spares are only insurance, n any swap later has to be for a data reason n logged."

- **Accepted**: the date and the AI's suggested 10.
- **Caught a gap in the AI's own list**: it called the hand-calculation reserve a reserve without checking that the 10 already had three. The AI checked: only two. It swapped 0x29306d in for 0xeb214d. It picked 29306d over the named reserve because 29306d is smaller (about 24 bets against about 306).
- **Added**: three spares captured as insurance, and the rule that any later swap needs a data reason and a log entry.
- **Plan changes he asked for**: the PRD Q2 leaderboard line changed, and the 40-Wallet extra draw logged as a choice.

## 5. The capture

About 6,900 requests at 4 per second. Every one of the 13 Wallets (10 plus 3 spares) got one-minute prices for every after-part token, with no failed request. Per-Wallet counts are in `spike/FINDINGS.md`.

The AI checked its own capture and found two things:
- **Tokens classed "after" that were bought before the date.** On three Wallets whose before-the-date reading hit the 150,000-row cap, 165, 46 and 20 tokens looked new, but the positions list's first-entry time was before the date. The capture was fixed and re-run (234 requests). **The same gap is in the architecture**: AD-7 reads the after part from the date forward and cannot see older buys.
- **The two largest Wallets' after-the-date reading stops at 12 and 20 August 2025.** So 808 and 418 tokens may miss later fills.

It also re-checked the hand-calculation Wallets on the real rows. **Its earlier count was wrong**: 0x8861f0 has only 50 Positions but 10,132 trades, so it cannot be done by hand.

## 6. The student's second round

> "yes to 1, 3 n 4. on 1 put in the memlog that the swap used trade n fee counts only, nothing from after the date, so its not a leak. on 3 zip it n put it outside the repo, n since its 1 gb n cant be refetched, put a second copy somewhere thats not the same disk. on 2 i agree, dont complete the whale fills, but write it down as a one way door: if the cap rule ever changes those two whales cant be fixed cuz the route will be gone by then. that goes in findings n on the limitation, not just skipped."

- **Swap 2**: 0x8861f0 out, spare 0x091596 in. 091596 has 64 Positions and $1,138 in fees, a real test of the fee rule.
- **The AI corrected the wording he asked for.** The trade and fee counts do include after-the-date activity (fees only exist from June 2026). What the swap never used is an after-the-date *result*. The memlog says that instead.
- **Crypto check (the student's catch).** Before swapping, he pointed out that 0xeb214d, the only crypto-heavy Wallet, sat among the spares, while the AI's own coverage list wanted crypto. The AI checked before-the-date counts: 0x736483, 0x63d43b and 0x94884d hold 164, 287 and 87 crypto bets, so crypto is covered. The swap does not change it. The AI recommended keeping 0xeb214d a spare (it would push another Wallet out, and it is messy: 10,554 trades, 1,804 sells, 94 split/merge rows). Edvard agreed: "your reasoning holds since three wallets clear the 30 bet floor."
- **One-way door**: completing the whales' fills was declined, but written into FR-12 and FINDINGS as a limitation that cannot be repaired once the old price route is gone.
- **Backup**: zipped to 176 MB outside the repository, with a checksum. **No second disk was available** (D: is an empty slot, OneDrive not running). The AI offered a USB stick or OneDrive. **Edvard chose a USB stick, not OneDrive**, because turning OneDrive on could start syncing folders that are not part of the project. The copy is verified against the checksum when the stick is in.
- **Added**: the 25 MB Sample Dataset must be rebuilt by a script from the raw capture, never trimmed by hand (spine AD-14).
- **Accepted**: the AD-7 fix (also check `first_entry_at`).

## 7. Commit rules from the student

- Add files by name, never `git add .`: the two `validation-report.html` files stay untracked on purpose, as before.
- Show the diff and this log before committing; push to `sample-dataset`; he opens the pull request himself.

## 8. Still open

- Second backup copy on a USB stick (Edvard plugs it in).
