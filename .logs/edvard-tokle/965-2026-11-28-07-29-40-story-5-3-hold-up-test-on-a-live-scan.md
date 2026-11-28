# Story 5.3: the Hold-up Test on a live Scan

## 2026-11-28 kl. 07:29 — Edvard Tokle

### Oppgave
Edvard ba om å lese handoff, sette Story 5.2 til `done` (PR #47 var merget) og gjøre Story 5.3: Hold-up Test på en live Scan av ekte Polymarket-Wallets. Storyen ligger utenfor stage 2-minimumet, legger ikke til kode, og skal skrive resultatet inn i README og refleksjonsnotatene slik det faller ut. Økten gikk over to dager (27. og 28. november).

### Plan
- `main` pullet, branch `story-5-3-hold-up-test-on-a-live-scan`, 5.2 satt til `done` (49ae83b). Mains CI for merge-commiten feilet på én macOS-jobb; Edvard kjørte den på nytt og den passerte. Hans instruks: før den på issues-lista, ikke fiks den nå.
- `bmad-build`: spec [spec-5-3-hold-up-test-on-a-live-scan.md](../../_bmad-output/implementation-artifacts/spec-5-3-hold-up-test-on-a-live-scan.md).
- Edvards valg («1a 2a 3a, keep it whole», alle AI-ens anbefalinger): Scannen som teller er 200 Wallets, Cut-off Date 1. juli 2025, Seed 44; en prøve-Scan på 10 Wallets først, rapportert med én linje; AI-en kjører prøven, han starter den store selv i egen terminal; ingen annen Seed, dato eller størrelse kjøres for å få et penere svar. Planen ble committet (bbca83f) før noe ble kjørt.
- Etter prøven valgte han («a, write the helper») et lite skript utenfor repoet som trykker *Resume Scan* etter en stopp, framfor å trykke selv eller endre appen.
- Så: resultatet leses ut med skript, README, planfilene, review med tre hjelpere, AI-logg. Etter review sa han nei til å committe en eksport av det lagrede resultatet (AI-ens anbefaling), og «commit n push».

### Resultat
- **Prøve-Scan (10 Wallets):** 2 t 20 min mot appens «about 10 minutes». Stoppet én gang: Polymarket svarte 503 tre ganger etter 39 minutter på den svært store Walleten 0xd218e4, og det som var lest for den ble kastet. Gjenopptatt med *Resume Scan*. Ingen Passers; Comparison Group 7 Wallets, *No evidence of skill*, 2 072 bets.
- **200-Wallet-Scannen (den som teller):** startet av Edvard 27.11 kl. 19:24, ferdig 22:08, 2 t 44 min i én kjøring, ingen stopp (hjelpeskriptet trykket 0 ganger). Den gjenbrukte 39 Wallet-deler fra prøven.
- **Hold-up Test, slik appen viser det:** Before-Cut-off Passers *Skilled (high confidence)*, færre enn 1 av 10 000, 4 161 bets, $3 439 086, 9 Wallets, 2 droppet, 1 ikke fullt lest. Comparison Group *No evidence of skill*, ca. 1 av 20 (p = 0,0503), 26 431 bets, $3 096 636, 62 Wallets, 10 droppet, 3 ikke fullt lest. 77 av 100 Markets brukt, 7 av 200 Wallets ikke fullt lest, 10 på Watchlist.
- **README:** ny seksjon *The Hold-up Test on a live Scan* med tabellen, fakta om Scannen, prøven i én linje og sju forbehold (37b271a). Tallene er hentet fra den lagrede Scannen med skript og sjekket mot Hold-up-siden (26 sjekker, 0 avvik).
- **Planfiler:** `epics.md` (hvordan det gikk), `decision-log.md` (ny 5.3-seksjon), PRD-memlog (3 nye linjer) (1216199); spec med kjørenotater, review-logg og verifisering, sprint-status 5-3 `review` (e833b5e). AI-logg `docs/ai-logs/2026-11-27-story-5-3.md` (30773f7).
- **Ingen kode endret:** `git diff main --stat -- src tests` er tom. 1 702 tester passerer med `CI=true`, som før.
- **Review:** tre hjelpere, 26 funn, ingen feil tall i resultattabellen. 24 førte til rettinger i teksten: «alle 200 er toppinntjenere» stemte ikke (bare 258 av 599 hadde tjent noe før datoen; de 200 går fra $819 053 ned til under én cent), de største Walletene ble ikke lest helt og falt utenfor, Comparison Groups merkelapp henger på 3 av 10 000 simuleringer, to Passers står for $2,27 mill. av $3,44 mill., og plan-commiten var lokal, 16 sekunder før prøven. 1 avvist, 1 delvis til Edvard (ingen eksport).
- **Databasen er beholdt for Story 6.6:** kopi utenfor repoet, `../G44-tokle-data/live-scan-200-cutoff-2025-07-01.db` (1,1 GB, skrivebeskyttet) med SHA-256-fil; hashen står også i specen. Sjekkskriptet ligger ved siden av (`check_readme_live_scan.py`).
- **Etter omstart:** Scannen står fortsatt i *Your Scans* med begge faner (sjekket 28.11 etter at Edvard hadde stoppet appen).
- **Lukket fra issues-lista:** tiden på Hold-up-steget i en live Scan (ca. 10 s på 30 592 bets), og at «stage 2 minimum done» i README ventet på grønn CI (PR #47 er merget, main grønn på andre forsøk).
- Refleksjonsnotatene (utenfor repoet) fikk fire punkter.
- **Etter push (28.11, lagt til kl. 08:35):** Edvard åpnet og merget PR #48 med vanlig merge-commit (b7d0cfd); bbca83f ligger i `main`, så hashen README viser til gjelder fortsatt. CI: push-kjøringen for b672669 feilet først på macOS med Python 3.12 («Run the tests») og ble grønn da Edvard kjørte den på nytt; PR-kjøringen og mains kjøring etter merge var grønne på første forsøk. Merge-punktet på issues-lista er lukket.

### Åpne punkter
- Tidsanslaget på Scans-siden bommet begge veier på ekte data (10 minutter for 2 t 20 min; så 25 timer for 2 t 44 min).
- Et 503-svar midt i en svært stor Wallet kaster alt som er lest for den og stopper Scannen til noen trykker *Resume Scan*; appen prøver ikke igjen selv. Hvor de ca. 40 minuttene på 0xd218e4 går er ikke målt.
- Kjent grense: de største Walletene på shortlisten ble ikke lest helt, endte på $0 og kom ikke med blant de 200 (står i README).
- Andre tilfeldige macOS-feil 27.11 (mains kjøring for merge av PR #47, Python 3.12, «Run the tests»; grønn ved ny kjøring; testen er ukjent). Edvard: ikke fiks nå.
- Story 6.6 må jobbe på et duplikat av databasekopien, ellers endres fila og SHA-256 stemmer ikke lenger. Wallet-delene i `instance/live.db` er eldre enn 24 timer fra 28.11 kveld og gjenbrukes ikke av en ny Scan.
- PR-en for denne branchen må merges med vanlig merge-commit: README viser til commit bbca83f, og squash eller rebase endrer hashen. (Løst 28.11: merget med merge-commit.)
- Tredje tilfeldige macOS-feil (28.11): push-kjøringen for b672669, macOS med Python 3.12, «Run the tests», grønn ved ny kjøring. Den andre feilen var også macOS med Python 3.12. Testen er fortsatt ukjent. AI-ens forslag: kopier FAILED-linjene fra loggen før neste nye kjøring.
