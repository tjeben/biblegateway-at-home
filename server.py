"""
Bible Gateway Norsk - Local Bible search server
Run this file to start the server and open the website in your browser.
"""

import http.server
import json
import os
import re
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
BIBLE_DIR = BASE_DIR / "bible_versions"

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
# Bible data loading
# ──────────────────────────────────────────────

class BibleData:
    def __init__(self):
        self.versions = {}  # version_name → { usfm_code → { "BOOK.CH.VS": text } }
        self.version_books = {}  # version_name → [usfm_codes in order]
        self.book_chapters = {}  # version_name → { usfm_code → max_chapter }
        self._load_all()

    def _load_all(self):
        if not BIBLE_DIR.exists():
            print(f"Warning: {BIBLE_DIR} not found")
            return
        for version_dir in sorted(BIBLE_DIR.iterdir()):
            if not version_dir.is_dir():
                continue
            vname = version_dir.name
            self.versions[vname] = {}
            self.book_chapters[vname] = {}
            codes = []
            for book_file in sorted(version_dir.glob("*.json")):
                parts = book_file.stem.split("_", 2)
                if len(parts) < 2:
                    continue
                code = parts[1]
                try:
                    with open(book_file, "r", encoding="utf-8") as f:
                        self.versions[vname][code] = json.load(f)
                    codes.append(code)
                    # Compute max chapter
                    max_ch = 0
                    for key in self.versions[vname][code]:
                        ch = int(key.split(".")[1])
                        if ch > max_ch:
                            max_ch = ch
                    self.book_chapters[vname][code] = max_ch
                except Exception as e:
                    print(f"Warning: Failed to load {book_file}: {e}")
            self.version_books[vname] = codes
        print(f"Loaded {len(self.versions)} Bible version(s): {', '.join(self.versions.keys())}")

    def get_verses(self, version, book_code, chapter, verse_start=None, verse_end=None):
        """Get verses from a specific book/chapter/verse range."""
        if version not in self.versions:
            return None, f"Version '{version}' not found"
        if book_code not in self.versions[version]:
            return None, f"Book '{book_code}' not found in {version}"

        data = self.versions[version][book_code]
        results = []

        if verse_start is None:
            # Whole chapter
            prefix = f"{book_code}.{chapter}."
            for key, text in data.items():
                if key.startswith(prefix):
                    vs_num = int(key.split(".")[-1])
                    results.append((vs_num, text))
            if not results:
                return None, f"Chapter {chapter} not found in {USFM_TO_NAME.get(book_code, book_code)}"
            results.sort(key=lambda x: x[0])
        else:
            end = verse_end if verse_end is not None else verse_start
            for v in range(verse_start, end + 1):
                key = f"{book_code}.{chapter}.{v}"
                if key in data:
                    results.append((v, data[key]))
            if not results:
                ref = f"{chapter}:{verse_start}" + (f"-{verse_end}" if verse_end and verse_end != verse_start else "")
                return None, f"Verses {ref} not found in {USFM_TO_NAME.get(book_code, book_code)}"

        return results, None

    def get_verses_cross_chapter(self, version, book_code, ch_start, vs_start, ch_end, vs_end):
        """Get verses spanning multiple chapters."""
        if version not in self.versions:
            return None, f"Version '{version}' not found"
        if book_code not in self.versions[version]:
            return None, f"Book '{book_code}' not found in {version}"

        data = self.versions[version][book_code]
        results = []

        for ch in range(ch_start, ch_end + 1):
            prefix = f"{book_code}.{ch}."
            chapter_verses = []
            for key, text in data.items():
                if key.startswith(prefix):
                    vs_num = int(key.split(".")[-1])
                    chapter_verses.append((vs_num, text, ch))

            chapter_verses.sort(key=lambda x: x[0])

            for vs_num, text, ch_num in chapter_verses:
                if ch_num == ch_start and vs_num < vs_start:
                    continue
                if ch_num == ch_end and vs_num > vs_end:
                    continue
                results.append((vs_num, text, ch_num))

        if not results:
            return None, f"Verses {ch_start}:{vs_start}-{ch_end}:{vs_end} not found"

        return results, None

    def get_chapter_range(self, version, book_code, ch_start, ch_end):
        """Get all verses from a range of chapters."""
        if version not in self.versions:
            return None, f"Version '{version}' not found"
        if book_code not in self.versions[version]:
            return None, f"Book '{book_code}' not found in {version}"

        data = self.versions[version][book_code]
        results = []

        for ch in range(ch_start, ch_end + 1):
            prefix = f"{book_code}.{ch}."
            for key, text in data.items():
                if key.startswith(prefix):
                    vs_num = int(key.split(".")[-1])
                    results.append((vs_num, text, ch))

        if not results:
            return None, f"Chapters {ch_start}-{ch_end} not found in {USFM_TO_NAME.get(book_code, book_code)}"

        results.sort(key=lambda x: (x[2], x[0]))
        return results, None


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


