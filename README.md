# BibleGateway at home

A local Bible search app with some Norwegian and English translations. Look up multiple verses by reference, search full text, and compare versions side by side.

## Usage

```bash
python server.py
```

Opens `http://127.0.0.1:8421` in your browser automatically. The server shuts down when you close the tab.

## Search examples

- `Johannes 3:16` — single verse
- `1. Mosebok 1:1-3` — verse range
- `Salme 23` — whole chapter
- `Joh 3:16;17` — multiple passages (semicolon-separated, context carries over)
- `nåde` — full-text search across the entire Bible

Abbreviations and English book names work too: `joh`, `1. mos`, `rom`, `genesis`.

## Adding a Bible version

Drop a folder into `bible_versions/` containing 66 JSON files named `NN_USFM_BookName.json` (e.g. `43_JHN_Johannes.json`). Each file maps `BOOK.CHAPTER.VERSE` keys to verse text:

```json
{
  "JHN.1.1": "I begynnelsen var Ordet...",
  "JHN.1.2": "Han var i begynnelsen hos Gud."
}
```

The server auto-discovers the new version on next start. Add an entry to `VERSION_DISPLAY` in `index.html` if the folder name needs a prettier display label.
