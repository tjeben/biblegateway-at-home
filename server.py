"""
Bible Gateway Norsk - Local Bible search server
Run this file to start the server and open the website in your browser.
"""

import http.server
import json
import os
import re
import sqlite3
import sys
import webbrowser
import urllib.parse
import threading
import time

try:
    from google import genai as _genai
    _genai_client = _genai.Client()
    GENAI_AVAILABLE = True
except Exception:
    _genai_client = None
    GENAI_AVAILABLE = False
from pathlib import Path

PORT = 8421
BASE_DIR = Path(__file__).parent
BIBLE_DB = BASE_DIR / "bible.db"

# Mapping mellom URL-/frontend-versjonsnavn (gammelt mappe-navn) og translations.name i bible.db.
# Holder API-kontrakten stabil: frontend fortsetter å sende "NB88", "Bibel2011" osv.
VERSION_NAME_MAP = {
    # frontend-navn → DB translations.name
    "NB88":      "NB88/07",
    "BGO":       "BGO",
    "Bibel2011": "Bibel 2011",
    "Bibel1930": "Bibel 1930",
    "KJV":       "KJV",
    "ESV":       "ESV",
    "NIV":       "NIV",
    "NKJV":      "NKJV",
    "NASB1995":  "NASB 1995",
}
# Reverse: DB-navn → frontend-navn (det vi returnerer i /api/versions)
DB_TO_FRONTEND_NAME = {v: k for k, v in VERSION_NAME_MAP.items()}

# ──────────────────────────────────────────────
# Book alias mapping: alias → USFM code
# ──────────────────────────────────────────────

BOOKS = [
    # (usfm, order, norwegian_name, [aliases...])
    ("GEN", 1, "1. Mosebok", [
        "1. mosebok", "1.mosebok", "1 mosebok", "1mosebok",
        "1. mos", "1.mos", "1 mos", "1mos",
        "genesis", "gen", "1mo",
    ]),
    ("EXO", 2, "2. Mosebok", [
        "2. mosebok", "2.mosebok", "2 mosebok", "2mosebok",
        "2. mos", "2.mos", "2 mos", "2mos",
        "exodus", "exo", "exod", "ex", "2mo",
    ]),
    ("LEV", 3, "3. Mosebok", [
        "3. mosebok", "3.mosebok", "3 mosebok", "3mosebok",
        "3. mos", "3.mos", "3 mos", "3mos",
        "leviticus", "lev", "3mo",
    ]),
    ("NUM", 4, "4. Mosebok", [
        "4. mosebok", "4.mosebok", "4 mosebok", "4mosebok",
        "4. mos", "4.mos", "4 mos", "4mos",
        "numbers", "num", "4mo",
    ]),
    ("DEU", 5, "5. Mosebok", [
        "5. mosebok", "5.mosebok", "5 mosebok", "5mosebok",
        "5. mos", "5.mos", "5 mos", "5mos",
        "deuteronomy", "deut", "deu", "5mo",
    ]),
    ("JOS", 6, "Josva", [
        "josva", "jos", "joshua", "josh",
    ]),
    ("JDG", 7, "Dommerne", [
        "dommerne", "dom", "judges", "judg", "jdg",
    ]),
    ("RUT", 8, "Rut", [
        "rut", "ruth",
    ]),
    ("1SA", 9, "1. Samuelsbok", [
        "1. samuelsbok", "1.samuelsbok", "1 samuelsbok", "1samuelsbok",
        "1. sam", "1.sam", "1 sam", "1sam",
        "1. samuel", "1.samuel", "1 samuel", "1samuel",
        "1sa",
    ]),
    ("2SA", 10, "2. Samuelsbok", [
        "2. samuelsbok", "2.samuelsbok", "2 samuelsbok", "2samuelsbok",
        "2. sam", "2.sam", "2 sam", "2sam",
        "2. samuel", "2.samuel", "2 samuel", "2samuel",
        "2sa",
    ]),
    ("1KI", 11, "1. Kongebok", [
        "1. kongebok", "1.kongebok", "1 kongebok", "1kongebok",
        "1. kong", "1.kong", "1 kong", "1kong",
        "1. kings", "1.kings", "1 kings", "1kings",
        "1ki", "1kgs",
    ]),
    ("2KI", 12, "2. Kongebok", [
        "2. kongebok", "2.kongebok", "2 kongebok", "2kongebok",
        "2. kong", "2.kong", "2 kong", "2kong",
        "2. kings", "2.kings", "2 kings", "2kings",
        "2ki", "2kgs",
    ]),
    ("1CH", 13, "1. Krønikebok", [
        "1. krønikebok", "1.krønikebok", "1 krønikebok", "1krønikebok",
        "1. krøn", "1.krøn", "1 krøn", "1krøn",
        "1. chronicles", "1.chronicles", "1 chronicles", "1chronicles",
        "1ch", "1chr",
    ]),
    ("2CH", 14, "2. Krønikebok", [
        "2. krønikebok", "2.krønikebok", "2 krønikebok", "2krønikebok",
        "2. krøn", "2.krøn", "2 krøn", "2krøn",
        "2. chronicles", "2.chronicles", "2 chronicles", "2chronicles",
        "2ch", "2chr",
    ]),
    ("EZR", 15, "Esra", [
        "esra", "ezr", "ezra",
    ]),
    ("NEH", 16, "Nehemja", [
        "nehemja", "neh", "nehemiah",
    ]),
    ("EST", 17, "Ester", [
        "ester", "est", "esther",
    ]),
    ("JOB", 18, "Job", [
        "job",
    ]),
    ("PSA", 19, "Salme", [
        "salme", "salmene", "sal", "sl",
        "psalms", "psalm", "psa", "ps",
    ]),
    ("PRO", 20, "Ordspråkene", [
        "ordspråkene", "ordsp", "ords",
        "proverbs", "prov", "pro",
    ]),
    ("ECC", 21, "Forkynneren", [
        "forkynneren", "fork",
        "ecclesiastes", "eccl", "ecc", "eccles",
    ]),
    ("SNG", 22, "Høysangen", [
        "høysangen", "høys",
        "song of solomon", "song of songs", "song", "sng", "sos",
    ]),
    ("ISA", 23, "Jesaja", [
        "jesaja", "jes",
        "isaiah", "isa",
    ]),
    ("JER", 24, "Jeremia", [
        "jeremia", "jer",
        "jeremiah",
    ]),
    ("LAM", 25, "Klagesangene", [
        "klagesangene", "klag", "kl",
        "lamentations", "lam",
    ]),
    ("EZK", 26, "Esekiel", [
        "esekiel", "esek",
        "ezekiel", "ezek", "ezk",
    ]),
    ("DAN", 27, "Daniel", [
        "daniel", "dan",
    ]),
    ("HOS", 28, "Hosea", [
        "hosea", "hos",
    ]),
    ("JOL", 29, "Joel", [
        "joel", "jol",
    ]),
    ("AMO", 30, "Amos", [
        "amos", "amo", "am",
    ]),
    ("OBA", 31, "Obadja", [
        "obadja", "ob", "oba",
        "obadiah",
    ]),
    ("JON", 32, "Jona", [
        "jona",
        "jonah", "jon",
    ]),
    ("MIC", 33, "Mika", [
        "mika", "mi",
        "micah", "mic",
    ]),
    ("NAM", 34, "Nahum", [
        "nahum", "nah", "na", "nam",
    ]),
    ("HAB", 35, "Habakkuk", [
        "habakkuk", "hab",
    ]),
    ("ZEP", 36, "Sefanja", [
        "sefanja", "sef",
        "zephaniah", "zeph", "zep",
    ]),
    ("HAG", 37, "Haggai", [
        "haggai", "hag",
    ]),
    ("ZEC", 38, "Sakarja", [
        "sakarja", "sak",
        "zechariah", "zech", "zec",
    ]),
    ("MAL", 39, "Malaki", [
        "malaki", "mal",
        "malachi",
    ]),
    ("MAT", 40, "Matteus", [
        "matteus", "matt", "mat",
        "matthew",
    ]),
    ("MRK", 41, "Markus", [
        "markus", "mark", "mrk", "mk",
    ]),
    ("LUK", 42, "Lukas", [
        "lukas", "luk", "lk",
        "luke",
    ]),
    ("JHN", 43, "Johannes", [
        "johannes", "joh",
        "john", "jhn", "jn",
    ]),
    ("ACT", 44, "Apostlenes gjerninger", [
        "apostlenes gjerninger", "apostlenes", "apg",
        "acts", "act",
    ]),
    ("ROM", 45, "Romerne", [
        "romerne", "rom",
        "romans",
    ]),
    ("1CO", 46, "1. Korinterbrev", [
        "1. korinterbrev", "1.korinterbrev", "1 korinterbrev", "1korinterbrev",
        "1. kor", "1.kor", "1 kor", "1kor",
        "1. corinthians", "1.corinthians", "1 corinthians", "1corinthians",
        "1co", "1cor",
    ]),
    ("2CO", 47, "2. Korinterbrev", [
        "2. korinterbrev", "2.korinterbrev", "2 korinterbrev", "2korinterbrev",
        "2. kor", "2.kor", "2 kor", "2kor",
        "2. corinthians", "2.corinthians", "2 corinthians", "2corinthians",
        "2co", "2cor",
    ]),
    ("GAL", 48, "Galaterne", [
        "galaterne", "gal",
        "galatians",
    ]),
    ("EPH", 49, "Efeserne", [
        "efeserne", "ef", "efe",
        "ephesians", "eph",
    ]),
    ("PHP", 50, "Filipperne", [
        "filipperne", "fil",
        "philippians", "php", "phil",
    ]),
    ("COL", 51, "Kolosserne", [
        "kolosserne", "kol",
        "colossians", "col",
    ]),
    ("1TH", 52, "1. Tessalonikerbrev", [
        "1. tessalonikerbrev", "1.tessalonikerbrev", "1 tessalonikerbrev", "1tessalonikerbrev",
        "1. tess", "1.tess", "1 tess", "1tess",
        "1. thessalonians", "1.thessalonians", "1 thessalonians", "1thessalonians",
        "1th", "1thess",
    ]),
    ("2TH", 53, "2. Tessalonikerbrev", [
        "2. tessalonikerbrev", "2.tessalonikerbrev", "2 tessalonikerbrev", "2tessalonikerbrev",
        "2. tess", "2.tess", "2 tess", "2tess",
        "2. thessalonians", "2.thessalonians", "2 thessalonians", "2thessalonians",
        "2th", "2thess",
    ]),
    ("1TI", 54, "1. Timoteus", [
        "1. timoteus", "1.timoteus", "1 timoteus", "1timoteus",
        "1. tim", "1.tim", "1 tim", "1tim",
        "1. timothy", "1.timothy", "1 timothy", "1timothy",
        "1ti",
    ]),
    ("2TI", 55, "2. Timoteus", [
        "2. timoteus", "2.timoteus", "2 timoteus", "2timoteus",
        "2. tim", "2.tim", "2 tim", "2tim",
        "2. timothy", "2.timothy", "2 timothy", "2timothy",
        "2ti",
    ]),
    ("TIT", 56, "Titus", [
        "titus", "tit",
    ]),
    ("PHM", 57, "Filemon", [
        "filemon", "filem",
        "philemon", "phlm", "phm",
    ]),
    ("HEB", 58, "Hebreerne", [
        "hebreerne", "hebr", "heb",
        "hebrews",
    ]),
    ("JAS", 59, "Jakob", [
        "jakob", "jak",
        "james", "jas",
    ]),
    ("1PE", 60, "1. Peter", [
        "1. peter", "1.peter", "1 peter", "1peter",
        "1. pet", "1.pet", "1 pet", "1pet",
        "1pe",
    ]),
    ("2PE", 61, "2. Peter", [
        "2. peter", "2.peter", "2 peter", "2peter",
        "2. pet", "2.pet", "2 pet", "2pet",
        "2pe",
    ]),
    ("1JN", 62, "1. Johannesbrev", [
        "1. johannesbrev", "1.johannesbrev", "1 johannesbrev", "1johannesbrev",
        "1. joh", "1.joh", "1 joh", "1joh",
        "1. john", "1.john", "1 john", "1john",
        "1jn",
    ]),
    ("2JN", 63, "2. Johannesbrev", [
        "2. johannesbrev", "2.johannesbrev", "2 johannesbrev", "2johannesbrev",
        "2. joh", "2.joh", "2 joh", "2joh",
        "2. john", "2.john", "2 john", "2john",
        "2jn",
    ]),
    ("3JN", 64, "3. Johannesbrev", [
        "3. johannesbrev", "3.johannesbrev", "3 johannesbrev", "3johannesbrev",
        "3. joh", "3.joh", "3 joh", "3joh",
        "3. john", "3.john", "3 john", "3john",
        "3jn",
    ]),
    ("JUD", 65, "Judas", [
        "judas", "jud",
        "jude",
    ]),
    ("REV", 66, "Åpenbaringen", [
        "åpenbaringen", "åpenb", "åp",
        "openbaringen", "openb", "op",
        "revelation", "rev",
    ]),
]

