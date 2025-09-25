# Stoltzen Result Scraper

Et Python-script som henter og parser løpsresultater fra Stoltzekleiven Opp 2024 for Cowi-teamet.

## Funktionalitet

Scriptet:
1. Henter HTML fra en spesifisert URL (sendes som argument)
2. Parser resultat-tabellen og kategoriserer deltakerne i:
   - **Mann**
   - **Dame** 
   - **Pluss**
3. For hver deltaker henter den profil-informasjon fra `http://stoltzen.no/statistikk/stat.php?id=XXXXX`
4. Ekstraherer historisk data inkludert:
   - Antall deltagelser totalt
   - Beste tidligere tid (før 2024)
   - År for beste tidligere tid
   - Om årets tid er en ny personlig rekord
5. Skriver ut strukturert JSON til stdout

## Installasjon

```bash
# Klon/last ned prosjektet
git clone <repository-url>
cd stoltzen-result-scraper

# Installer avhengigheter
pip install -r requirements.txt
```

## Bruk

### Windows Batch Scripts (Anbefalt)

```cmd
# Enkel kjøring - kjører automatisk og åpner resultatet
quick_run.bat

# Standard kjøring med feilhåndtering
run_scraper.bat

# Avansert meny med flere alternativer
run_scraper_advanced.bat

# Oppdater requirements.txt automatisk
update_requirements.bat
```

### Direkte Python-kommandoer

```bash
# Kjør scriptet med URL som argument
python stoltzen_scraper.py "http://stoltzen.no/resultater/2024/resklubb_16.html"

# Lagre resultater til fil
python stoltzen_scraper.py "http://stoltzen.no/resultater/2024/resklubb_16.html" > results.json

# Kun JSON-output (skjul progresinfo)
python stoltzen_scraper.py "http://stoltzen.no/resultater/2024/resklubb_16.html" 2>nul

# Vis hjelp
python stoltzen_scraper.py --help
```

## JSON-struktur

```json
{
  "Mann": [
    {
      "Navn": "Ola Nordman",
      "Tid": "11:12",
      "Klasse": "Menn 35-39 år",
      "Deltagelser": 3,
      "BesteTidligere": "11:29",
      "BesteÅr": 2023,
      "NyBestetid": true,
      "Differanse": "-0:17"
    }
  ],
  "Dame": [...],
  "Pluss": [...]
}
```

## Tekniske detaljer

- **Concurrent HTTP requests**: Bruker `ThreadPoolExecutor` for parallell henting av profiler (maks 10 samtidige)
- **Robust parsing**: Håndterer manglende data gracefully - setter til `null` hvis ikke funnet
- **Tidsformat-parsing**: Normaliserer tidsformater fra "1:23:45" til "1:23:45" eller "23:45"
- **Feilhåndtering**: Fortsetter selv om enkelte profiler ikke kan hentes
- **Progress info**: Skriver progresinfo til stderr, JSON til stdout

## Avhengigheter

- `requests>=2.28.0` - HTTP-forespørsler
- `beautifulsoup4>=4.11.0` - HTML-parsing

## Struktur

```
stoltzen-result-scraper/
├── stoltzen_scraper.py        # Hovedscript
├── requirements.txt           # Python-avhengigheter
├── quick_run.bat             # Enkel Windows batch-kjøring
├── run_scraper.bat           # Standard Windows batch med feilhåndtering
├── run_scraper_advanced.bat  # Avansert Windows batch med meny
├── update_requirements.bat   # Automatisk requirements.txt oppdatering
├── .gitignore                # Git ignore-regler
├── results.json              # Siste kjørte resultater (ikke i Git)
└── README.md                 # Denna filen
```

## Nye funksjoner

- **NyBestetid**: Boolean som viser om årets tid er en personlig rekord
- **Differanse**: Tidsdifferanse mellom årets tid og beste tidligere tid (f.eks. "-0:17" = 17 sekunder raskere, "+1:23" = 1 minutt 23 sekunder tregere)
- **Klasse**: Full klassebeskriving (f.eks. "Menn 35-39 år")
- **URL-argument**: Fleksibel URL-input for ulike resultatsider
- **Forbedret kategorisering**: Mann/Dame/Pluss i stedet for Menn/Kvinner/Pluss 90kg
- **Sortering**: Deltakere sorteres etter beste tid (raskeste først) innenfor hver kategori
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
- Verifiser at "BesteÅr" er før 2024

Hvis nordiske bokstaver vises feil:
- Sørg für at JSON-filen åpnes med UTF-8 encoding
- Scriptet håndterer automatisk encoding-problemer fra norske nettsider

## Git og versjonskontroll

Results.json-filer er ekskludert fra Git via `.gitignore` siden disse inneholder scrapet data som endrer seg ved hver kjøring. Dette holder repositoryet rent og fokusert på kildekoden.