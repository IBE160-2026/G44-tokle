# Tilbakemelding på PRD

| | |
|---|---|
| **Gruppe** | G44 – G44-tokle |
| **PRD vurdert** | `_bmad-output/planning-artifacts/prds/prd-LiquidOracle-2026-10-12/prd.md` (status `final`, sist endret 2026-11-11, commit 056c33b) |
| **Dato** | 2026-11-12 |
| **Type** | Formativ tilbakemelding, ikke karakter |

## 1. Samlet inntrykk

Dette er en uvanlig sterk PRD: tydelig tese, 24 FR-er med testbare konsekvenser, ærlig om hva testen ikke ser, og syntetiske lommebøker med kjent fasit som bærer kvalitetssikringen. Risikoen ligger ikke i innholdet, men i størrelsen. PRD-en er på ca. 11 500 ord, og trinn 2 er svært stort for ett semester. Det gjør det vanskeligere å hente ut stories og å vite hva som er «ferdig nok».

## 2. Dette fungerer godt

- **Testbarhet er bygd inn.** FR-5 har konkrete grenser (hand-check mellom 0,0003 og 0,002; av 1 000 coin-flippers maks 7 % med p < 0,05), og FR-13 kobler hver syntetiske lommebok til FR-en den tester. Briefens viktigste risiko, å kontrollere at KI-skrevet statistikk er riktig, er dermed besvart.
- **Ærlig om begrensninger.** FR-3 «Known limit (decided)» og FR-11 viser at verdiktet ikke dekker bets solgt før oppgjør, og §7 har motmål (SM-C1 «do not optimise», SM-C2: at ferdighet ikke varer er «a valid outcome, not a failure»).
- **Kjørbarhet og KI-kontroll.** Offline Mode (FR-14), Mock LLM Mode (FR-15), blind håndmerking av 50 markeder med 80 %-grense (FR-19) og kode som sjekker forklaringen mot kortet (FR-24) viser hvordan KI-delen kontrolleres uten nøkkel.

## 3. Oversikt per dimensjon

| Dimensjon | Vurdering | Kort begrunnelse |
|---|---|---|
| Beslutningsklarhet | sterk | Valg står med begrunnelse og avveining (Main Copy Delay fast fordi tre forsøk gir flaks tre sjanser). |
| Substans | sterk | Ingen pynte-personas; NFR-er har tall (5 forespørsler/s, 10 s, 25 MB). |
| Strategisk sammenheng | sterk | Tesen «slo lommeboken oddsene mer enn flaks forklarer?» styrer alle tre trinn. |
| Testbarhet | sterk | Nesten alle FR-er har målbare konsekvenser; små hull i FR-24 (se 4.3). |
| Scope og avgrensning | god | Non-Goals og trinn er tydelige, men trinn 2 er for stort og har ingen nedskaleringsplan. |
| Brukbarhet for neste fase | god | Glossar og ID-er holder, men lengde og tetthet gjør uthenting tungt. |
| Formtilpasning | god | Riktig form for et metodetungt produkt; UJ-4 og glossaret bærer for mye. |

## 4. Viktigste forbedringer

### 4.1 PRD-en er for lang og tett til å brukes direkte
- **Alvorlighet:** høy
- **Hvor:** §3 Glossary («Sliver», «Follower PnL», «Random Group Check») og FR-18 (ca. 14 punkter)
- **Problem og hvorfor det betyr noe:** Glossaret inneholder krav og beregningsregler, og kilde-/historikknotater som «(Edvard, 2026-10-21)» og «(Architecture, …)» står midt i FR-ene. Story-skriving trenger én regel ett sted. FR-18 er egentlig tre krav: prisingen, luck-sjekken mot tilfeldige grupper og datakilden med fallback.
- **Forslag:** Flytt begrunnelser og dato-notater til `addendum.md` eller en beslutningslogg, og la glossaret bare definere begreper. Del FR-18 i for eksempel FR-18a (Follower PnL/Return), FR-18b (Random Group Check) og FR-18c (prishistorikk og fallback), hver med 3–5 punkter. Mål: under ca. 6 000 ord.

### 4.2 Trinn 2 er for stort, og har ingen minimumsversjon
- **Alvorlighet:** høy
- **Hvor:** §6.1 «Stage 3 … Trimmed first if time runs short»; FR-16–FR-18
- **Problem og hvorfor det betyr noe:** Bare trinn 3 kan kuttes. Men trinn 2 har traktutvelging av markeder, Scan, Hold-up Test, Copy Test med 10 000 tilfeldige grupper, flere simuleringsgater og en fallback-pool på 50 lommebøker, alt for én person. Går trinn 2 tregt, mangler en definert «god nok» versjon.
- **Forslag:** Legg til en rekkefølge og et minimum, f.eks.: «2a: Scan og Watchlist på Sample Dataset (FR-16). 2b: Hold-up Test (FR-17). 2c: Copy Test (FR-18). Hvis 2c ikke rekkes, leveres 2a+2b, og SM-5 rapporteres for Hold-up alene.» Skriv også hvilket FR-sett som er «ferdig» for hver milepæl.

