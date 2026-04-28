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
- **Data backend: SQLite (`bible.db`).** `BibleData` opens the database once with `check_same_thread=False` and WAL mode; verse text is queried on-demand, only metadata (translations, version_books, book_chapters, book_groups) is cached in memory. The 91 MB `bible.db` file is gitignored — fetch separately. Old `bible_versions/` JSON folders + `cross_references_openbible.txt` are no longer used.
- **Version names**: frontend keeps using folder-style names (`NB88`, `Bibel2011`); `VERSION_NAME_MAP` in `server.py` maps these to `translations.name` rows in the DB.
- **Book alias system**: `BOOKS` list defines USFM codes, Norwegian names, and aliases (Norwegian, English, abbreviations). `ALIAS_MAP` provides case-insensitive lookup, `SORTED_ALIASES` enables longest-match-first parsing. `USFM_TO_ENG` maps codes to English display names.
- **Query parser**: `parse_query()` splits on `;` into blocks. Context carries across blocks: a bare number after a `chapter:verse` block becomes a verse in the same chapter (e.g., `Joh 3:16;17` → John 3:16 and John 3:17); a bare number without prior verse context becomes a chapter. `identify_book()` uses longest-match-first against `SORTED_ALIASES`. `is_reference_query()` returns true if the first semicolon-part resolves to a known book.
- **Text search** (`search_text()`): quoted phrases use FTS5 (word-boundary match), bare words use SQL `LIKE` (substring), `-word` excludes via `NOT LIKE`, `+` between groups runs OR (union). Capped at `per_book` per book.
- **Cross-references**: served from the `cross_references` table (~345k OpenBible TSK rows), version-independent, formatted to USFM strings (`JHN.3.16`, `JHN.3.16-18`, `JHN.3.16-4.5`).
- **Section headings & footnotes**: fetched per chapter from the `headings` and `footnotes` tables and merged into verse objects (`section`, `footnotes` fields). Footnotes use a synthetic `#` marker since the DB doesn't store inline positions.
- **Shutdown watchdog**: frontend pings `/api/heartbeat` every 3 seconds; a daemon thread calls `os._exit(0)` after 10 seconds without a ping.
- **API endpoints**:
  - `/api/versions` → `{versions: [...]}`
  - `/api/books?version=NB88` → `{books: [{code, name, name_en, chapters}, ...]}`
  - `/api/search?q=...&version=NB88` → `{type: "reference"|"text_search", results: [...], version}`
  - `/api/all_versions?q=...` → runs reference parse across every loaded version; `{results: {versionName: [blocks]}}`
  - `/api/places?usfm=JHN.1.28` → `{places: [{id, name, aliases, placemark, kind, geometry}], scope: "verse", usfm}` (verse-level)
  - `/api/places?book=JHN&chapter=1` → same shape, but each place also has `verses: [int]`; `scope: "chapter"` (chapter-level)
  - `/api/places/has` → `{verses: ["JHN.1.28", ...], chapters: ["JHN.1", ...]}` — used by frontend at startup to disable the "📍 Kart"-button on verses/chapters without registered places
  - `/api/heartbeat` → resets shutdown timer

### index.html

- All JS inline in a `<script>` block, all CSS inline in `<style>`
- State variables track current view (`normal`, `text_search`, `all_versions`), compare mode, and cached data for re-rendering on toggle changes (`allVersionsCache`, `textSearchCache`, `mainData`, `compareData`). `previousState` enables back-navigation from text search drill-down.
- **Compare mode**: calls `/api/search` twice (once per version) and renders results side-by-side. **All versions mode**: calls `/api/all_versions` and renders a column per version.
- `VERSION_DISPLAY` maps folder names to display names (e.g., `NB88` → `NB88/07`). Falls back to the raw folder name if no entry.
- `BIBLEHUB_SLUGS` and `ENG_NAMES` provide client-side book code mappings for interlinear links and language toggle.
- **`📍 Kart` study element**: opens a Leaflet-based geographic map of biblical locations tied to the verse (or chapter, when not viewing a single verse). Backed by `/api/places` and `places` / `place_verses` tables. Button auto-disables when `PLACES_HAS` set (loaded from `/api/places/has` at startup) doesn't contain the relevant USFM-key. Chips above the map let the user toggle individual places on/off; map auto-fits remaining bounds. Cleanup (Leaflet `map.remove()` + ResizeObserver) happens in `closeVizHost`.
- **xref popover footer**: contains `Vis alle (N)`, `🗺️ Oversikt` (book heatmap of cross-references — formerly named `🗺️ Kart`), and `📈 Tidslinje`. Each button only renders when relevant (e.g., `Vis alle` only when collapsed; `Oversikt` only when refs span ≥2 books).
- `translateLabel(label, bookCode)` swaps Norwegian book names in server labels for the currently selected language (`bookLang`: `"no"` or `"en"`).
- Dark mode is toggled via `data-theme="dark"` on the `<html>` element.

## Bible Data Format (`bible.db`, SQLite + FTS5)

| Table | Description |
|-------|-------------|
| `translations` | `(id, name, full_name, language)` — Bible versions. `id` matches bible.com IDs. |
| `books` | `(usfm, order_num, name_no, name_en, testament)` — 66 books. |
| `verses` | `(id, translation_id, book_usfm, chapter, verse, text)`, indexed `(translation_id, book_usfm, chapter)`. |
| `headings` | `(translation_id, book_usfm, chapter, verse, text)` — section headings. |
| `footnotes` | `(translation_id, book_usfm, chapter, verse, text)` — translation footnotes. |
| `cross_references` | `(from_book, from_chapter, from_verse, to_book, to_chapter, to_verse_start, to_verse_end, to_chapter_end, votes)` — ~345k OpenBible TSK rows, version-independent. |
| `verses_fts` | FTS5 virtual table (content=verses, tokenize=unicode61). |
| `book_groups` + `book_group_members` | Named groups like `gt`, `nt`, `paulusbrevene`, `evangeliene`. Available in `BibleData.book_groups`; not yet wired into the search prefix parser. |
| `places` | `(id, name, aliases JSON, placemark, kind, geometry GeoJSON)` — ~1336 biblical locations. `kind` ∈ {`landpoint`, `region`, `water`, `path`, `waterpoint`}. `geometry` is GeoJSON `Point` / `LineString` / `Polygon`. Optional table; absent in older bible.db builds. |
| `place_verses` | `(place_id, book_usfm, chapter, verse)` — many-to-many between places and verses (~8700 rows). Indexed on `(book_usfm, chapter, verse)`. Optional table. |

`bible.db` is ~91 MB and is **not** committed to git (see `.gitignore`). Fetch it separately and place in project root.

## Key Patterns

- **Adding a new Bible version**: insert a row in `translations` and import verses/headings/footnotes. The `id` should match bible.com's translation ID. Add a display name entry to `VERSION_DISPLAY` in index.html, and a `VERSION_NAME_MAP` entry in server.py if the frontend name differs from the DB name.
- **Adding a new book alias**: Add to the relevant tuple in the `BOOKS` list in server.py. Aliases are lowercase.
- **Theming**: CSS variables in `:root` and `[data-theme="dark"]` control all colors. Accent color is red (`#a83232` light / `#c94444` dark). The `data-theme` attribute is set on `<html>`.
