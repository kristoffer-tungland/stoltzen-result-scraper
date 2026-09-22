# Stoltzen Result Scraper

Et Python-script som henter og parser løpsresultater fra Stoltzekleiven Opp for COWI-teamet.

For årets løp (2026) er EQ Timing kilden til løpstiden samme dag. Stoltzen brukes
fortsatt som kilde til historiske tider og antall tidligere deltagelser.

## Funktionalitet

Scriptet:
1. Henter HTML fra en spesifisert URL (sendes som argument)
2. Parser resultat-tabellen og kategoriserer deltakerne i:
   - **Dame**
   - **Mann** 
   - **Pluss**
3. For hver deltaker henter den profil-informasjon fra `http://stoltzen.no/statistikk/stat.php?id=XXXXX`
4. Ekstraherer historisk data inkludert:
   - Antall deltagelser totalt
   - Beste tidligere tid før årets løpsår
   - År for beste tidligere tid
   - Om årets tid er en ny personlig rekord
5. Skriver resultater til en CSV-fil (`results.csv`) sortert etter gruppe og tid

## Installasjon

```bash
# Klon/last ned prosjektet
git clone <repository-url>
cd stoltzen-result-scraper

# Installer avhengigheter
pip install -r requirements.txt
```

## Bruk

### EQ Timing 2026 (anbefalt)

Kjør den nye standardflyten fra prosjektmappen:

```cmd
run_eqtiming_2026.bat
```

Dette bruker EQ Timing-arrangement `78640`, søker etter klubben `COWI`, bruker
2026 som løpsår og skriver `results.csv`. Scriptet henter årets data fra EQ
Timing og prøver deretter å berike hver deltager med historikk fra Stoltzen.
Resultater som ennå ikke har passert mål får tom `Tid`; de beholdes i CSV-en
slik at startlisten kan vises før målgang.

Samme flyt kan kjøres direkte med Python:

```cmd
python src\eqtiming_scraper.py --event-id 78640 --club COWI --year 2026 --output results.csv
```

Nyttige valg:

- `--no-history` hopper over kallene til Stoltzen og er nyttig for rask live-oppdatering.
- `--event-id ID` velger et annet EQ Timing-arrangement.
- `--club NAVN` endrer klubb-/teamsøket.
- `--year ÅR` angir hvilket år som skal behandles som årets løp.
- `--output FIL` velger CSV-filen.
- `--timeout SEKUNDER` angir HTTP-timeout.

Åpne deretter `results_viewer.html`. Den laster automatisk `results.csv` når
den kjøres via lokal webserver, eller du kan dra CSV-filen inn i filvelgeren.

### Windows Batch Scripts (Anbefalt for eldre Stoltzen-flyt)

```cmd
# Enkel kjøring - spør om URL og åpner resultatet
quick_run.bat

# Standard kjøring med URL-input og feilhåndtering
run_scraper.bat

# Alternativ scraper - bruker liste med stat.php URLs
run_stat_scraper.bat

# Avansert meny med flere alternativer
run_scraper_advanced.bat

# Oppdater requirements.txt automatisk
update_requirements.bat
```

### URL-input

Alle batch scripts spør nå om URL-en til resultatsiden:
- **Standard URL**: `http://stoltzen.no/resultater/2024/resklubb_16.html` (historisk COWI-side)
- **Custom URL**: Skriv inn egen URL for andre klubber eller år
- **Tom input**: Trykk Enter for å bruke standard URL

### Alternativ metode: Stat URL Scraper

I tillegg til hovedscriptet som scraper resultatsider, finnes det en alternativ metode som henter data direkte fra individuelle deltakerprofiler:

**Oppsett:**
1. Opprett en tekstfil med stat.php URLer (en per linje)
2. Kjør `run_stat_scraper.bat` eller Python-scriptet direkte

