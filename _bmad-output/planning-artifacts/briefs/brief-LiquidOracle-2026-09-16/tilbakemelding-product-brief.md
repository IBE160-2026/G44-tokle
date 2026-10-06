# Tilbakemelding på product brief

| | |
|---|---|
| **Gruppe** | G44 – G44-tokle |
| **Product brief** | `_bmad-output/planning-artifacts/briefs/brief-LiquidOracle-2026-09-16/brief.md` (commit `a04c474`) |
| **Tilbakemelding fra** | Faglærer i IBE160 (utarbeidet med KI-støtte) |
| **Dato** | 2026-10-06 |

## Samlet vurdering

- **Bør revideres før dere går videre.** Rett punktene markert «Endre» før dere lager PRD og arkitektur.

Vi har vurdert `brief.md` for «LiquidOracle». Briefen er grundig og ærlig, og problemet er interessant. Det som må rettes, gjelder først og fremst suksesskriteriene og hvordan dere skal kontrollere at den statistiske metoden faktisk er riktig implementert.

**Det som er bra:**

1. Problemet er skarpt formulert. Rå PnL sier lite om ferdigheter, og eksisterende verktøy (Polymarkets leaderboard, Dune, polywallet.app, polymarketanalytics.com) rangerer bare etter PnL, ROI eller volum. Kjerneidéen om en randomiseringstest som skiller ferdighet fra flaks, er konkret og faglig begrunnet.
2. Avgrensningen er ærlig og moden. Sybil-deteksjon er eksplisitt utsatt («Named out loud so it doesn't creep back in»), bot-filtreringen er tydelig merket som heuristikk med kjente begrensninger, og det er klart at verktøyet ikke gir finansielle råd eller handler.

**De viktigste endringene:**

1. Suksesskriteriene kan ikke testes slik de står. «Working code that demonstrably runs …», et refleksjonsnotat og et uformelt «out-of-sample backtest» er ikke kriterier som kan bli testtilfeller. Legg til konkrete, funksjonelle kriterier, og særlig kriterier som viser at randomiseringstesten gir riktige svar.
2. Beskriv hvordan dere skal kontrollere at Claude Codes implementasjon av randomiseringstesten er riktig. Det er den største risikoen i prosjektet. Bruk syntetiske lommebøker med kjent fasit, altså en simulert «flaks»-lommebok og en simulert «dyktig» lommebok, som testdata.
3. Planlegg hvordan sensor kan kjøre appen uten å være avhengig av at Polymarkets API svarer, og uten deres LLM-nøkkel. Lagre for eksempel et utvalg lommebøker lokalt, og ha en mock-modus for språkmodellen.

## Vanskelighetsgrad og gjennomførbarhet

### Vurdert vanskelighetsgrad

- **Vanskelig**

**Sammenlignbart med:** 4) KI-støttet MRP II (vanskelig) og 5) KI-styrt sensurering (vanskelig). Som i de forslagene må omfattende domenelogikk stemme. Her gjelder det statistisk inferens over store handelshistorikker, i tillegg til eksterne data og to LLM-roller.

**Begrunnelse:**

| Faktor | Nivå (lav / middels / høy) | Kommentar |
|---|---|---|
| Domenelogikk – hvor mange og hvor kompliserte regler og beregninger må stemme? | høy | Permutasjonstest med nullfordeling, konfidensnivå per domene, PnL-beregning for løste markeder og atferdsheuristikker for bot og market maker. Feil er lette å gjøre og vanskelige å oppdage. |
| Datamodell – antall entiteter og relasjoner mellom dem | middels | Lommebok, marked (med domene), handel, posisjon, utfall, testresultat per domene og bot-flagg. |
| Brukere, roller og innlogging | lav | Ingen innlogging. Oppslag på lommebokadresse. |
| KI-funksjonalitet i appen, f.eks. kall til språkmodell, prompts i koden og håndtering av usikre svar | middels | Domeneklassifisering av markeder og forklaringer i klart språk. Forklaringen må ikke overdrive det statistikken sier, og det må kontrolleres. |
| Integrasjoner og eksterne tjenester, f.eks. API-er, betaling og e-post | høy | Polymarkets Data API og subgraph med paginering, rate limits og endringer i formatet, pluss LLM-API. |
| Sanntid, samtidighet eller flere brukere som påvirker hverandre | lav | Ingen sanntid. Tusenvis av permutasjoner per lommebok kan likevel gi lang beregningstid. |
| Filhåndtering, f.eks. opplasting, PDF-lesing og eksport | lav | Ingen filhåndtering, men behov for lokal hurtigbuffer eller lagring av hentede data. |
| Sikkerhet og personvern | lav | Offentlige on-chain-data. Vær likevel bevisst på å presentere vurderinger av navngitte lommebøker. |

**Hva vanskelighetsgraden betyr for dere:**

- _Vanskelig:_ Et vanskelig prosjekt gir større mulighet for toppkarakter, men også større risiko. Definer en minimal versjon som sikkert kan bli ferdig, og legg resten i tydelige trinn etterpå.