# English book names
USFM_TO_ENG = {
    "GEN": "Genesis", "EXO": "Exodus", "LEV": "Leviticus", "NUM": "Numbers",
    "DEU": "Deuteronomy", "JOS": "Joshua", "JDG": "Judges", "RUT": "Ruth",
    "1SA": "1 Samuel", "2SA": "2 Samuel", "1KI": "1 Kings", "2KI": "2 Kings",
    "1CH": "1 Chronicles", "2CH": "2 Chronicles", "EZR": "Ezra", "NEH": "Nehemiah",
    "EST": "Esther", "JOB": "Job", "PSA": "Psalms", "PRO": "Proverbs",
    "ECC": "Ecclesiastes", "SNG": "Song of Solomon", "ISA": "Isaiah", "JER": "Jeremiah",
    "LAM": "Lamentations", "EZK": "Ezekiel", "DAN": "Daniel", "HOS": "Hosea",
    "JOL": "Joel", "AMO": "Amos", "OBA": "Obadiah", "JON": "Jonah", "MIC": "Micah",
    "NAM": "Nahum", "HAB": "Habakkuk", "ZEP": "Zephaniah", "HAG": "Haggai",
    "ZEC": "Zechariah", "MAL": "Malachi", "MAT": "Matthew", "MRK": "Mark",
    "LUK": "Luke", "JHN": "John", "ACT": "Acts", "ROM": "Romans",
    "1CO": "1 Corinthians", "2CO": "2 Corinthians", "GAL": "Galatians",
    "EPH": "Ephesians", "PHP": "Philippians", "COL": "Colossians",
    "1TH": "1 Thessalonians", "2TH": "2 Thessalonians",
    "1TI": "1 Timothy", "2TI": "2 Timothy", "TIT": "Titus", "PHM": "Philemon",
    "HEB": "Hebrews", "JAS": "James", "1PE": "1 Peter", "2PE": "2 Peter",
    "1JN": "1 John", "2JN": "2 John", "3JN": "3 John", "JUD": "Jude",
    "REV": "Revelation",
}

# Build alias lookup: lowercase alias → USFM code
ALIAS_MAP = {}
USFM_TO_NAME = {}
USFM_TO_ORDER = {}

for usfm, order, norw_name, aliases in BOOKS:
    USFM_TO_NAME[usfm] = norw_name
    USFM_TO_ORDER[usfm] = order
    # Add the USFM code itself as an alias
    ALIAS_MAP[usfm.lower()] = usfm
    # Add Norwegian name
    ALIAS_MAP[norw_name.lower()] = usfm
    # Add all aliases
    for alias in aliases:
        ALIAS_MAP[alias.lower()] = usfm

# Sort aliases by length descending for longest-match-first matching
SORTED_ALIASES = sorted(ALIAS_MAP.keys(), key=len, reverse=True)


# ──────────────────────────────────────────────
# Bible data — SQLite-backed
# ──────────────────────────────────────────────


def _format_xref_ref(to_book, to_chapter, to_verse_start, to_verse_end, to_chapter_end):
    """Bygg USFM-strenger som frontend forventer fra cross_references-rader.
    Eksempler:
      single:           JHN.3.16
      verse range:      JHN.3.16-18
      cross-chapter:    JHN.3.16-4.5
    """
    base = f"{to_book}.{to_chapter}.{to_verse_start}"
    if to_chapter_end and to_chapter_end != to_chapter:
        end_v = to_verse_end if to_verse_end else to_verse_start
        return f"{base}-{to_chapter_end}.{end_v}"
    if to_verse_end and to_verse_end != to_verse_start:
        return f"{base}-{to_verse_end}"
    return base


