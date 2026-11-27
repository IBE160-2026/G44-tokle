# Story 5.1: the two groups and their test (Hold-up Test)

## 2026-11-27 kl. 12:22 — Edvard Tokle

### Oppgave
Edvard ba om å lese handoff, bytte til `main` og pulle (PR #45, Story 4.7, var merget), sette 4.7 til `done` og starte Story 5.1 (de to gruppene og Hold-up-testen deres) med `bmad-build`.

### Plan
- `main` pullet, branch `story-5-1-the-two-groups-and-their-test`, 4.7 og Epic 4 satt til `done` (44055cd). CI sjekket uten `gh`: 4.6-mergen grønn, 4.7-mergen kjørte fortsatt.
- Epic 5 manglet kontekstfil: skrevet (`epic-5-context.md`).
- `bmad-build`: spec [spec-5-1-the-two-groups-and-their-test.md](../../_bmad-output/implementation-artifacts/spec-5-1-the-two-groups-and-their-test.md).
- Edvards valg: lucky-streak-Walletene bare til sjekkene (AI-anbefaling a). FØR han låste det SPURTE HAN hva som skjer med coin-flipperne som alt er i Scan-en: målt, de har ingen bets etter datoen, alle 1 000 droppes, og advarselen om ulik andel droppet vises offline. HANS EGET VALG: advarselen er riktig og blir, regelen bøyes ikke, og Story 5.2 skal forklare hvorfor den vises (ny linje i epics 5.2). Hjelpere bare til review; spec holdt hel. Etter review: «drop the files» (lucky-streak-filene, ca. 200 MB som ingenting leste; Spec Change Log).
- Planen oppdatert før kode (PRD decision log, FR-13-raden, epics 5.1/5.2, AD-14, AD-15, AD-22, to memlogs), så kode, tester, review med tre hjelpere.

### Resultat
- Scan-jobben har et nytt siste steg, «Hold-up Test»: gruppene dannes bare fra `scan_before`-resultatene (Passers = Skilled (high confidence); Comparison Group = Likely skilled / No evidence), hver gruppes bets etter datoen slås sammen (minst 10 per Wallet, minst 30 per gruppe) og testes med Skill Test-motoren som én tilfeldig enhet, og de to radene lagres i samme transaksjon som setter Scan-en `done` (tabell `group_result`, skjema 7; eldre filer beholder Scan-ene sine uten Hold-up-rader).
- Ny `core/holdup.py`; fasen ligger i `services/scan.py` (avvik fra planens `services/holdup.py`, forklart i spine og memlog); `skill_test` har fått `purpose` og trekker simuleringene i blokker tilpasset gruppens størrelse (samme tall).
- Generatoren lager 1 000 lucky-streak-Wallets (bare for sjekkene, aldri skrevet eller lastet). 7 passerer før datoen; på de 700 senere betsene: No evidence of skill (p = 0,62).
- Full offline Scan (51 s, steget tar 0,3 s): Passers 10 Wallets, 7 droppet, Skilled (high confidence) på 300 bets; Comparison Group 999 Wallets, 996 droppet, No evidence of skill på 409 bets fra 3 ekte Wallets (0x0f4b0a 89, 0x736483 13, 0xd3a6e5 307), Real PnL −19 217, p = 0,56. Advarselsflagget er satt (70 % mot 99,7 %).
- Plantet kjøring: 7 Passers i de samme 40 Markets gir p < 0,05 i 37 av 1 000 (grense 7 %); talt som 280 separate bets: 249 av 1 000.
- Review: 23 funn, ingen feil resultat. 15 førte til rettinger (tre testhull bevist med plantede feil, `finish_scan` tar nøyaktig de to gruppene, rekkefølgen Passers først, konstanter i `records.py`, plandokumenter rettet), 7 avvist, 1 avgjort av Edvard. 38 plantede feil fanget (30 egne: 27 med en gang, ett reelt testhull tettet, to uten virkning; reviewernes 8).
- Tester: 1 636 passerer med `CI=true`, 0 hoppet over (1 577 før); de to `slow`-sjekkene passerer med 1 000 repetisjoner.
- Commits: 44055cd (4.7 og Epic 4 `done`), 8c256c2 (plan), b096d0d (kode, tester, README), 4ae889e (spec, review-logg, sprint-status), 1e9f28d (AI-logg `docs/ai-logs/2026-11-27-story-5-1.md`).

### Åpne punkter
- Story 5.2: forklar hvorfor advarselen om ulik andel droppet vises på offline-Scan-en (coin-flipperne har ingen bets etter datoen), så det ikke ser ut som en feil (epics 5.2, Edvards valg).
- Story 5.2: README-grensene: ingen ekte Wallet blant Passers; Comparison Group-resultatet hviler på 3 ekte Wallets, 307 av 409 bets fra én (0xd3a6e5) (epics 5.2).
- Story 5.2: `services/holdup.py` for siden; en Scan fra før skjema 7 har ingen Hold-up-rader (`group_results` gir `()`), så fanen må tåle det.
- Story 5.3: følg med på hvor lenge Hold-up-steget tar på den ekte Scan-en (22 s for ca. 99 000 bets; oppslag venter imens) og på minnebruken.
- Kjent grense: feiler Hold-up-steget, er Scan-en ikke ferdig og Watchlist-en vises ikke (AD-22).
- En nettlesertest (`test_checklist_1_skip_link_is_the_first_tab_stop`) feilet én gang i full kjøring med `net::ERR_NO_BUFFER_SPACE` (Windows gikk tom for nettverksbuffer); passerte alene og i de tre neste fulle kjøringene. Følg med.