En merknad: briefen skriver at en «load-bearing AI component» i appen teller i vurderingen. Sensorveiledningen legger vekt på hvordan dere styrer og kvalitetssikrer KI-assistert utvikling, og på vanskelighetsgrad og gjennomføring. Den krever ikke språkmodell i selve appen. Hold gjerne LLM-delene, men velg dem fordi de gir verdi for brukeren.

### Gjennomførbarhet med BMAD og Claude Code

Dere skal planlegge med BMAD (product brief → PRD → arkitektur → epics og stories) og implementere med Claude Code. Vurderingen under tar hensyn til at det må være tid til hele denne flyten, og til testing, retting og README til slutt.

| Spørsmål | Vurdering (OK / risiko / stor risiko) | Kommentar |
|---|---|---|
| **Tid og omfang** – kan v1 realistisk bli ferdig og stabil i løpet av semesteret, med tid til flere iterasjoner? | risiko | Seks punkter i v1 for én person, der tre av dem (randomiseringstest, analyse per domene og bot-filtrering) er krevende hver for seg. |
| **BMAD-flyten** – er briefen konkret nok til at PRD, arkitektur og stories kan lages uten store hull, og blir det overkommelig mange stories? | OK | Løsningen er konkret beskrevet i fem trinn. PRD-en må presisere metoden: hva som stokkes, antall permutasjoner, minste antall løste handler og signifikansnivå. |
| **Egnet for Claude Code** – bruker løsningen en vanlig, godt dokumentert teknologistakk som Claude Code håndterer godt, eller krever den nisjeteknologi, spesialmaskinvare eller mye manuell konfigurasjon? | OK | Python med pandas/numpy og et enkelt webgrensesnitt er godt egnet. Polymarkets API er mindre godt dokumentert og kan kreve prøving. |
| **Kontroll på KI-ens arbeid** – kan gruppen selv avgjøre om koden gjør det riktige? Krever domenet kunnskap gruppen ikke har, f.eks. avanserte beregninger eller fagregler, så er det vanskelig å kvalitetssikre. | stor risiko | En permutasjonstest kan se riktig ut og likevel være feil, for eksempel ved at feil ting stokkes eller at PnL ikke beregnes likt i ekte og stokket data. Uten tester mot data med kjent fasit er det vanskelig å vite om verdiktene stemmer. |
| **Testbarhet** – finnes det tydelige regler og forventede resultater som tester kan skrives mot? | risiko | Godt egnet for tester hvis dere lager syntetiske data. Tilfeldig lommebok skal gi p > 0,05 i de fleste kjøringer, og en lommebok som alltid treffer, skal gi p < 0,01. Bot-heuristikkene trenger egne konstruerte eksempler. |
| **Kjørbar for sensor** – kan appen kjøres lokalt etter README, uten gruppens nøkler, betalte kontoer eller egen infrastruktur? | risiko | Polymarkets offentlige API krever ikke nøkkel, men kan endre seg eller være tregt. LLM-delen krever nøkkel. Lag et lokalt datasett og en mock-modus. |
| **Avhengigheter og kostnader** – krever løsningen betalte API-er, f.eks. språkmodeller, og finnes det en plan for kostnad, testmodus eller mock-data? | risiko | Domeneklassifisering av mange markeder gir mange LLM-kall. Lagre klassifiseringen per marked, slik at hvert marked bare klassifiseres én gang. |

**Konklusjon om gjennomførbarhet:**

- **Gjennomførbart med justert omfang.** Se forslagene under.

**Forslag til justering av omfang eller vanskelighetsgrad:**

1. Bygg i trinn. Trinn 1 er datainnhenting med lokal lagring, randomiseringstest for hele lommeboken og et webgrensesnitt med verdikt og konfidens. Trinn 2 er domeneklassifisering og test per domene. Trinn 3 er bot- og market maker-heuristikker og LLM-forklaringer. Hvert trinn gir en fungerende app.
2. Lag et syntetisk testdatasett tidlig, med simulerte lommebøker der dere vet svaret, og bruk det både som enhetstester og som demo for sensor. Det gjør kvalitetssikringen synlig og troverdig.

## Hvorfor product brief er viktig for mappen

Product brief er utgangspunktet for PRD, arkitektur, stories og til slutt koden. Del 1 av mappen vurderes blant annet på om sensor kan følge en sporbar vei fra plan til ferdig app. Den vurderes også på om appen gjør det dere har beskrevet, om den er testet, om den er godt designet, og om den kan kjøres etter README. Et uklart, for stort eller for lite brief gjør alt dette vanskeligere senere. Det er mye enklere å rette nå enn sent i semesteret.

## 1. Gjennomgang av briefens deler