class BibleData:
    """SQLite-backed Bible data. Åpner bible.db én gang og lar tråder dele connection
    via check_same_thread=False (WAL-modus gjør samtidige lesninger trygt)."""

    def __init__(self):
        if not BIBLE_DB.exists():
            raise FileNotFoundError(
                f"bible.db not found at {BIBLE_DB}. "
                "Last ned databasen før du starter serveren."
            )
        self._conn = sqlite3.connect(
            str(BIBLE_DB), check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA query_only=1")
        self._lock = threading.Lock()  # serialiser SQL-kall — sqlite3-modulen er ikke fully reentrant

        # Metadata — caches
        self.translations = {}      # frontend_name → {id, db_name, full_name, language}
        self.version_books = {}     # frontend_name → [usfm_codes in canonical order]
        self.book_chapters = {}     # frontend_name → {usfm_code → max_chapter}
        self.book_groups = {}       # group_key (lowercase) → [usfm_codes]
        self._load_metadata()

    # ── intern: trådsikker spørring ──
    def _query(self, sql, params=()):
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def _query_one(self, sql, params=()):
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    # ── oppstart ──
    def _load_metadata(self):
        # Translations
        for row in self._query(
            "SELECT id, name, full_name, language FROM translations"
        ):
            db_name = row["name"]
            frontend_name = DB_TO_FRONTEND_NAME.get(db_name, db_name)
            self.translations[frontend_name] = {
                "id": row["id"],
                "db_name": db_name,
                "full_name": row["full_name"],
                "language": row["language"],
            }

        # version_books + book_chapters per oversettelse
        for fname, meta in self.translations.items():
            tid = meta["id"]
            rows = self._query(
                """
                SELECT v.book_usfm AS usfm, MAX(v.chapter) AS max_ch
                FROM verses v
                JOIN books b ON b.usfm = v.book_usfm
                WHERE v.translation_id = ?
                GROUP BY v.book_usfm
                ORDER BY b.order_num
                """,
                (tid,),
            )
            self.version_books[fname] = [r["usfm"] for r in rows]
            self.book_chapters[fname] = {r["usfm"]: r["max_ch"] for r in rows}

        # book_groups (nøkkel → bok-koder) + visningsnavn
        self.book_groups_meta = {}  # key → {name_no, name_en, books}
        for grow in self._query("SELECT id, key, name_no, name_en FROM book_groups"):
            members = self._query(
                "SELECT book_usfm FROM book_group_members WHERE group_id=?",
                (grow["id"],),
            )
            books = [r["book_usfm"] for r in members]
            key = grow["key"].lower()
            self.book_groups[key] = books
            self.book_groups_meta[key] = {
                "key": key,
                "name_no": grow["name_no"],
                "name_en": grow["name_en"],
                "books": books,
            }

        print(
            f"Loaded {len(self.translations)} Bible version(s) from bible.db: "
            f"{', '.join(self.translations.keys())}"
        )

    # ── oppslag av oversettelses-id, med tilbakefall til DB-navn ──
    def _resolve_tid(self, version):
        meta = self.translations.get(version)
        if meta:
            return meta["id"], None
        # Tilbakefall: prøv DB-navnet direkte (i tilfelle frontend sender 'NB88/07' osv.)
        for fname, m in self.translations.items():
            if m["db_name"] == version:
                return m["id"], None
        return None, f"Version '{version}' not found"

    # ── intern: hent rader for et span og bygg meta (footnotes + headings) ──
    def _fetch_span(self, tid, book, ch_start, vs_start, ch_end, vs_end):
        """Returner rader (chapter, verse, text) for et span, sortert."""
        # Bygg WHERE-klausul som dekker både ett-kapittel- og kryss-kapittel-span
        if ch_start == ch_end:
            return self._query(
                """
                SELECT chapter, verse, text FROM verses
                WHERE translation_id=? AND book_usfm=? AND chapter=?
                  AND verse BETWEEN ? AND ?
                ORDER BY verse
                """,
                (tid, book, ch_start, vs_start, vs_end),
            )
        # Kryss-kapittel: første kapittel fra vs_start, siste til vs_end, mellomliggende komplette
        rows = self._query(
            """
            SELECT chapter, verse, text FROM verses
            WHERE translation_id=? AND book_usfm=?
              AND (
                (chapter = ? AND verse >= ?)
                OR (chapter > ? AND chapter < ?)
                OR (chapter = ? AND verse <= ?)
              )
            ORDER BY chapter, verse
            """,
            (tid, book, ch_start, vs_start, ch_start, ch_end, ch_end, vs_end),
        )
        return rows

    def _fetch_headings(self, tid, book, ch_start, ch_end):
        rows = self._query(
            """
            SELECT chapter, verse, text FROM headings
            WHERE translation_id=? AND book_usfm=? AND chapter BETWEEN ? AND ?
            """,
            (tid, book, ch_start, ch_end),
        )
        return {(r["chapter"], r["verse"]): r["text"] for r in rows}

    def _fetch_footnotes(self, tid, book, ch_start, ch_end):
        """Returner {(ch, vs): [{marker, text}, ...]} med syntetiske markører."""
        rows = self._query(
            """
            SELECT chapter, verse, text FROM footnotes
            WHERE translation_id=? AND book_usfm=? AND chapter BETWEEN ? AND ?
            ORDER BY id
            """,
            (tid, book, ch_start, ch_end),
        )
        out = {}
        for r in rows:
            key = (r["chapter"], r["verse"])
            out.setdefault(key, []).append({"marker": "#", "text": r["text"]})
        return out

    def _fetch_xrefs(self, book, ch_start, ch_end):
        """Returner {(ch, vs): [{r, v}, ...]} sortert på votes desc.
        Versjonsuavhengig — samme xrefs for alle oversettelser."""
        rows = self._query(
            """
            SELECT from_chapter, from_verse,
                   to_book, to_chapter, to_verse_start, to_verse_end, to_chapter_end, votes
            FROM cross_references
            WHERE from_book=? AND from_chapter BETWEEN ? AND ?
            ORDER BY from_chapter, from_verse, votes DESC
            """,
            (book, ch_start, ch_end),
        )
        out = {}
        for r in rows:
            key = (r["from_chapter"], r["from_verse"])
            ref = _format_xref_ref(
                r["to_book"], r["to_chapter"], r["to_verse_start"],
                r["to_verse_end"], r["to_chapter_end"],
            )
            out.setdefault(key, []).append({"r": ref, "v": r["votes"]})
        return out

    def _build_verse_results(self, tid, book, rows, ch_start, ch_end, want_meta=True):
        """Bygg liste av (vs, text, chapter, meta) fra rader + meta-tabeller."""
        if not rows:
            return []
        headings = self._fetch_headings(tid, book, ch_start, ch_end) if want_meta else {}
        footnotes = self._fetch_footnotes(tid, book, ch_start, ch_end) if want_meta else {}
        xrefs = self._fetch_xrefs(book, ch_start, ch_end) if want_meta else {}
        results = []
        for r in rows:
            key = (r["chapter"], r["verse"])
            meta = {
                "footnotes": footnotes.get(key, []),
                "xrefs": xrefs.get(key, []),
                "section": headings.get(key),
            }
            results.append((r["verse"], r["text"], r["chapter"], meta))
        return results

    # ── offentlig API: samme signatur som før ──
    def get_verses(self, version, book_code, chapter, verse_start=None, verse_end=None):
        tid, err = self._resolve_tid(version)
        if err:
            return None, err
        if book_code not in self.book_chapters.get(version, {}):
            return None, f"Book '{book_code}' not found in {version}"

        if verse_start is None:
            rows = self._query(
                """
                SELECT chapter, verse, text FROM verses
                WHERE translation_id=? AND book_usfm=? AND chapter=?
                ORDER BY verse
                """,
                (tid, book_code, chapter),
            )
            if not rows:
                return None, f"Chapter {chapter} not found in {USFM_TO_NAME.get(book_code, book_code)}"
            results = self._build_verse_results(tid, book_code, rows, chapter, chapter)
            # get_verses (whole chapter) returnerer (vs, text, meta) — uten kapittel
            return [(v, t, m) for v, t, _ch, m in results], None

        end = verse_end if verse_end is not None else verse_start
        rows = self._query(
            """
            SELECT chapter, verse, text FROM verses
            WHERE translation_id=? AND book_usfm=? AND chapter=?
              AND verse BETWEEN ? AND ?
            ORDER BY verse
            """,
            (tid, book_code, chapter, verse_start, end),
        )
        if not rows:
            ref = f"{chapter}:{verse_start}" + (f"-{verse_end}" if verse_end and verse_end != verse_start else "")
            return None, f"Verses {ref} not found in {USFM_TO_NAME.get(book_code, book_code)}"
        results = self._build_verse_results(tid, book_code, rows, chapter, chapter)
        return [(v, t, m) for v, t, _ch, m in results], None

    def get_verses_cross_chapter(self, version, book_code, ch_start, vs_start, ch_end, vs_end):
        tid, err = self._resolve_tid(version)
        if err:
            return None, err
        if book_code not in self.book_chapters.get(version, {}):
            return None, f"Book '{book_code}' not found in {version}"

        rows = self._fetch_span(tid, book_code, ch_start, vs_start, ch_end, vs_end)
        if not rows:
            return None, f"Verses {ch_start}:{vs_start}-{ch_end}:{vs_end} not found"
        results = self._build_verse_results(tid, book_code, rows, ch_start, ch_end)
        # get_verses_cross_chapter returnerer (vs, text, ch, meta)
        return [(v, t, ch, m) for v, t, ch, m in results], None

    def get_chapter_range(self, version, book_code, ch_start, ch_end):
        tid, err = self._resolve_tid(version)
        if err:
            return None, err
        if book_code not in self.book_chapters.get(version, {}):
            return None, f"Book '{book_code}' not found in {version}"

        rows = self._query(
            """
            SELECT chapter, verse, text FROM verses
            WHERE translation_id=? AND book_usfm=? AND chapter BETWEEN ? AND ?
            ORDER BY chapter, verse
            """,
            (tid, book_code, ch_start, ch_end),
        )
        if not rows:
            return None, f"Chapters {ch_start}-{ch_end} not found in {USFM_TO_NAME.get(book_code, book_code)}"
        results = self._build_verse_results(tid, book_code, rows, ch_start, ch_end)
        return [(v, t, ch, m) for v, t, ch, m in results], None

    # ── kompatibilitetsegenskap brukt enkelte steder i koden ──
    @property
    def versions(self):
        """Liste over versjonsnavn (frontend-navn). Kompat: gammel kode bruker `bible_data.versions`."""
        return self.translations


# ──────────────────────────────────────────────
# Search query parser
# ──────────────────────────────────────────────

def identify_book(text):
    """Try to identify a book name at the start of text. Returns (usfm_code, remaining_text) or (None, text)."""
    text_lower = text.lower().strip()
    for alias in SORTED_ALIASES:
        if text_lower.startswith(alias):
            rest = text_lower[len(alias):]
            # Make sure the alias is not a partial match of a longer word
            # e.g. "job" should not match "joel"
            if rest and rest[0].isalpha():
                continue
            return ALIAS_MAP[alias], text[len(alias):].strip()
    return None, text


_DASH_CHARS = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"  # ulike typer streker brukeren kan skrive


def normalize_dashes(s):
    """Erstatter alle dashe-varianter med standard ASCII-hyphen og fullbredde-kolon/semikolon."""
    if not s:
        return s
    for ch in _DASH_CHARS:
        s = s.replace(ch, "-")
    return s.replace("\uff1a", ":").replace("\uff1b", ";")


def parse_reference(ref_str):
    """
    Parse a reference string like "3:16", "3:16-18", "3:16-4:2", "3", "3-5".
    Returns a dict with parsing results.
    """
    ref_str = normalize_dashes(ref_str).strip()
    if not ref_str:
        return None

    # Pattern: chapter:verse-chapter:verse (cross-chapter range)
    m = re.match(r'^(\d+):(\d+)\s*-\s*(\d+):(\d+)$', ref_str)
    if m:
        return {
            "type": "cross_chapter",
            "ch_start": int(m.group(1)),
            "vs_start": int(m.group(2)),
            "ch_end": int(m.group(3)),
            "vs_end": int(m.group(4)),
        }

    # Pattern: chapter:verse-verse (verse range in single chapter)
    m = re.match(r'^(\d+):(\d+)\s*-\s*(\d+)$', ref_str)
    if m:
        return {
            "type": "verse_range",
            "chapter": int(m.group(1)),
            "vs_start": int(m.group(2)),
            "vs_end": int(m.group(3)),
        }

    # Pattern: chapter:verse (single verse)
    m = re.match(r'^(\d+):(\d+)$', ref_str)
    if m:
        return {
            "type": "single_verse",
            "chapter": int(m.group(1)),
            "verse": int(m.group(2)),
        }

    # Pattern: chapter-chapter (chapter range)
    m = re.match(r'^(\d+)\s*-\s*(\d+)$', ref_str)
    if m:
        return {
            "type": "chapter_range",
            "ch_start": int(m.group(1)),
            "ch_end": int(m.group(2)),
        }

    # Pattern: just a number
    m = re.match(r'^(\d+)$', ref_str)
    if m:
        return {
            "type": "number",
            "value": int(m.group(1)),
        }

    return None


def parse_query(query):
    """
    Parse a full search query into a list of blocks.
    Each block = { book, label, ref_info }
    Semicolons separate blocks. Context is inherited across blocks.
    """
    query = normalize_dashes(query)
    parts = [p.strip() for p in query.split(";") if p.strip()]
    blocks = []

    # Context tracking
    ctx_book = None
    ctx_chapter = None
    ctx_had_verse = False  # Did previous context include a specific verse?

    for part in parts:
        book_code, remainder = identify_book(part)

        if book_code:
            ctx_book = book_code
            ctx_chapter = None
            ctx_had_verse = False
        elif ctx_book is None:
            blocks.append({"error": f"Could not identify book in '{part}'"})
            continue

        ref = parse_reference(remainder) if remainder.strip() else None

        book = ctx_book
        book_name = USFM_TO_NAME.get(book, book)

        if ref is None and remainder.strip() == "":
            if book_code:
                # Just a book name with no reference — could be a single-chapter book
                # We'll treat it as chapter 1 (whole chapter)
                blocks.append({
                    "book": book,
                    "label": book_name,
                    "type": "whole_chapter",
                    "chapter": 1,
                    "is_single_chapter_book": True,
                })
                ctx_chapter = 1
                ctx_had_verse = False
            else:
                blocks.append({"error": f"No reference provided in '{part}'"})
            continue

        if ref is None:
            blocks.append({"error": f"Could not parse reference '{part}'"})
            continue

        if ref["type"] == "cross_chapter":
            label = f"{book_name} {ref['ch_start']}:{ref['vs_start']}-{ref['ch_end']}:{ref['vs_end']}"
            blocks.append({
                "book": book, "label": label, "type": "cross_chapter",
                "ch_start": ref["ch_start"], "vs_start": ref["vs_start"],
                "ch_end": ref["ch_end"], "vs_end": ref["vs_end"],
            })
            ctx_chapter = ref["ch_end"]
            ctx_had_verse = True

        elif ref["type"] == "verse_range":
            label = f"{book_name} {ref['chapter']}:{ref['vs_start']}-{ref['vs_end']}"
            blocks.append({
                "book": book, "label": label, "type": "verse_range",
                "chapter": ref["chapter"], "vs_start": ref["vs_start"], "vs_end": ref["vs_end"],
            })
            ctx_chapter = ref["chapter"]
            ctx_had_verse = True

        elif ref["type"] == "single_verse":
            label = f"{book_name} {ref['chapter']}:{ref['verse']}"
            blocks.append({
                "book": book, "label": label, "type": "single_verse",
                "chapter": ref["chapter"], "verse": ref["verse"],
            })
            ctx_chapter = ref["chapter"]
            ctx_had_verse = True

        elif ref["type"] == "chapter_range":
            label = f"{book_name} {ref['ch_start']}-{ref['ch_end']}"
            blocks.append({
                "book": book, "label": label, "type": "chapter_range",
                "ch_start": ref["ch_start"], "ch_end": ref["ch_end"],
            })
            ctx_chapter = ref["ch_end"]
            ctx_had_verse = False

        elif ref["type"] == "number":
            val = ref["value"]
            if ctx_had_verse and ctx_chapter is not None:
                # Bare number after chapter:verse context → verse in same chapter
                label = f"{book_name} {ctx_chapter}:{val}"
                blocks.append({
                    "book": book, "label": label, "type": "single_verse",
                    "chapter": ctx_chapter, "verse": val,
                })
            else:
                # Bare number → chapter
                label = f"{book_name} {val}"
                blocks.append({
                    "book": book, "label": label, "type": "whole_chapter",
                    "chapter": val,
                })
                ctx_chapter = val
                ctx_had_verse = False

    return blocks


def resolve_block(bible_data, version, block):
    """Resolve a parsed block into actual verse data."""
    if "error" in block:
        return {"label": "Error", "error": block["error"], "verses": []}

    book = block["book"]
    btype = block["type"]
    base = {"label": block["label"], "book": book}

    def _verse_obj(num, chapter, text, meta):
        obj = {"num": num, "chapter": chapter, "text": text}
        if meta.get("footnotes"):
            obj["footnotes"] = meta["footnotes"]
        if meta.get("xrefs"):
            obj["xrefs"] = meta["xrefs"]
        if meta.get("section"):
            obj["section"] = meta["section"]
        return obj

    if btype == "single_verse":
        verses, err = bible_data.get_verses(version, book, block["chapter"], block["verse"])
        if err:
            return {**base, "error": err, "verses": []}
        return {
            **base,
            "verses": [_verse_obj(v, block["chapter"], t, m) for v, t, m in verses],
        }

    elif btype == "verse_range":
        verses, err = bible_data.get_verses(version, book, block["chapter"], block["vs_start"], block["vs_end"])
        if err:
            return {**base, "error": err, "verses": []}
        return {
            **base,
            "verses": [_verse_obj(v, block["chapter"], t, m) for v, t, m in verses],
        }

    elif btype == "whole_chapter":
        verses, err = bible_data.get_verses(version, book, block["chapter"])
        if err:
            return {**base, "error": err, "verses": []}
        return {
            **base,
            "verses": [_verse_obj(v, block["chapter"], t, m) for v, t, m in verses],
        }

    elif btype == "chapter_range":
        verses, err = bible_data.get_chapter_range(version, book, block["ch_start"], block["ch_end"])
        if err:
            return {**base, "error": err, "verses": []}
        return {
            **base,
            "verses": [_verse_obj(v, ch, t, m) for v, t, ch, m in verses],
        }

    elif btype == "cross_chapter":
        verses, err = bible_data.get_verses_cross_chapter(
            version, book, block["ch_start"], block["vs_start"], block["ch_end"], block["vs_end"]
        )
        if err:
            return {**base, "error": err, "verses": []}
        return {
            **base,
            "verses": [_verse_obj(v, ch, t, m) for v, t, ch, m in verses],
        }

    return {"label": block.get("label", "?"), "error": "Unknown block type", "verses": []}


def extract_book_prefix(query):
    """Hvis query starter med 'Bokenavn: resten' eller 'Gruppenavn: resten',
    returner (book_codes_list, rest). Returnerer (None, query) ellers.

    Bok → liste med ett USFM-kode.
    Gruppe → liste med alle medlemmer (f.eks. 'paulusbrevene' → 13 brev).
    """
    m = re.match(r'^([^:"]+?):\s*(.*)$', query)
    if not m:
        return None, query
    prefix = m.group(1).strip().lower()
    rest = m.group(2).strip()
    if prefix in ALIAS_MAP:
        return [ALIAS_MAP[prefix]], rest
    # Bok-grupper (paulusbrevene, evangeliene, mosebøkene, gt, nt, ...) — fra bible.db.
    if bible_data is not None and prefix in bible_data.book_groups:
        return list(bible_data.book_groups[prefix]), rest
    return None, query


def is_reference_query(query):
    """Check if the query looks like a Bible reference (vs free text search)."""
    query = normalize_dashes(query)
    # Bok-prefiks → alltid tekstsøk (filtrert)
    pb, _ = extract_book_prefix(query)
    if pb:
        return False
    # Operators → always text search
    if '"' in query:
        return False
    if any(t.startswith('-') and len(t) > 1 for t in query.split()):
        return False
    # Try to parse first semicolon-separated part
    first_part = query.split(";")[0].strip()
    book_code, remainder = identify_book(first_part)
    if book_code:
        return True
    return False


def _split_on_plus_outside_quotes(query):
    """Del en query på '+' som OR-separator, men kun når + er UTENFOR anførselstegn."""
    parts = []
    buf = []
    in_quote = False
    for ch in query:
        if ch == '"':
            in_quote = not in_quote
            buf.append(ch)
        elif ch == '+' and not in_quote:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p]