**URL-fil format (`src/stat_urls.txt`):**
```
# Kommentarer starter med #
http://stoltzen.no/statistikk/stat.php?id=68772
http://stoltzen.no/statistikk/stat.php?id=12345
http://stoltzen.no/statistikk/stat.php?id=67890
```

**Fordeler:**
- Kan hente spesifikke deltakere du er interessert i
- Fungerer selv om resultatsiden ikke er tilgjengelig
- Samme CSV-output som hovedscriptet
- Raskere for få deltakere (unngår å parse hele resultatsiden)

**Bruksområder:**
- Følge med på spesifikke venner/kolleger
- Sammenligne historisk utvikling for utvalgte løpere
- Backup-metode når resultatsider er utilgjengelige

### HTML Resultatvisning

`results_viewer.html` er en interaktiv webside som automatisk laster data fra `results.csv`:

**Funksjoner:**
- **Fleksibel filinnlasting**: Drag-and-drop eller filvelger for CSV-filer
- **Automatisk prøving**: Forsøker å laste `results.csv` automatisk
- **Komplett filtrering**: Søk, gruppe, klasse og ny bestetid filtre
- **Sortering**: Klikk på kolonneheader for å sortere
- **Responsivt design**: Fungerer på desktop og mobil
- **Statistikk**: Live oppdatering av tall basert på filtre
- **CORS-sikker**: Fungerer når åpnet som lokal fil

**Bruk:**
1. Kjør en av scraperne for å generere `results.csv`
2. Åpne `results_viewer.html` i nettleseren
3. **Metode 1**: Dra og slipp `results.csv` på dropområdet
4. **Metode 2**: Klikk på dropområdet og velg CSV-fil
5. **Metode 3**: Klikk "🔄 Prøv å last results.csv" (fungerer kun med lokal server)

### Direkte Python-kommandoer

```bash
# Hovedscript - kjør med URL som argument (genererer results.csv)
python src/stoltzen_scraper.py \"http://stoltzen.no/resultater/2024/resklubb_16.html\"

# Alternativ scraper - kjør med URL-fil
python src/stoltzen_stat_scraper.py \"src/stat_urls.txt\"

# Skjul progresinfo (kun vis hovedutskrift)
python src/stoltzen_scraper.py \"http://stoltzen.no/resultater/2024/resklubb_16.html\" 2>nul

# Vis hjelp
python src/stoltzen_scraper.py --help
python src/stoltzen_stat_scraper.py --help
python src/eqtiming_scraper.py --help
```

## CSV-struktur

Resultatet lagres i `results.csv` med følgende kolonner sortert etter gruppe (Dame, Mann, Pluss) og tid (beste først):

```csv
Gruppe,Navn,Tid,Klasse,Deltagelser,BesteTidligere,BesteÅr,NyBestetid,Differanse
Dame,Ingvild Erdal,11:58,Kvinner 18-34 år,3,12:30,2023,True,-0:32
Mann,Ole Eirik Foshaugen,11:12,Menn 35-39 år,3,11:29,2023,True,-0:17
Pluss,Jon Laurits Strand,13:52,Pluss 90kg,4,13:37,2022,False,+0:15
```

**Kolonneforklaring:**
- **Gruppe**: Dame, Mann eller Pluss
- **Navn**: Deltakerens navn
- **Tid**: Årets løpstid
- **Klasse**: Aldersklasse/kategori
- **Deltagelser**: Totalt antall deltagelser
- **BesteTidligere**: Beste tidligere tid før årets løpsår
- **BesteÅr**: År for beste tidligere tid
- **NyBestetid**: True hvis årets tid er ny personlig rekord
- **Differanse**: Tidsdifferanse fra beste tidligere (+tregere, -raskere)

## Tekniske detaljer

