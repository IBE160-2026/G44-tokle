# Story 5.2: the Hold-up Test page

## 2026-11-27 kl. 15:04 — Edvard Tokle

### Oppgave
Edvard ba om å lese handoff, sette Story 5.1 til `done` (PR #46 var merget og sjekkene grønne) og starte Story 5.2, Hold-up-siden, med `bmad-build`. Story 5.2 lukker stage 2-minimumet.

### Plan
- `main` pullet, CI sjekket uten `gh` (merge-kjøringen grønn; PR-kjøringen passerte på andre forsøk), branch `story-5-2-the-hold-up-test-page`, 5.1 satt til `done` (c54c5b5).
- `bmad-build`: spec [spec-5-2-the-hold-up-test-page.md](../../_bmad-output/implementation-artifacts/spec-5-2-the-hold-up-test-page.md).
- Edvards valg: 1a (grunnen til offline-advarselen sies både i README og i en infoboks på siden, bare i Offline Mode) med HANS EGET TILLEGG: boksen skal også si at Passers som testes offline er oppdiktede Wallets, ellers leses kortet som om vi fant en ekte dyktig trader. 2a (uten Passers: setningen i Passers-kortet, Comparison Group-kortet vises fortsatt). Spec holdt hel (ca. 3 000 tokens; AI-en sa først 2 400 til 2 600 og rettet det). Hjelpere bare til review. Tre AI-valg godtatt (fem tall per kort, Verdict-kortets odds-setning, én teknisk grense i README). VED GODKJENNING LA HAN TIL: en test skal feile hvis «no real Wallet passed» slutter å være sant.
- Planen oppdatert før kode (DESIGN.md, EXPERIENCE.md, epics 5.2, AD-13, to memlogs), så kode, tester, README, review med tre hjelpere.
- Etter review spurte AI-en om en linje på hvert kort som sier hvem som er i gruppen (en reviewer savnet den; planen hadde den ikke). Edvard: «yeah add the line, then commit n push», og de to validation-report-filene holdes utenfor som alltid.

### Resultat
- Hver ferdige Scan har en *Hold-up Test*-fane ved siden av Watchlist (`/scans/<id>/hold-up`). Siden viser de to lagrede grupperesultatene som kort (Verdict-pille, odds-setning, fem tall, en linje om hvem som er i gruppen), advarselen over kortene, og notatet og Seed under. Ingenting testes på nytt. En Scan fra før Story 5.1 har ingen fane, og adressen gir «Page not found».
- I Offline Mode sier en infoboks at Passers som testes er oppdiktede Wallets, ikke ekte tradere, og hvorfor advarselen vises på Sample Dataset.
- Ny `services/holdup.py`; Scan-headeren og fanene er nå én funksjon (`services.watchlist.scan_header`) og én mal (`scan_head.html`) som Watchlist og Hold-up-siden deler. Ingen ny JavaScript.
- README: resultat-tabellen (Passers: Skilled (high confidence), 300 bets, $6 000, 10 Wallets, 7 droppet; Comparison Group: No evidence of skill, 409 bets, −$19 217, 999 Wallets, 996 droppet), fem grenser, stage 2-teksten som liste, status «stage 2 minimum done».
- Edvards test: `test_fr17_no_real_wallet_is_a_passer_in_the_offline_scan` (ekte offline-Scan; ingen ekte Wallet er Passer etter appens egen regel). Plantet feil: testen feilet og navnga 0xcf0d7f. Etter review også under fire andre Seeds.
- Ekte app: ny offline-Scan (Scan 3, 53 s); siden, de lagrede radene og README stemmer overens.
- Review: 30 funn, ingen feil tall på siden. 22 førte til rettinger (README-størrelsene bygges nå fra de seks listede heldige coin-flipperne, bevist mot generatoren; ni-sifrede beløp fikk siden til å rulle sidelengs på 320 px med første CSS, nå én kolonne der to blir for trangt; boksen forklarer ikke advarselen når det er Passers som er droppet mest; to tester som ikke kunne feile er skrevet om), 7 avvist, 1 tatt til Edvard og bygget, 1 del utsatt.
- Plantede feil: 29 + 11 + 3, alle fanget til slutt (reelle hull tettet: en gruppe der alle er droppet ble vist som tom; tre kolonner; beløp som brytes).
- Tester: 1 702 passerer med `CI=true`, 0 hoppet over (1 636 før); `tests/test_holdup.py` med 1 000 repetisjoner: 60 passerer.
- Lukket i `issues.md`: de fire 5.2-punktene fra 5.1 og 4.7, README-resultatet (fra 18.11) og «first 2,000»-linjen (fra 4.5).
- Commits: c54c5b5 (5.1 `done`), 0083202 (plan), 9e1967b (kode, tester, README), 2caa5e9 (spec, review-logg, sprint-status), 663dfd2 (AI-logg `docs/ai-logs/2026-11-27-story-5-2.md`).

### Åpne punkter
- `docs/accessibility-check.md` dekker bare stage 1-sidene; Scans-siden, Watchlist og Hold-up-siden mangler, selv om sjekkene finnes som nettlesertester (`deferred-work.md`).
- «Wallets not fully read» på gruppekortene har ingen forklaring (andre halvdel av reviewfunn BH13; ikke bedt om, ikke bygget).
- PR #46 sin CI-kjøring feilet på begge macOS-jobbene i «Run the tests» 27.11 og passerte på nytt forsøk; testnavnet er ukjent (loggene krever innlogging). Følg med på macOS-jobbene.
- README sier at stage 2-minimumet er ferdig: det gjelder først når CI er grønn på alle tre systemene for denne branchen.