def _parse_single_group(group):
    """Parse én gruppe (AND-logikk) til (phrases, words, excluded)."""
    required_phrases = []
    phrase_pat = re.compile(r'"([^"]+)"')
    for m in phrase_pat.finditer(group):
        required_phrases.append(m.group(1).lower())
    remainder = phrase_pat.sub(' ', group)

    required_words = []
    excluded_words = []
    for tok in remainder.split():
        if tok.startswith('-') and len(tok) > 1:
            excluded_words.append(tok[1:].lower())
        elif tok:
            required_words.append(tok.lower())
    return required_phrases, required_words, excluded_words


def parse_search_query(query):
    """Parse query til liste av OR-grupper (hver gruppe = AND-logikk).
    Operatorer:
    - "quoted phrases" → eksakt substring match
    - word → AND-match enkeltord
    - -word → må IKKE inneholde
    - + → OR mellom grupper (f.eks. "frykt ikke" + "vær ikke redd")

    Returnerer: list of (phrases, words, excluded) — vers matcher hvis ANY gruppe matcher.
    """
    groups = _split_on_plus_outside_quotes(query)
    if not groups:
        return []
    return [_parse_single_group(g) for g in groups]


def has_search_operators(query):
    """Returns True if query uses ", -word, or + operators."""
    if '+' in query and _split_on_plus_outside_quotes(query) and len(_split_on_plus_outside_quotes(query)) > 1:
        return True
    for group in parse_search_query(query):
        phrases, _, excl = group
        if phrases or excl:
            return True
    return False


def _fts_escape_phrase(term):
    """Escape \" inside an FTS5 phrase literal so 'foo"bar' blir trygt sitert."""
    return term.replace('"', '""')