- **Concurrent HTTP requests**: Bruker `ThreadPoolExecutor` for parallell henting av Stoltzen-historikk (maks 10 samtidige)
- **Robust parsing**: Håndterer manglende data gracefully - setter til `null` hvis ikke funnet
- **Tidsformat-parsing**: Normaliserer tidsformater fra "1:23:45" til "1:23:45" eller "23:45"
- **Feilhåndtering**: Fortsetter selv om enkelte profiler ikke kan hentes
- **CSV Output**: Skriver resultater til `results.csv` fil med UTF-8 encoding
- **Progress info**: Skriver progresinfo til stderr

## Avhengigheter

- `requests>=2.28.0` - HTTP-forespørsler
- `beautifulsoup4>=4.11.0` - HTML-parsing

## Struktur

```
stoltzen-result-scraper/
├── src/                              # Kildekode-mappe
│   ├── eqtiming_scraper.py           # EQ Timing 2026 + Stoltzen-historikk
│   ├── stoltzen_scraper.py          # Eldre scraper (Stoltzen-resultatsider)
│   ├── stoltzen_stat_scraper.py     # Alternativt script (scraper stat URLs)
│   ├── stat_urls.txt                # Eksempel URL-fil for stat scraper
│   ├── requirements.txt             # Python-avhengigheter
│   └── update_requirements.bat      # Automatisk requirements oppdatering
├── quick_run.bat                    # Enkel Windows batch-kjøring
├── run_eqtiming_2026.bat            # Anbefalt kjøring for 2026
├── run_scraper.bat                  # Eldre Windows batch med feilhåndtering
├── run_stat_scraper.bat             # Batch for stat URL scraper
├── run_scraper_advanced.bat         # Avansert Windows batch med meny
├── results_viewer.html              # HTML-visning av resultater (laster data fra results.csv)
├── .gitignore                       # Git ignore-regler
├── results.csv                      # Siste kjørte resultater (ikke i Git)
└── README.md                        # Denna filen
```

## Nye funksjoner

- **NyBestetid**: Boolean som viser om årets tid er en personlig rekord
- **Differanse**: Tidsdifferanse mellom årets tid og beste tidligere tid (f.eks. "-0:17" = 17 sekunder raskere, "+1:23" = 1 minutt 23 sekunder tregere)
- **Klasse**: Full klassebeskriving (f.eks. "Menn 35-39 år")
- **URL-argument**: Fleksibel URL-input for ulike resultatsider
- **Forbedret kategorisering**: Mann/Dame/Pluss i stedet for Menn/Kvinner/Pluss 90kg
- **Sortering**: Resultater sorteres først etter gruppe (Dame, Mann, Pluss) og deretter etter tid (beste tid først)
- **CSV-format**: Strukturert CSV-fil med UTF-8 encoding for enkel bruk i Excel og andre verktøy
- **Norske tegn**: Korrekt håndtering av æøå og andre nordiske bokstaver i UTF-8 format

## Ytelse

- Henter ~90 deltakere på ca. 10-15 sekunder
- Parallelle HTTP-forespørsler for optimal hastighet
- Respekterer serverens begrensninger med max 10 samtidige connections

## Feilsøking

Hvis scriptet ikke finner deltakere:
1. Sjekk at URL-en er korrekt og tilgjengelig
2. Verifiser at tabellstrukturen på siden ikke har endret seg
3. Sjekk nettverkstilkobling

Hvis noen profiler mangler data:
- Dette er normalt - ikke alle deltakere har komplette historiske data
- Manglende felter settes til `null` som spesifisert

Hvis "NyBestetid" vises som `false` når det burde være `true`:
- Sjekk at tidsformatene kan sammenlignes korrekt
- Verifiser at "BesteÅr" er før årets løpsår (for standardflyten før 2026)

Hvis nordiske bokstaver vises feil:
- Sørg für at JSON-filen åpnes med UTF-8 encoding
- Scriptet håndterer automatisk encoding-problemer fra norske nettsider

## Git og versjonskontroll

Results.csv-filer er ekskludert fra Git via `.gitignore` siden disse inneholder scrapet data som endrer seg ved hver kjøring. Dette holder repositoryet rent og fokusert på kildekoden.