| Del av brief | Status | Kommentar |
|---|---|---|
| Executive Summary – er det klart hva appen er, og hvilket problem den løser? | OK | Klart: et verktøy som gir et ferdighetsverdikt i stedet for et PnL-tall for Polymarket-lommebøker. |
| The Problem – er problemet konkret, med reelle situasjoner og brukere? | OK | Konkret, med eksempler på dagens verktøy og tall om wash trading. Kilder til studiene (Yale SOM, Columbia, arXiv) bør lenkes, slik at påstandene kan etterprøves. |
| The Solution – beskriver løsningen brukeropplevelsen, ikke bare teknologi? | Juster | De fem trinnene er tydelige, men handler mest om databehandling. Beskriv kort hva brukeren ser: skjermbildet med verdikt, konfidens og fordeling per domene, og hva som skjer når en lommebok har for få løste handler. |
| What Makes This Different – er vurderingen ærlig og realistisk? | OK | Ærlig om at data er offentlige og at fortrinnet bare ligger i metoden, og om begrensningene i bot-deteksjonen. |
| Who This Serves – er primærbrukerne tydelige, og vet vi hva de trenger? | Juster | To «primary»-brukere (andre tradere og forfatteren selv). Velg én for v1, og beskriv hva de trenger å se for å stole på et verdikt. |
| Success Criteria – kan kriteriene faktisk sjekkes eller testes? | Endre | Kriteriene handler om kursleveransen og om et uformelt backtest. Legg til kriterier som «for en syntetisk lommebok med tilfeldige handler gir testen ikke ‹skilled› i minst 95 % av kjøringene», «for en lommebok med færre enn N løste handler vises ‹ikke nok data› i stedet for et verdikt», «samme lommebok og samme seed gir samme resultat» og «LLM-forklaringen gjengir samme konfidensnivå som den statistiske testen». |
| Scope – er det klart hva som er med i første versjon, og hva som ikke er det? | Juster | Tydelig delt i «In for v1» og «Explicitly out». Del v1 i trinn som foreslått over, slik at det finnes en minimal versjon. |
| Vision – henger visjonen sammen med resten uten å blåse opp omfanget? | OK | Andre markeder og sybil-deteksjon er tydelig plassert i fremtiden, og dere sier eksplisitt at målet på kort sikt er smalere. |

## 2. Utgangspunkt for del 1 av mappen

Punktene følger kriteriene i sensorveiledningen for del 1. Vektene i parentes viser hvor mye hvert kriterium teller i del 1.

| Kriterium i del 1 | Hva briefen bør legge til rette for | Status | Kommentar |
|---|---|---|---|
| **1. Prosess og KI-styring** (30 %) | Brief som er presis nok til at PRD og stories kan bygges direkte på den, slik at krav kan spores fra brief til kode. | OK | Briefen er presis og ligger i BMAD-strukturen. Dokumenter beslutningene om metoden (antall permutasjoner, signifikansnivå) i PRD og arkitektur, slik at de kan spores. |
| **2. Funksjonalitet og omfang** (20 %) | Realistisk omfang for gruppen og semesteret: en tydelig kjerneflyt som kan bli ferdig og stabil, og nok innhold til å vise reell funksjonalitet. | Juster | Kjerneflyten «skriv inn lommebok → få verdikt» er tydelig. Omfanget rundt den bør trinndeles. |
| **3. Kvalitetssikring og testing** (15 %) | Suksesskriterier og funksjoner som er konkrete nok til å bli testtilfeller. | Endre | Grunnlaget for testene mangler i briefen. Legg til testbare kriterier og en plan for syntetiske testdata. |
| **4. Design og brukeropplevelse** (10 %) | Tydelige brukere og brukssituasjoner som designet kan bygges rundt, gjerne med de viktigste skjermbildene eller flytene skissert. | Juster | Det er en designutfordring å formidle statistisk usikkerhet forståelig. Skisser verdiktsiden tidlig. |
| **5. Kodekvalitet og arkitektur** (10 %) | Teknologivalg som er begrunnet og ikke mer komplekse enn appen trenger. | OK | Ingen teknologi er låst ennå. Hold den statistiske motoren som en ren, testbar modul atskilt fra API-henting og webgrensesnitt. |
| **6. README og kjørbarhet** (10 %) | Løsning som andre kan kjøre lokalt uten betalte kontoer, og uten tilgang til gruppens egne tjenester og nøkler. | Juster | Planlegg et lokalt eksempeldatasett og mock-modus for språkmodellen, slik at sensor ikke er avhengig av API-er eller nøkler. |
| **7. Ryddighet i repoet** (5 %) | En plan for hvor hemmeligheter, testdata og dokumentasjon skal ligge. | Juster | Bestem hvor hurtigbufrede data skal ligge (og om de skal committes), og hold LLM-nøkkelen i `.env` som ikke committes. |

## 3. Neste steg for gruppen

1. Skriv om Success Criteria med funksjonelle, testbare kriterier, særlig for randomiseringstesten og håndteringen av for lite data.
2. Beskriv metoden presist (hva som stokkes, antall permutasjoner, minste antall handler, signifikansnivå), og lag en plan for syntetiske testlommebøker med kjent fasit.
3. Del v1 i trinn, beskriv lokal kjøring med lagrede data og mock-modus, og gå videre til PRD.

Oppdater product brief i repoet når dere har gjort endringene, slik at historikken viser hvordan planen utviklet seg. Det er en del av prosessen sensor ser etter.