def _build_search_sql(group, tid, book_filter):
    """Bygg (sql, params) for én OR-gruppe.
    Quoted phrases bruker FTS5 (ordgrense). Bare ord og eksklusjon bruker LIKE (substring).
    book_filter kan være None, en USFM-streng, eller en liste av USFM-koder (gruppe)."""
    phrases, words, excluded = group
    where = ["v.translation_id = ?"]
    params = [tid]

    join = ""
    if phrases:
        join = "JOIN verses_fts fts ON fts.rowid = v.id"
        # FTS5 MATCH: AND mellom flere fraser kan uttrykkes som mellomrom-separert kjede
        match = " ".join(f'"{_fts_escape_phrase(p)}"' for p in phrases)
        where.append("verses_fts MATCH ?")
        params.append(match)

    for w in words:
        where.append("LOWER(v.text) LIKE ? ESCAPE '\\'")
        params.append(f"%{_like_escape(w)}%")
    for w in excluded:
        where.append("LOWER(v.text) NOT LIKE ? ESCAPE '\\'")
        params.append(f"%{_like_escape(w)}%")

    if book_filter:
        if isinstance(book_filter, str):
            where.append("v.book_usfm = ?")
            params.append(book_filter)
        else:
            placeholders = ",".join("?" for _ in book_filter)
            where.append(f"v.book_usfm IN ({placeholders})")
            params.extend(book_filter)

    sql = f"""
        SELECT v.book_usfm, v.chapter, v.verse, v.text
        FROM verses v {join}
        WHERE {' AND '.join(where)}
    """
    return sql, params


def _like_escape(s):
    """Escape % og _ i LIKE-mønster."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_text(bible_data, version, query, per_book=10, book_filter=None):
    """Full-text search via SQLite (FTS5 for fraser, LIKE for ord).
    Returns (results, book_totals)."""
    groups = parse_search_query(query)
    groups = [g for g in groups if g[0] or g[1] or g[2]]
    if not groups:
        return [], {}

    tid, err = bible_data._resolve_tid(version)
    if err:
        return [], {}

    # Kjør hver gruppe og union resultater (de-duplicate på (book, ch, vs))
    seen = set()
    rows_by_book = {}
    for grp in groups:
        sql, params = _build_search_sql(grp, tid, book_filter)
        for r in bible_data._query(sql, tuple(params)):
            key = (r["book_usfm"], r["chapter"], r["verse"])
            if key in seen:
                continue
            seen.add(key)
            rows_by_book.setdefault(r["book_usfm"], []).append(r)

    # Sortér per bok i bibelsk rekkefølge (kapittel/vers-stigende), respektér per_book-grense
    book_order = bible_data.version_books.get(version, [])
    order_idx = {b: i for i, b in enumerate(book_order)}
    sorted_books = sorted(rows_by_book.keys(), key=lambda b: order_idx.get(b, 999))

    effective_per_book = 999999 if book_filter else per_book
    results = []
    book_totals = {}
    for book_code in sorted_books:
        rows = sorted(rows_by_book[book_code], key=lambda r: (r["chapter"], r["verse"]))
        book_name = USFM_TO_NAME.get(book_code, book_code)
        book_totals[book_code] = len(rows)
        for r in rows[:effective_per_book]:
            results.append({
                "ref": f"{book_name} {r['chapter']}:{r['verse']}",
                "book": book_code,
                "chapter": r["chapter"],
                "verse": r["verse"],
                "text": r["text"],
            })
    return results, book_totals


# ──────────────────────────────────────────────
# HTTP Server
# ──────────────────────────────────────────────

bible_data = None
last_heartbeat = time.time()

# ──────────────────────────────────────────────
# Rate limiting for KI-endepunkter (beskytt API-nøkkel mot misbruk)
# ──────────────────────────────────────────────
import threading
from collections import deque

_ai_rate_lock = threading.Lock()
_ai_calls_per_ip = {}        # ip -> deque[(timestamp, endpoint)]
_ai_global_day = deque()     # timestamps for alle KI-kall i løpet av 24t

# Konfigurasjon (kan overstyres via miljøvariabler)
AI_RATE_WINDOW_SEC = int(os.environ.get("AI_RATE_WINDOW_SEC", "600"))      # 10 min
AI_RATE_PER_WINDOW = int(os.environ.get("AI_RATE_PER_WINDOW", "20"))       # max 20 kall per 10 min
AI_DAILY_PER_IP    = int(os.environ.get("AI_DAILY_PER_IP",    "200"))      # max 200 kall per IP per dag
AI_DAILY_GLOBAL    = int(os.environ.get("AI_DAILY_GLOBAL",    "2000"))     # max 2000 totalt per dag


def _get_client_ip(handler):
    """Finn ekte klient-IP: Cloudflare > X-Forwarded-For > remote_addr."""
    cf = handler.headers.get("CF-Connecting-IP")
    if cf:
        return cf.strip()
    xff = handler.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return handler.client_address[0]


def check_ai_rate_limit(ip, endpoint):
    """Returnerer (allowed: bool, reason_if_blocked: str|None)."""
    with _ai_rate_lock:
        now = time.time()
        day_start = now - 86400
        window_start = now - AI_RATE_WINDOW_SEC

        # Rydd globalt
        while _ai_global_day and _ai_global_day[0] < day_start:
            _ai_global_day.popleft()

        # Rydd per-IP kø
        q = _ai_calls_per_ip.setdefault(ip, deque())
        while q and q[0][0] < day_start:
            q.popleft()

        # Hvis køen er tom etter rydding, fjern entry for å spare minne
        if not q and ip in _ai_calls_per_ip:
            # (la stå for nå — vi rydder ved periodisk vedlikehold)
            pass

        # Vindu-begrensning
        in_window = sum(1 for t, _ in q if t >= window_start)
        if in_window >= AI_RATE_PER_WINDOW:
            return False, "For mange KI-spørringer i kort tid. Prøv igjen om noen minutter."

        # Dags-begrensning per IP
        if len(q) >= AI_DAILY_PER_IP:
            return False, "Dagens KI-kvote er brukt opp. Prøv igjen i morgen."

        # Global dags-begrensning
        if len(_ai_global_day) >= AI_DAILY_GLOBAL:
            return False, "KI-tjenesten er midlertidig utilgjengelig pga. høy trafikk. Prøv igjen senere."

        # Alt OK — registrer
        q.append((now, endpoint))
        _ai_global_day.append(now)
        return True, None


class BibleHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Log to stderr so Coolify picks it up
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")
        sys.stderr.flush()

    def log_error(self, format, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] ERROR: {format % args}\n")
        sys.stderr.flush()

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            self._do_GET_inner()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            sys.stderr.write(f"[{self.log_date_time_string()}] do_GET UNHÅNDTERT FEIL: {e}\n{tb}\n")
            sys.stderr.flush()
            try:
                if self.path.startswith("/api/"):
                    self._send_json({"error": f"Intern serverfeil: {type(e).__name__}: {e}"}, 500)
                else:
                    self._send_html(f"<h1>Serverfeil</h1><pre>{type(e).__name__}: {e}</pre>")
            except Exception:
                pass

    def _do_GET_inner(self):
        global last_heartbeat
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            html_path = BASE_DIR / "index.html"
            if html_path.exists():
                self._send_html(html_path.read_text(encoding="utf-8"))
            else:
                self._send_html("<h1>index.html not found</h1>")

        elif path == "/api/versions":
            versions = list(bible_data.versions.keys())
            if versions:
                versions = ["Alle"] + versions  # Virtuell "Alle"-versjon øverst
            self._send_json({"versions": versions})

        elif path == "/api/books":
            version = params.get("version", [""])[0]
            if version == "Alle":
                # Bøker for Alle = union av alle versjoner (i praksis samme 66)
                version = list(bible_data.versions.keys())[0] if bible_data.versions else ""
            if not version or version not in bible_data.versions:
                version = list(bible_data.versions.keys())[0] if bible_data.versions else ""
            books_list = []
            for code in bible_data.version_books.get(version, []):
                books_list.append({
                    "code": code,
                    "name": USFM_TO_NAME.get(code, code),
                    "name_en": USFM_TO_ENG.get(code, code),
                    "chapters": bible_data.book_chapters.get(version, {}).get(code, 0),
                })
            self._send_json({"books": books_list, "version": version})

        elif path == "/api/search":
            query = params.get("q", [""])[0]
            version = params.get("version", [""])[0]
            if not query:
                self._send_json({"error": "No search query provided"}, 400)
                return
            if version == "Alle":
                # Virtuell versjon: søk på tvers av alle versjoner
                if is_reference_query(query):
                    # For referanser: returner samme form som /api/all_versions
                    all_results = {}
                    for vname in bible_data.versions:
                        blocks = parse_query(query)
                        resolved = [resolve_block(bible_data, vname, b) for b in blocks]
                        all_results[vname] = resolved
                    self._send_json({"type": "all_versions", "results": all_results, "query": query, "version": "Alle"})
                    return
                # Tekstsøk: slå sammen alle versjoner, dedupliser på USFM-nøkkel
                book_filter = params.get("book", [""])[0] or None
                search_query = query
                prefix_book, rest = extract_book_prefix(query)
                if prefix_book and not book_filter:
                    book_filter = prefix_book
                    search_query = rest
                if not search_query.strip():
                    self._send_json({
                        "type": "text_search", "results": [], "book_totals": {},
                        "total": 0, "query": query, "version": "Alle",
                        "book_filter": book_filter, "has_operators": False,
                    })
                    return
                # Hent ALLE treff (ingen per-bok-cap) per versjon så dedup blir riktig.
                # Uten dette: BGO 871 treff → Alle rapporterer 293 fordi hver versjon er
                # kappet til 10 per bok FØR dedup.
                merged = {}
                book_totals = {}
                for vname in bible_data.versions:
                    results, _bt = search_text(bible_data, vname, search_query, per_book=10**9, book_filter=book_filter)
                    for r in results:
                        key = f"{r['book']}.{r['chapter']}.{r['verse']}"
                        if key not in merged:
                            merged[key] = {**r, "matched_versions": [vname]}
                            book_totals[r['book']] = book_totals.get(r['book'], 0) + 1
                        else:
                            merged[key]["matched_versions"].append(vname)

                # Sortér i bibelsk rekkefølge (bruk første versjons bok-orden) og bruk
                # per-bok-cap (10) i stedet for et hardt totalcap, så svaret reflekterer
                # alle bøker — ikke bare den første sett under iterasjonen.
                first_vname = next(iter(bible_data.versions), None)
                book_order = bible_data.version_books.get(first_vname, []) if first_vname else []
                order_idx = {b: i for i, b in enumerate(book_order)}
                all_results = sorted(
                    merged.values(),
                    key=lambda r: (order_idx.get(r["book"], 999), r["chapter"], r["verse"]),
                )
                per_book_cap = 10
                merged_list = []
                book_seen_count = {}
                for r in all_results:
                    n = book_seen_count.get(r["book"], 0)
                    if n < per_book_cap:
                        merged_list.append(r)
                        book_seen_count[r["book"]] = n + 1
                self._send_json({
                    "type": "text_search", "results": merged_list, "book_totals": book_totals,
                    "total": len(merged), "query": query, "version": "Alle",
                    "book_filter": book_filter, "has_operators": has_search_operators(search_query),
                })
                return
            if not version or version not in bible_data.versions:
                version = list(bible_data.versions.keys())[0] if bible_data.versions else ""
            if not version:
                self._send_json({"error": "No Bible versions available"}, 400)
                return

            if is_reference_query(query):
                blocks = parse_query(query)
                results = [resolve_block(bible_data, version, b) for b in blocks]
                self._send_json({"type": "reference", "results": results, "version": version})
            else:
                book_filter = params.get("book", [""])[0] or None
                search_query = query
                # "Bokenavn:"-prefiks overstyrer/aktiverer book-filter
                prefix_book, rest = extract_book_prefix(query)
                if prefix_book and not book_filter:
                    book_filter = prefix_book
                    search_query = rest
                if not search_query.strip():
                    # Kun bok-prefiks uten søkeord → vis bok tomt
                    self._send_json({
                        "type": "text_search", "results": [], "book_totals": {},
                        "total": 0, "query": query, "version": version,
                        "book_filter": book_filter, "has_operators": False,
                    })
                else:
                    results, book_totals = search_text(bible_data, version, search_query, book_filter=book_filter)
                    total = sum(book_totals.values())
                    self._send_json({
                        "type": "text_search", "results": results, "book_totals": book_totals,
                        "total": total, "query": query, "version": version,
                        "book_filter": book_filter, "has_operators": has_search_operators(search_query),
                    })

        elif path == "/api/all_versions":
            query = params.get("q", [""])[0]
            if not query:
                self._send_json({"error": "No query provided"}, 400)
                return
            all_results = {}
            for vname in bible_data.versions:
                blocks = parse_query(query)
                resolved = [resolve_block(bible_data, vname, b) for b in blocks]
                all_results[vname] = resolved
            self._send_json({"results": all_results, "query": query})

        elif path == "/api/book_groups":
            # Eksponer book_groups (Mosebøkene, Evangeliene, Paulusbrevene osv.) til frontend.
            groups = list(bible_data.book_groups_meta.values())
            self._send_json({"groups": groups})

        elif path == "/api/heartbeat":
            last_heartbeat = time.time()
            self._send_json({"ok": True})

        elif path == "/api/list_models":
            if not GENAI_AVAILABLE:
                self._send_json({"error": "google-genai ikke tilgjengelig"}, 500)
                return
            try:
                models = []
                for m in _genai_client.models.list():
                    name = getattr(m, "name", str(m))
                    supported = getattr(m, "supported_actions", None) or getattr(m, "supported_generation_methods", None)
                    models.append({"name": name, "supported": list(supported) if supported else None})
                self._send_json({"models": models, "current": GEMINI_MODEL})
            except Exception as e:
                sys.stderr.write(f"[{self.log_date_time_string()}] list_models FEIL: {e}\n")
                sys.stderr.flush()
                self._send_json({"error": str(e)}, 500)

        elif path == "/api/ai_parse":
            # Rate-limit før vi treffer KI-API
            ip = _get_client_ip(self)
            allowed, reason = check_ai_rate_limit(ip, path)
            if not allowed:
                sys.stderr.write(f"[{self.log_date_time_string()}] RATE-LIMIT {path} fra {ip}: {reason}\n")
                sys.stderr.flush()
                self._send_json({"error": reason}, 429)
                return
            query = params.get("q", [""])[0]
            if not query:
                self._send_json({"error": "No query"}, 400)
                return
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                sys.stderr.write(f"[{self.log_date_time_string()}] ai_parse: GEMINI_API_KEY mangler\n")
                sys.stderr.flush()
                self._send_json({"error": "GEMINI_API_KEY ikke konfigurert"}, 500)
                return
            sys.stderr.write(f"[{self.log_date_time_string()}] ai_parse: spør Gemini om '{query[:80]}'\n")
            sys.stderr.flush()
            system_prompt = """Du hjelper en bibelsøkemotor med å forstå brukerens søk. Søkemotoren har to moduser:

