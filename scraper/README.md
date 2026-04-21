# Bibel-scraper

Henter Bibel-oversettelser fra [bible.com](https://www.bible.com) (YouVersion)
med **vers-tekst, fotnoter, kryssreferanser og seksjonsoverskrifter**.

Basert på [tobiashellerslien/bible-scraper](https://github.com/tobiashellerslien/bible-scraper)
(MIT-lisens), men utvidet til å fange all metadata bible.com leverer.

## Installasjon

```bash
pip install requests beautifulsoup4
```

## Bruk

### Scrape en hel oversettelse

```bash
# Med registrert versjonsnavn (fra book_maps.py → TRANSLATION_IDS)
python scrape_entire_bible.py --version Bibel2011

# Eller direkte translation ID (fra bible.com-URL)
python scrape_entire_bible.py --translation-id 29 --lang norwegian

# Bare noen bøker
python scrape_entire_bible.py --version NB88 --only JHN,ROM,1CO
```

Utdata lagres i `../bible_versions/<VersjonsNavn>/NN_USFM_BokNavn.json`
så det plugger rett inn i hovedappen.

### Test scraperen på ett kapittel

```bash
python bible_scraper.py  # kjører innebygd test: Johannes 3 i NB88
```

### Bruke som modul

```python
from bible_scraper import fetch_chapter, fetch_book

# Henter hele Johannes 3 med footnotes og xrefs
data = fetch_chapter("JHN", 3, 102)  # 102 = NB88
print(data["JHN.3.16"])
# {
#   "text": "For så har Gud elsket verden ...",
#   "footnotes": [{"marker": "a", "text": "..."}],
#   "xrefs": [{"marker": "†", "text": "Rom 5.8", "refs": ["ROM.5.8"]}],
#   "section": "Nikodemus"
# }
```

## JSON-format

Hver JSON-fil (én per bok) har USFM-keys som tidligere, men verdiene er nå
strukturerte objekter:

```json
{
  "GEN.1.1": {
    "text": "I begynnelsen skapte Gud himmelen og jorden.",
    "footnotes": [
      {"marker": "a", "text": "Eller 'da Gud begynte å skape'"}
    ],
    "xrefs": [
      {"marker": "†", "text": "Joh 1,1-3", "refs": ["JHN.1.1", "JHN.1.2", "JHN.1.3"]}
    ],
    "section": "Skapelsen"
  }
}
```

### Felt

| Felt        | Type       | Beskrivelse                                                      |
| ----------- | ---------- | ---------------------------------------------------------------- |
| `text`      | string     | Selve vers-teksten (mellomrom normalisert, noter tatt ut)        |
| `footnotes` | array      | Translator-noter (oversetter-kommentarer, alternative lesemåter) |
| `xrefs`     | array      | Kryssreferanser til andre bibelsteder                            |
| `section`   | string\|null | Navn på seksjonen dette verset starter (null hvis midten av seksjon) |

### Fotnote-struktur

```json
{"marker": "a", "text": "Eller 'da Gud begynte å skape'"}
```

### Kryssreferanse-struktur

```json
{
  "marker": "†",
  "text": "Joh 1,1-3",
  "refs": ["JHN.1.1", "JHN.1.2", "JHN.1.3"]
}
```

`refs` er parsede USFM-koder som kan brukes til direkte lenking.

## Rate-limiting

Standard er 0.1 sekunder mellom kapittel-requests. Juster med `--sleep`
hvis du vil være mer/mindre forsiktig.

## Lagt til nye versjoner

Åpne `book_maps.py` og legg til en ny oppføring i `TRANSLATION_IDS`.
Translation ID finner du i URL-en på bible.com når du leser et kapittel:
`https://www.bible.com/bible/**102**/GEN.1` → ID er `102`.

## Bakoverkompatibilitet med eksisterende JSON-filer

Appens server (`server.py`) forstår både det gamle formatet
(`{"GEN.1.1": "tekst"}`) og det nye strukturerte formatet — ingen
eksisterende data blir ugyldig.
