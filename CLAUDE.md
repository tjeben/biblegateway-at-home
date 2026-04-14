# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
python server.py
```

Starts an HTTP server at `http://127.0.0.1:8421`, auto-opens the browser, and shuts down when the browser tab is closed. No build step, no external dependencies — only Python standard library.

## Architecture

**Two-file application**: `server.py` (Python backend) and `index.html` (single-page frontend with embedded JS/CSS).

### server.py

- HTTP server on port 8421 using `http.server`
- Loads all Bible versions from `bible_versions/` into memory at startup (`BibleData` class)
- **Book alias system**: `BOOKS` list defines USFM codes, Norwegian names, and aliases (Norwegian, English, abbreviations). `ALIAS_MAP` provides case-insensitive lookup, `SORTED_ALIASES` enables longest-match-first parsing. `USFM_TO_ENG` maps codes to English display names.
- **Query parser**: `parse_query()` splits on `;` into blocks. Context carries across blocks: a bare number after a `chapter:verse` block becomes a verse in the same chapter (e.g., `Joh 3:16;17` → John 3:16 and John 3:17); a bare number without prior verse context becomes a chapter. `identify_book()` uses longest-match-first against `SORTED_ALIASES`. `is_reference_query()` returns true if the first semicolon-part resolves to a known book.
- **Text search** (`search_text()`): case-insensitive substring AND-match across all words, hard-capped at 150 results.
- **Shutdown watchdog**: frontend pings `/api/heartbeat` every 3 seconds; a daemon thread calls `os._exit(0)` after 10 seconds without a ping.
- **API endpoints**:
  - `/api/versions` → `{versions: [...]}`
  - `/api/books?version=NB88` → `{books: [{code, name, name_en, chapters}, ...]}`
  - `/api/search?q=...&version=NB88` → `{type: "reference"|"text_search", results: [...], version}`
  - `/api/all_versions?q=...` → runs reference parse across every loaded version; `{results: {versionName: [blocks]}}`
  - `/api/heartbeat` → resets shutdown timer

### index.html

- All JS inline in a `<script>` block, all CSS inline in `<style>`
- State variables track current view (`normal`, `text_search`, `all_versions`), compare mode, and cached data for re-rendering on toggle changes (`allVersionsCache`, `textSearchCache`, `mainData`, `compareData`). `previousState` enables back-navigation from text search drill-down.
- **Compare mode**: calls `/api/search` twice (once per version) and renders results side-by-side. **All versions mode**: calls `/api/all_versions` and renders a column per version.
- `VERSION_DISPLAY` maps folder names to display names (e.g., `NB88` → `NB88/07`). Falls back to the raw folder name if no entry.
- `BIBLEHUB_SLUGS` and `ENG_NAMES` provide client-side book code mappings for interlinear links and language toggle.
- `translateLabel(label, bookCode)` swaps Norwegian book names in server labels for the currently selected language (`bookLang`: `"no"` or `"en"`).
- Dark mode is toggled via `data-theme="dark"` on the `<html>` element.

## Bible Data Format

Each version is a folder under `bible_versions/` containing 66 JSON files named `NN_USFM_BookName.json` (e.g., `43_JHN_Johannes.json`). The USFM code in the filename is what the server uses as the book identifier.

```json
{
  "JHN.1.1": "In the beginning was the Word...",
  "JHN.1.2": "He was in the beginning with God."
}
```

Keys are `BOOK.CHAPTER.VERSE`. All data is loaded into memory at startup.

## Key Patterns

- **Adding a new Bible version**: Drop a folder with correctly-named JSON files into `bible_versions/`. The server auto-discovers it. Add a display name entry to `VERSION_DISPLAY` in index.html if the folder name isn't presentation-ready.
- **Adding a new book alias**: Add to the relevant tuple in the `BOOKS` list in server.py. Aliases are lowercase.
- **Adding a new USFM book code**: If a scraped Bible uses a non-standard USFM code (like `NAM` instead of `NAH` for Nahum), the `BOOKS` entry must match the code used in the JSON filenames.
- **Theming**: CSS variables in `:root` and `[data-theme="dark"]` control all colors. Accent color is red (`#a83232` light / `#c94444` dark). The `data-theme` attribute is set on `<html>`.