1. REFERANSE-oppslag: f.eks. 'Joh 3:16', '1 Mos 1:1-3', 'Sal 23', 'Matt 5:1-10'. Bruk norske bokforkortelser: 1 Mos, 2 Mos, 3 Mos, 4 Mos, 5 Mos, Jos, Dom, Rut, 1 Sam, 2 Sam, 1 Kong, 2 Kong, 1 Krøn, 2 Krøn, Esra, Neh, Est, Job, Sal, Ordsp, Fork, Høys, Jes, Jer, Klag, Esek, Dan, Hos, Joel, Amos, Obad, Jona, Mika, Nah, Hab, Sef, Hag, Sak, Mal, Matt, Mark, Luk, Joh, Apg, Rom, 1 Kor, 2 Kor, Gal, Ef, Fil, Kol, 1 Tess, 2 Tess, 1 Tim, 2 Tim, Tit, Filem, Heb, Jak, 1 Pet, 2 Pet, 1 Joh, 2 Joh, 3 Joh, Jud, Åp.

2. TEKSTSØK: hvilke som helst ord som finnes i bibelteksten (case-insensitive AND-match på alle ord).

Brukerens søk gikk ikke gjennom. Din oppgave: returner EN KORRIGERT SØKESTRENG som søkemotoren kan forstå. Ikke forklar noe — KUN den korrigerte strengen.