def parse_reference(ref_str):
    """
    Parse a reference string like "3:16", "3:16-18", "3:16-4:2", "3", "3-5".
    Returns a dict with parsing results.
    """
    ref_str = ref_str.strip()
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

    if btype == "single_verse":
        verses, err = bible_data.get_verses(version, book, block["chapter"], block["verse"])
        if err:
            return {**base, "error": err, "verses": []}
        return {
            **base,
            "verses": [{"num": v, "chapter": block["chapter"], "text": t} for v, t in verses],
        }

    elif btype == "verse_range":
        verses, err = bible_data.get_verses(version, book, block["chapter"], block["vs_start"], block["vs_end"])
        if err:
            return {**base, "error": err, "verses": []}
        return {
            **base,
            "verses": [{"num": v, "chapter": block["chapter"], "text": t} for v, t in verses],
        }

    elif btype == "whole_chapter":
        verses, err = bible_data.get_verses(version, book, block["chapter"])
        if err:
            return {**base, "error": err, "verses": []}
        return {
            **base,
            "verses": [{"num": v, "chapter": block["chapter"], "text": t} for v, t in verses],
        }

    elif btype == "chapter_range":
        verses, err = bible_data.get_chapter_range(version, book, block["ch_start"], block["ch_end"])
        if err:
            return {**base, "error": err, "verses": []}
        return {
            **base,
            "verses": [{"num": v, "chapter": ch, "text": t} for v, t, ch in verses],
        }

    elif btype == "cross_chapter":
        verses, err = bible_data.get_verses_cross_chapter(
            version, book, block["ch_start"], block["vs_start"], block["ch_end"], block["vs_end"]
        )
        if err:
            return {**base, "error": err, "verses": []}
        return {
            **base,
            "verses": [{"num": v, "chapter": ch, "text": t} for v, t, ch in verses],
        }

    return {"label": block.get("label", "?"), "error": "Unknown block type", "verses": []}


def is_reference_query(query):
    """Check if the query looks like a Bible reference (vs free text search)."""
    # Try to parse first semicolon-separated part
    first_part = query.split(";")[0].strip()
    book_code, remainder = identify_book(first_part)
    if book_code:
        return True
    # Also check if it's just a number (could be continuing context, but standalone = text)
    return False


def search_text(bible_data, version, query, per_book=10):
    """Full-text search: find verses containing all query words (case insensitive, substring).
    Returns up to per_book hits per book, plus total match counts per book."""
    words = query.lower().split()
    if not words:
        return [], {}

    results = []
    book_totals = {}
    for book_code in bible_data.version_books.get(version, []):
        book_name = USFM_TO_NAME.get(book_code, book_code)
        data = bible_data.versions[version][book_code]
        total = 0
        for key, text in data.items():
            text_lower = text.lower()
            if all(w in text_lower for w in words):
                total += 1
                if total <= per_book:
                    parts = key.split(".")
                    ch = int(parts[1])
                    vs = int(parts[2])
                    results.append({
                        "ref": f"{book_name} {ch}:{vs}",
                        "book": book_code,
                        "chapter": ch,
                        "verse": vs,
                        "text": text,
                    })
        if total > 0:
            book_totals[book_code] = total
    return results, book_totals


# ──────────────────────────────────────────────
# HTTP Server
# ──────────────────────────────────────────────

bible_data = None
last_heartbeat = time.time()


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
            self._send_json({"versions": versions})

        elif path == "/api/books":
            version = params.get("version", [""])[0]
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
                results, book_totals = search_text(bible_data, version, query)
                total = sum(book_totals.values())
                self._send_json({"type": "text_search", "results": results, "book_totals": book_totals, "total": total, "query": query, "version": version})

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
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length)) if length else {}
        except Exception:
            self._send_json({"error": "Ugyldig JSON"}, 400)
            return

        if path == "/api/ai_diff":
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
