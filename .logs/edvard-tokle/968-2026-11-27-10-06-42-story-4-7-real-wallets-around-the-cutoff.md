# Story 4.7: the real Wallets around the Cut-off Date

## 2026-11-27 kl. 10:06 — Edvard Tokle

### Oppgave
Edvard ba om å lese handoff, bytte til `main` og pulle (PR #44, Story 4.6, var merget), sette 4.6 til `done` og starte Story 4.7 (de ekte Walletene rundt Cut-off Date) med `bmad-build`.

### Plan
- `main` pullet, branch `story-4-7-the-real-wallets-around-the-cut-off-date`, 4.6 satt til `done` (50f931b).
- Målt på capture-zipen før spørsmål: 8 av 10 ekte Wallets koster nesten ingenting; 0xd218e4 og 0x63d43b (aktivitet bare fra mai 2025) ville gitt 60–130 MB; capturen har Scan-funnelen fra 21. oktober med holder-lister.
- `bmad-build`: spec [spec-4-7-the-real-wallets-around-the-cut-off-date.md](../../_bmad-output/implementation-artifacts/spec-4-7-the-real-wallets-around-the-cut-off-date.md).
- Edvards valg: de to tunge holdes utenfor (AI-anbefaling a); holder-radene kopieres fra capturen (AI-anbefaling a), og HAN LA TIL kravet om at ingenting fra etter 1. juli sniker seg inn (no-peeking-sjekk); hjelpere bare til review; spec holdt hel. Etter review: han godkjente å rette én setning i den låste specen (Spec Change Log).
- Planen oppdatert før kode (PRD decision log, epics 4.7/5.2/stage 2-minimum, prd.md §6.1, AD-14, epic-4-context, to memlogs), så kode, tester, review med tre hjelpere.

### Resultat
- `build-sample` skriver før- og etter-del for de 8, spiller av alle tre vinduer, og skriver `sample_data/real/funnel-markets.json` (50 Markets, 65 rader) med no-peeking-sjekk (sene trades, split, merge, combo, konvertering i eventet, ufullstendig capture, Market ikke løst før datoen, pris ikke 0/1). Ingen ny henting fra Polymarket trengtes. Sample Dataset 41 MB, byte-likt ved ny kjøring.
- Offline Scan: «Scan of 1,012 Wallets» (var 1 004), alle 53 Markets brukt, de 8 ekte funnet, de to tunge ikke; ca. ett minutt. Ingen ekte Wallet på Watchlist; før datoen: 0xcf0d7f Likely skilled, fire No evidence, tre Not enough data.
- Review: 31 funn, 19 fikset i 12 endringer (tre hull i no-peeking-sjekken), 1 utsatt, resten avvist. 10 plantede feil fanget.
- Tester: 1 577 passerer med `CI=true`, 0 hoppet over (1 548 før).
- 0x0f4b0a sin referanse-CSV regenerert av sitt eget skript (9 flere «left out»-rader, Real PnL uendret −188,77).
- Commits: 0ecfec2 (plan), 7b0effc (kode, tester, data), 9bcdcbb (spec, review-logg, sprint-status), 519cb80 (AI-logg). Lukker issues-punktene om 4.6 `done`, Story 4.7 og «Scan of 1,004».

### Åpne punkter
- Scan-lista viser 1 018 Wallets mens Watchlist sier «Scan of 1,012» (de fire små Synthetic Wallets uten anchor-bets og de to tunge telles i N) (`deferred-work.md`).
- Story 5.2: README-resultatet får ingen ekte Wallet blant Passers (ingen ekte er Skilled (high confidence) før datoen) og 5 i Comparison Group; si det rett ut.