Regler:
- Hvis input ligner en bibelreferanse (uformell, stavefeil, ordtall) → konverter til standard referanseformat (f.eks. 'johannes tre seksten' → 'Joh 3:16', 'første mosebok femten ti' → '1 Mos 15:10', 'salme tjuetre' → 'Sal 23').
- Hvis input ser ut som et ord/uttrykk brukeren søker på i bibelteksten → rett stavefeil og returner det korrigerte ordet (f.eks. 'jesos' → 'Jesus', 'nåda' → 'nåde', 'frels' → 'frelse').
- Bruk flere ord med mellomrom for AND-søk (f.eks. 'jesus betlehem').
- ALDRI returner forklaringer, spørsmål eller setninger. KUN den ferdige søkestrengen.
- Hvis du er usikker, gjør din beste gjetning og returner den direkte."""
            try:
                result = gemini_request(api_key, query, system_prompt, max_tokens=50)
                # Filter out AI responses that contain explanatory language
                bad_words = ["forstår", "vennligst", "hvilken", "mener du", "oppgi", "?", "beklager", "spesifiser"]
                if len(result) > 60 or any(w in result.lower() for w in bad_words):
                    sys.stderr.write(f"[{self.log_date_time_string()}] ai_parse: forkastet forklarings-svar '{result}'\n")
                    sys.stderr.flush()
                    self._send_json({"error": "KI kunne ikke tolke søket"}, 200)
                    return
                sys.stderr.write(f"[{self.log_date_time_string()}] ai_parse: svar '{result}'\n")
                sys.stderr.flush()
                self._send_json({"result": result})
            except Exception as e:
                sys.stderr.write(f"[{self.log_date_time_string()}] ai_parse FEIL: {e}\n")
                sys.stderr.flush()
                self._send_json({"error": str(e)}, 500)

        elif path in ("/logo_biblegateway.png", "/favicon.ico"):
            img_path = BASE_DIR / "logo_biblegateway.png"
            if img_path.exists():
                body = img_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

        else:
            sys.stderr.write(f"[{self.log_date_time_string()}] 404 ukjent GET-sti: {path!r}\n")
            sys.stderr.flush()
            self.send_error(404)

    def do_POST(self):
        try:
            self._do_POST_inner()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            sys.stderr.write(f"[{self.log_date_time_string()}] do_POST UNHÅNDTERT FEIL: {e}\n{tb}\n")
            sys.stderr.flush()
            try:
                self._send_json({"error": f"Intern serverfeil: {type(e).__name__}: {e}"}, 500)
            except Exception:
                pass

    def _do_POST_inner(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length)) if length else {}
        except Exception:
            self._send_json({"error": "Ugyldig JSON"}, 400)
            return

        # Rate-limit for alle KI-endepunkter (POST)
        if path.startswith("/api/ai_"):
            ip = _get_client_ip(self)
            allowed, reason = check_ai_rate_limit(ip, path)
            if not allowed:
                sys.stderr.write(f"[{self.log_date_time_string()}] RATE-LIMIT {path} fra {ip}: {reason}\n")
                sys.stderr.flush()
                self._send_json({"error": reason}, 429)
                return

        if path == "/api/ai_most_different":
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                self._send_json({"error": "GEMINI_API_KEY ikke konfigurert"}, 500)
                return
            label = body.get("label", "")
            current = body.get("current_version", "")
            if not label or not current:
                self._send_json({"error": "Mangler label eller versjon"}, 400)
                return
            # Hent teksten for referansen i alle versjoner
            all_texts = {}
            for vname in bible_data.versions:
                try:
                    blocks = parse_query(label)
                    resolved = [resolve_block(bible_data, vname, b) for b in blocks]
                    parts = []
                    for r in resolved:
                        if r.get("error"):
                            continue
                        for v in r.get("verses", []):
                            parts.append(v["text"])
                    if parts:
                        all_texts[vname] = " ".join(parts)
                except Exception:
                    pass
            if current not in all_texts or len(all_texts) < 2:
                self._send_json({"error": "Ikke nok versjoner å sammenligne"}, 400)
                return

            current_text = all_texts[current]
            other_versions = [k for k in all_texts if k != current]
            others_list = [f"{k}: {all_texts[k]}" for k in other_versions]
            user_prompt = (
                f"REFERANSE: {label}\n\n"
                f"VALGT VERSJON ({current}): {current_text}\n\n"
                f"ANDRE VERSJONER:\n" + "\n".join(others_list)
            )
            system_prompt = (
                "Du er en bibelforsker. Sammenlign den valgte versjonen med alle andre, "
                "og identifiser hvilken versjon som er MEST ULIK fra den valgte.\n\n"
                "Returner KUN gyldig JSON på dette formatet:\n"
                '{"version": "VERSJONSNAVN", "explanation": "kort forklaring 1-2 setninger", '
                '"current_highlights": ["frase i valgt versjon", ...], '
                '"other_highlights": ["frase i den ulike versjonen", ...]}\n\n'
                f"- version MÅ være EKSAKT en av: {', '.join(other_versions)}\n"
                "- current_highlights: 1-3 korte fraser (1-4 ord) fra den VALGTE versjonen "
                "som er meningsforskjellige. Frasene MÅ stå eksakt slik i teksten.\n"
                "- other_highlights: tilsvarende 1-3 korte fraser fra den ulike versjonen.\n"
                "- Hopp over synonymer og stilforskjeller — kun meningsforskjell.\n\n"
                "Ingen innledning, ingen etterord. Bare JSON."
            )
            sys.stderr.write(f"[{self.log_date_time_string()}] ai_most_different: {label} (current={current})\n")
            sys.stderr.flush()
            try:
                raw = gemini_request(api_key, user_prompt, system_prompt, max_tokens=500)
                cleaned = raw.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                    if cleaned.endswith("```"):
                        cleaned = cleaned.rsplit("\n", 1)[0]
                    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
                try:
                    parsed = json.loads(cleaned)
                    version = parsed.get("version", "").strip()
                    # Valider at version er i listen
                    if version not in other_versions:
                        # Forsøk å matche via case-insensitive
                        version_lc = version.lower()
                        match = next((v for v in other_versions if v.lower() == version_lc), None)
                        if match:
                            version = match
                        else:
                            sys.stderr.write(f"[{self.log_date_time_string()}] ai_most_different: ukjent versjon '{version}' — rå: {raw[:200]}\n")
                            sys.stderr.flush()
                    self._send_json({
                        "version": version,
                        "explanation": parsed.get("explanation", ""),
                        "current_highlights": parsed.get("current_highlights", []),
                        "other_highlights": parsed.get("other_highlights", []),
                        # Behold 'result' for bakoverkompatibilitet
                        "result": parsed.get("explanation", ""),
                    })
                except Exception as parse_err:
                    sys.stderr.write(f"[{self.log_date_time_string()}] ai_most_different parse-feil: {parse_err} — rå: {raw[:200]}\n")
                    sys.stderr.flush()
                    self._send_json({"error": "KI returnerte ugyldig format", "raw": raw}, 500)
            except Exception as e:
                sys.stderr.write(f"[{self.log_date_time_string()}] ai_most_different FEIL: {e}\n")
                sys.stderr.flush()
                self._send_json({"error": str(e)}, 500)

        elif path == "/api/ai_diff":
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                sys.stderr.write(f"[{self.log_date_time_string()}] ai_diff: GEMINI_API_KEY mangler\n")
                sys.stderr.flush()
                self._send_json({"error": "GEMINI_API_KEY ikke konfigurert"}, 500)
                return
            text1 = body.get("text1", "")
            text2 = body.get("text2", "")
            v1 = body.get("version1", "Versjon 1")
            v2 = body.get("version2", "Versjon 2")
            label = body.get("label", "")
            if not text1 or not text2:
                self._send_json({"error": "Mangler tekst"}, 400)
                return
            sys.stderr.write(f"[{self.log_date_time_string()}] ai_diff: sammenligner '{label}' ({v1} vs {v2})\n")
            sys.stderr.flush()
            try:
                result = gemini_request(
                    api_key,
                    f"Sammenlign disse to oversettelsene av {label}:\n\n{v1}: {text1}\n\n{v2}: {text2}",
                    "Du er en bibelforsker. Oppsummer KORT de viktigste forskjellene i ordvalg og formulering mellom de to oversettelsene. Svar på norsk. Maks 3 setninger. Vær konkret om hvilke ord som er forskjellige.",
                    max_tokens=300,
                )
                self._send_json({"result": result})
            except Exception as e:
                sys.stderr.write(f"[{self.log_date_time_string()}] ai_diff FEIL: {e}\n")
                sys.stderr.flush()
                self._send_json({"error": str(e)}, 500)
        elif path == "/api/ai_gen_refs":
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                self._send_json({"error": "GEMINI_API_KEY ikke konfigurert"}, 500)
                return
            label = body.get("label", "")
            text = body.get("text", "")
            if not text:
                self._send_json({"error": "Mangler tekst"}, 400)
                return
            sys.stderr.write(f"[{self.log_date_time_string()}] ai_gen_refs: {label}\n")
            sys.stderr.flush()
            try:
                result = gemini_request(
                    api_key,
                    f"Vers: {label}\nTekst: {text}",
                    "Du er en bibelforsker. Gitt dette verset, generer 6-10 KORTE søkestrenger "
                    "(1-3 ord per søk) som vil finne andre vers i Bibelen med lignende tema, idé, "
                    "eller som refererer til samme sannhet. Fokus på:\n"
                    "- Nøkkelbegreper og kjernekonsepter\n"
                    "- Navn, personer, steder som nevnes\n"
                    "- Teologiske uttrykk og idiomer\n"
                    "- Bøyninger som faktisk finnes i norske bibeloversettelser (ta hensyn til verset er på norsk)\n\n"
                    "Unngå vanlige ord som finnes overalt (som 'Gud', 'Herren', 'og', 'i'). Sikt på "
                    "presise fraser som gir få, men relevante treff.\n\n"
                    "Returner KUN JSON-array med søkestrengene:\n"
                    '["søkestreng 1", "søkestreng 2", ...]\n\n'
                    "Ingen innledning, ingen etterord. Maks 10 søkestrenger.",
                    max_tokens=300,
                )
                cleaned = result.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                    if cleaned.endswith("```"):
                        cleaned = cleaned.rsplit("\n", 1)[0]
                    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
                try:
                    queries = json.loads(cleaned)
                    if not isinstance(queries, list):
                        raise ValueError("Forventet liste")
                    queries = [q.strip() for q in queries if isinstance(q, str) and q.strip()][:10]
                    self._send_json({"queries": queries})
                except Exception as parse_err:
                    sys.stderr.write(f"[{self.log_date_time_string()}] ai_gen_refs parse-feil: {parse_err} — rå: {result[:200]}\n")
                    sys.stderr.flush()
                    self._send_json({"error": "KI returnerte ugyldig format"}, 500)
            except Exception as e:
                sys.stderr.write(f"[{self.log_date_time_string()}] ai_gen_refs FEIL: {e}\n")
                sys.stderr.flush()
                self._send_json({"error": str(e)}, 500)

        elif path == "/api/ai_highlight_diff":
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                self._send_json({"error": "GEMINI_API_KEY ikke konfigurert"}, 500)
                return
            text1 = body.get("text1", "")
            text2 = body.get("text2", "")
            v1 = body.get("version1", "Versjon 1")
            v2 = body.get("version2", "Versjon 2")
            label = body.get("label", "")
            if not text1 or not text2:
                self._send_json({"error": "Mangler tekst"}, 400)
                return
            sys.stderr.write(f"[{self.log_date_time_string()}] ai_highlight_diff: {label} ({v1} vs {v2})\n")
            sys.stderr.flush()
            try:
                result = gemini_request(
                    api_key,
                    f"Vers: {label}\n\n{v1}:\n{text1}\n\n{v2}:\n{text2}",
                    "Du er en bibelforsker. Finn fraser (1-4 ord) som er MENINGSFORSKJELLIG mellom "
                    "de to oversettelsene — ikke synonymer eller små stilforskjeller, men ord/fraser "
                    "med betydningsmessig forskjell som er nyttig å se.\n\n"
                    "Frasene MÅ stå EKSAKT slik de er i teksten (samme bokstaver, samme bøyning). "
                    "Maks 3 fraser per versjon. Hvis det ikke finnes meningsfulle forskjeller, "
                    "returner tomme lister.\n\n"
                    "Returner KUN gyldig JSON:\n"
                    '{"v1_highlights": ["frase", ...], "v2_highlights": ["frase", ...]}\n\n'
                    "Ingen innledning, ingen etterord.",
                    max_tokens=250,
                )
                cleaned = result.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                    if cleaned.endswith("```"):
                        cleaned = cleaned.rsplit("\n", 1)[0]
                    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
                try:
                    parsed = json.loads(cleaned)
                    self._send_json({
                        "v1": parsed.get("v1_highlights", []),
                        "v2": parsed.get("v2_highlights", []),
                    })
                except Exception as parse_err:
                    sys.stderr.write(f"[{self.log_date_time_string()}] ai_highlight_diff parse-feil: {parse_err} — rå: {result[:200]}\n")
                    sys.stderr.flush()
                    self._send_json({"error": "KI returnerte ugyldig format"}, 500)
            except Exception as e:
                sys.stderr.write(f"[{self.log_date_time_string()}] ai_highlight_diff FEIL: {e}\n")
                sys.stderr.flush()
                self._send_json({"error": str(e)}, 500)

        elif path == "/api/ai_match_phrase":
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                self._send_json({"error": "GEMINI_API_KEY ikke konfigurert"}, 500)
                return
            text1 = body.get("text1", "")
            text2 = body.get("text2", "")
            phrase = body.get("phrase", "")
            v1 = body.get("version1", "Versjon 1")
            v2 = body.get("version2", "Versjon 2")
            label = body.get("label", "")
            if not text1 or not text2 or not phrase:
                self._send_json({"error": "Mangler tekst eller frase"}, 400)
                return
            sys.stderr.write(f"[{self.log_date_time_string()}] ai_match_phrase: {label} {v1}→{v2} frase='{phrase}'\n")
            sys.stderr.flush()
            try:
                result = gemini_request(
                    api_key,
                    f"Vers: {label}\n\n"
                    f"Versjon A ({v1}):\n{text1}\n\n"
                    f"Brukerens markering i Versjon A: \"{phrase}\"\n\n"
                    f"Versjon B ({v2}):\n{text2}",
                    "Du er en erfaren bibeloversetter. Brukeren har markert en frase i Versjon A "
                    "og vil se den tilsvarende frasen (samme mening, samme rolle i setningen) i Versjon B.\n\n"
                    "Regler:\n"
                    "1. Frasen du returnerer MÅ stå EKSAKT slik den er i Versjon B — samme bokstaver, "
                    "samme bøyning, samme tegnsetting. Ikke oppdikt, ikke parafraser.\n"
                    "2. Den skal være kortest mulig men dekke hele meningen — typisk 1-8 ord.\n"
                    "3. Det er OK om ordlyden er helt ulik, så lenge betydningen er den samme "
                    "(f.eks. 'kjærlighet' ↔ 'elsket', 'evig liv' ↔ 'uendelig livet').\n"
                    "4. Hvis ingen rimelig ekvivalent finnes, eller brukerens frase er for vag, "
                    "returner tom streng.\n\n"
                    "Returner KUN gyldig JSON:\n"
                    '{"match": "eksakt frase fra Versjon B"}\n\n'
                    "Ingen innledning, ingen etterord, ingen forklaring.",
                    max_tokens=120,
                )
                cleaned = result.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                    if cleaned.endswith("```"):
                        cleaned = cleaned.rsplit("\n", 1)[0]
                    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
                try:
                    parsed = json.loads(cleaned)
                    match = (parsed.get("match") or "").strip()
                    # Verifiser at KI-et faktisk returnerte noe som finnes i text2
                    if match and match in text2:
                        self._send_json({"match": match})
                    else:
                        self._send_json({"match": ""})
                except Exception as parse_err:
                    sys.stderr.write(f"[{self.log_date_time_string()}] ai_match_phrase parse-feil: {parse_err} — rå: {result[:200]}\n")
                    sys.stderr.flush()
                    self._send_json({"match": ""})
            except Exception as e:
                sys.stderr.write(f"[{self.log_date_time_string()}] ai_match_phrase FEIL: {e}\n")
                sys.stderr.flush()
                self._send_json({"error": str(e)}, 500)

        elif path == "/api/ai_context":
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                self._send_json({"error": "GEMINI_API_KEY ikke konfigurert"}, 500)
                return
            label = body.get("label", "")
            text = body.get("text", "")
            if not text:
                self._send_json({"error": "Mangler tekst"}, 400)
                return
            sys.stderr.write(f"[{self.log_date_time_string()}] ai_context: {label}\n")
            sys.stderr.flush()
            try:
                # Bestem om dette er ett vers eller et større utsnitt (kapittel/avsnitt)
                is_longer = len(text) > 250
                if is_longer:
                    sys_prompt = (
                        "Du er en bibelforsker. Gi en bred kontekst for denne bibeltekst-delen "
                        "(typisk et helt kapittel eller flere vers): 5-7 setninger som dekker "
                        "hvor i bokens narrativ det er, hvem som snakker og til hvem, hva som "
                        "skjer rett før og etter, tekstens struktur, og hovedpoenget. "
                        "Skriv på norsk, enkelt og presist. Ikke tolk teologisk — kun litterær "
                        "og historisk kontekst. Ingen innledning, bare selve konteksten."
                    )
                    max_toks = 500
                else:
                    sys_prompt = (
                        "Du er en bibelforsker. Gi en kort kontekst for verset på 2-3 setninger: "
                        "hvem som snakker, til hvem, hva som skjer rett før og hva verset handler om. "
                        "Skriv på norsk, enkelt og presist. Ikke tolk teologisk — bare gi litterær/historisk kontekst. "
                        "Ingen innledning, bare selve konteksten."
                    )
                    max_toks = 250
                result = gemini_request(
                    api_key,
                    f"Referanse: {label}\nTekst: {text}",
                    sys_prompt,
                    max_tokens=max_toks,
                )
                self._send_json({"result": result})
            except Exception as e:
                sys.stderr.write(f"[{self.log_date_time_string()}] ai_context FEIL: {e}\n")
                sys.stderr.flush()
                self._send_json({"error": str(e)}, 500)

        elif path == "/api/ai_themes":
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                self._send_json({"error": "GEMINI_API_KEY ikke konfigurert"}, 500)
                return
            label = body.get("label", "")
            text = body.get("text", "")
            if not text:
                self._send_json({"error": "Mangler tekst"}, 400)
                return
            sys.stderr.write(f"[{self.log_date_time_string()}] ai_themes: {label}\n")
            sys.stderr.flush()
            try:
                result = gemini_request(
                    api_key,
                    f"Vers: {label}\nTekst: {text}",
                    "Du er en bibelforsker. Identifiser 3 sentrale tema i dette bibelverset. "
                    "For hvert tema, gi et kort navn (1-3 ord) og en liste med 6-10 presise "
                    "søkestrenger som til sammen finner de stedene i Bibelen hvor samme tema "
                    "faktisk behandles. Kvaliteten på dekningen er viktigere enn antall.\n\n"
                    "Søkestrengene skal være en MIKS av:\n"
                    '- Eksakte fraser i anførselstegn, f.eks. "\\"frykt for Herren\\"" — disse MÅ '
                    "være ordkombinasjoner som faktisk står i norske bibeloversettelser\n"
                    "- Enkelt-ord uten anførselstegn, f.eks. \"lydig\", \"nåde\", \"rettferdig\" — "
                    "disse finner alle bøyde former\n\n"
                    "Varier bøyninger (entall/flertall, bestemt/ubestemt), synonymer og relaterte "
                    "begreper for å få bred dekning. Unngå for vanlige småord (og, i, det). "
                    "Eksempel for tema 'Lov og orden': [\"\\\"Herrens lov\\\"\", \"\\\"budene\\\"\", "
                    "\"forskrifter\", \"rettferdighet\", \"lydighet\", \"\\\"hans bud\\\"\"]\n\n"
                    "Returner KUN gyldig JSON-array med 3 elementer:\n"
                    '[{"name": "Tema", "searches": ["søk1", "søk2", ...]}, ...]\n\n'
                    "Ingen innledning, ingen etterord. Bare JSON-arrayet.",
                    max_tokens=300,
                )
                # Strip markdown code fences if present
                cleaned = result.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                    if cleaned.endswith("```"):
                        cleaned = cleaned.rsplit("\n", 1)[0]
                    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
                try:
                    themes = json.loads(cleaned)
                    if not isinstance(themes, list):
                        raise ValueError("Forventet liste")
                    self._send_json({"themes": themes})
                except Exception as parse_err:
                    sys.stderr.write(f"[{self.log_date_time_string()}] ai_themes parse-feil: {parse_err} — rå: {result[:200]}\n")
                    sys.stderr.flush()
                    self._send_json({"error": "KI returnerte ugyldig format"}, 500)
            except Exception as e:
                sys.stderr.write(f"[{self.log_date_time_string()}] ai_themes FEIL: {e}\n")
                sys.stderr.flush()
                self._send_json({"error": str(e)}, 500)

        else:
            sys.stderr.write(f"[{self.log_date_time_string()}] 404 ukjent POST-sti: {path!r}\n")
            sys.stderr.flush()
            self.send_error(404)


GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def gemini_request(api_key, user_prompt, system_prompt, max_tokens=200):
    if not GENAI_AVAILABLE:
        raise RuntimeError("google-genai pakken er ikke installert")
    response = _genai_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=f"{system_prompt}\n\n{user_prompt}",
    )
    return response.text.strip()


def run_server():
    global bible_data
    bible_data = BibleData()

    if not bible_data.versions:
        print("Error: No Bible versions found. Make sure bible_versions/ directory has version folders with JSON files.")
        sys.exit(1)

    host = "0.0.0.0" if os.environ.get("SERVER_MODE") == "production" else "127.0.0.1"
    server = http.server.HTTPServer((host, PORT), BibleHandler)
    server.timeout = 1

    # Startup diagnostics
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    print(f"Server running at http://{host}:{PORT}")
    print(f"Versjoner lastet: {list(bible_data.versions.keys())}")
    print(f"GEMINI_API_KEY: {'satt (' + str(len(gemini_key)) + ' tegn)' if gemini_key else 'MANGLER - KI-funksjoner deaktivert'}")
    print(f"google-genai SDK: {'lastet' if GENAI_AVAILABLE else 'IKKE tilgjengelig - installer med: pip install google-genai'}")
    print(f"Gemini-modell: {GEMINI_MODEL}")
    sys.stdout.flush()
    if host == "127.0.0.1":
        webbrowser.open(f"http://127.0.0.1:{PORT}")

        def watchdog():
            """Shut down when no heartbeat received for 10 seconds."""
            while True:
                time.sleep(3)
                if time.time() - last_heartbeat > 10:
                    print("\nBrowser closed. Shutting down...")
                    os._exit(0)

        t = threading.Thread(target=watchdog, daemon=True)
        t.start()

    try:
        while True:
            server.handle_request()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    run_server()