### 4.3 KI-delen har hull i feil-, kostnads- og ordlistekontroll
- **Alvorlighet:** medium
- **Hvor:** FR-19 og FR-24 («none of the words banned in §8 Wording»)
- **Problem og hvorfor det betyr noe:** §8 Wording nevner bare tre eksempelord («guaranteed», «insider», «will win»), så FR-24 kan ikke bli en test uten en full liste. FR-19 sier ikke hva som skjer når modellen svarer med ukjent Domain, ugyldig format eller feil/timeout, eller hvor mange kall en klassifisering kan koste.
- **Forslag:** Legg til: «Svarer modellen med noe annet enn ett av de fem Domains, eller feiler kallet, får markedet *Other* med kilde `fallback` og telles; ingen forsøk gjentas mer enn 2 ganger.» Og: «De forbudte ordene står i en liste i koden; FR-24-testen bruker hele listen.» Oppgi et anslag for antall kall (ett per marked, lagret) og at kostnaden vises i README.

### 4.4 §9 Open Questions og status er ikke ryddet
- **Alvorlighet:** lav
- **Hvor:** §9 Q2, Q5 og Q6 («The value itself is still open» … «Decided … 1 July 2025»); Q7; frontmatter `status: final`
- **Problem og hvorfor det betyr noe:** Q5 og Q6 er besluttet, men står uten overstrykning, og Q6 sier fortsatt «still open». Q7 er en «kanskje senere»-idé, ikke et åpent spørsmål. En leser vet ikke hva som faktisk gjenstår.
- **Forslag:** Stryk Q5/Q6 som Q1/Q3/Q4, og rett den første setningen i Q6. Flytt Q7 til §6.2. Legg til «Gjenstår: ingen» eller en kort liste.

### 4.5 Teknologi og API-detaljer lekker inn i kravene
- **Alvorlighet:** lav
- **Hvor:** §8 «uv … Python 3.12 and 3.14», «`/v2/positions`»; FR-3 («the closed list's own timestamp»)
- **Problem og hvorfor det betyr noe:** §0 sier at teknologi bor i addendumet, men API-ruter og verktøyvalg står i §8 og FR-3. Da må PRD-en endres hver gang arkitekturen gjør det.
- **Forslag:** Skriv kravet («starter med høyst 3 kommandoer på Windows, macOS og Linux; kjører mot Polymarket under publiserte rategrenser») i PRD-en, og la verktøy og ruter stå i addendum/arkitektur.

## 5. Mekaniske funn

- FR-ID-ene 1–24 er sammenhengende og krysshenvisningene løser seg. FR-15 står i trinn 3 selv om nummeret ligger før FR-16; dette er forklart i teksten.
- Glossaret brukes konsekvent. Antakelsesindeksen (§10) dekker de innebygde `[ASSUMPTION]`-merkene.
- Minstegrensen på 30 Resolved Positions og p-grensene (0,01 / 0,05) er valgt, men ikke merket som antakelser. Det bør stå at de er konvensjoner.
- UJ-ene har navngitt hovedperson (Jonas) og dekker FR-ene godt. UJ-4 er likevel ett avsnitt med ca. 12 tall og bør deles i trinn.

## 6. Før dere går videre

**Må avklares før UX, arkitektur og epics:** minimum for trinn 2 (4.2), hele ordlisten for FR-24 og feilhåndtering i FR-19 (4.3), og hvilke Q-er som faktisk er åpne (4.4). Resten (antakelsesverdier som 200 lommebøker og 0,5 cent) kan vente til dere har målt med ekte data, slik §10 sier.

**Oppfølging av tilbakemeldingen på product brief: ja.** Testbare suksesskriterier (SM-1–SM-7), syntetiske lommebøker med fasit (FR-13), trinndeling (§6.1), reproduserbarhet med Seed (FR-7), offline-kjøring og mock-modus (FR-12, FR-14, FR-15) og database (§8) er alle på plass.

## 7. Refleksjonsspørsmål

1. FR-5 og FR-18 har svært detaljerte kontrolltall (f.eks. «maks 7 % av 1 000 kjøringer»). Hvilke av disse kom fra deg, og hvilke foreslo KI? Hvordan sjekket du at grensene er rimelige og ikke bare får testen til å passere?
2. Hvilke krav i PRD-en har KI lagt til som du ville fjernet hvis du måtte kutte omfanget med en tredel, og hvorfor?

_Vurdert mot kvalitetsrubrikken i bmad-prd. Dette er veiledning, ikke sensur._
