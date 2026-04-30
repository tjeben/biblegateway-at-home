"""Build commentaries.db from Matthew Henry's Complete Commentary HTML files.

Source: Ressurser/Bibelkommentarer/matthew_henry/MHC[NN][CCC].HTM
  NN  = 01-66  (Protestant canonical order; 00 = master TOC, skipped)
  CCC = 000    -> book introduction
        001+   -> chapter

Per chapter, Henry groups verses into commentary sections. Anchor pattern:
    <A NAME="Ge1_1"> ... <A NAME="Ge1_2"> ... <A NAME="Sec1">
        -> Sec1 covers verses 1-2
    <A NAME="Ge1_3"> ... <A NAME="Ge1_5"> ... <A NAME="Sec2">
        -> Sec2 covers verses 3-5

Output: commentaries.db at project root with tables `commentaries` and
`commentary_entries` (+ FTS5).
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

# -----------------------------------------------------------------------------
# Config

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "Ressurser" / "Bibelkommentarer" / "matthew_henry"
DB_PATH = ROOT / "commentaries.db"

# Index 0 unused; 1..66 = Protestant canonical order matching MHC NN prefix.
USFM_BY_NN = [
    "",
    "GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA",
    "1KI", "2KI", "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO",
    "ECC", "SNG", "ISA", "JER", "LAM", "EZK", "DAN", "HOS", "JOL", "AMO",
    "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL", "MAT",
    "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP",
    "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE",
    "2PE", "1JN", "2JN", "3JN", "JUD", "REV",
]

FILENAME_RE = re.compile(r"^MHC(\d{2})(\d{3})\.HTM$", re.IGNORECASE)
VERSE_ANCHOR_RE = re.compile(r"^[A-Za-z0-9]+?(\d+)_(\d+)$")
SEC_ANCHOR_RE = re.compile(r"^Sec(\d+)$", re.IGNORECASE)

# -----------------------------------------------------------------------------
# Schema

SCHEMA = """
CREATE TABLE IF NOT EXISTS commentaries (
    id          INTEGER PRIMARY KEY,
    slug        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    author      TEXT,
    year        INTEGER,
    language    TEXT NOT NULL,
    license     TEXT,
    source_url  TEXT
);

CREATE TABLE IF NOT EXISTS commentary_entries (
    id              INTEGER PRIMARY KEY,
    commentary_id   INTEGER NOT NULL REFERENCES commentaries(id),
    book_usfm       TEXT NOT NULL,
    chapter         INTEGER NOT NULL,
    verse_start     INTEGER,
    verse_end       INTEGER,
    scope           TEXT NOT NULL,
    heading         TEXT,
    body_html       TEXT NOT NULL,
    sort_order      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entries_lookup
  ON commentary_entries (commentary_id, book_usfm, chapter, verse_start, verse_end);

CREATE VIRTUAL TABLE IF NOT EXISTS commentary_entries_fts USING fts5 (
    body_html, heading,
    content='commentary_entries',
    content_rowid='id',
    tokenize='unicode61'
);
"""

# -----------------------------------------------------------------------------
# HTML cleanup helpers

def _strip_chrome(soup: BeautifulSoup) -> None:
    """Remove navigation, TOC links, biblesnet headers — anything not commentary."""
    # Drop any TABLE that contains a "Table of Contents" or Previous/Next nav link.
    for tbl in soup.find_all("table"):
        text = tbl.get_text(" ", strip=True).lower()
        if "table of contents" in text or "previous" in text or "back to biblesnet" in text:
            tbl.decompose()
    # Drop top-level h1/h3 site banners.
    for tag in soup.find_all(["h1", "h3"]):
        text = tag.get_text(" ", strip=True).lower()
        if "biblesnet" in text or "matthew henry" in text or "commentary on the whole bible" in text:
            tag.decompose()
    # Drop body background attribute references / hr separators at top level.
    for hr in soup.find_all("hr"):
        # Keep section dividers inside content; only strip the very first/last.
        pass
    # Drop comments.
    from bs4 import Comment
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()


def _rewrite_links(soup: BeautifulSoup) -> None:
    """Strip external bible.gospelcom.net href but keep link text."""
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "gospelcom" in href or "biblesnet" in href:
            a.unwrap()
        else:
            # Keep internal anchors but neutralize them — the consumer doesn't
            # navigate within the file.
            del a["href"]


def _inner_html(tag: Tag) -> str:
    return "".join(str(c) for c in tag.contents).strip()


# -----------------------------------------------------------------------------
# Per-chapter parser

def _walk_anchors(soup: BeautifulSoup):
    """Yield (kind, value, anchor_tag) tuples in document order.

    kind ∈ {"verse", "sec"}. verse value = int (verse number), sec value = int (sec idx).
    """
    for a in soup.find_all("a", attrs={"name": True}):
        name = a.get("name", "")
        m = SEC_ANCHOR_RE.match(name)
        if m:
            yield ("sec", int(m.group(1)), a)
            continue
        m = VERSE_ANCHOR_RE.match(name)
        if m:
            yield ("verse", int(m.group(2)), a)


def _slice_html_between(html: str, start_marker: str, end_marker: str | None) -> str:
    """Return HTML substring after start_marker up to (but not including) end_marker.

    Skips past the closing `</a>` so the fragment starts cleanly without a
    stray `>` from the anchor tag.
    """
    i = html.find(start_marker)
    if i < 0:
        return ""
    i += len(start_marker)
    # Advance past `> </a>` (or `"></a>` etc.) so the fragment begins at content.
    close = html.find("</a>", i)
    if close >= 0 and close - i < 40:
        i = close + len("</a>")
    if end_marker:
        j = html.find(end_marker, i)
        if j >= 0:
            # Step back to before the opening `<a` of the end marker.
            a_open = html.rfind("<a", i, j)
            return html[i:a_open] if a_open > i else html[i:j]
    return html[i:]


def _extract_heading(fragment_soup: BeautifulSoup) -> str | None:
    """Henry marks each section heading as <FONT SIZE=+1><I>...</I></FONT>."""
    for font in fragment_soup.find_all("font"):
        if (font.get("size") or "").lower() in ("+1", "1"):
            i = font.find("i")
            if i:
                txt = i.get_text(" ", strip=True)
                if txt:
                    return txt
    return None


def _clean_fragment(html_fragment: str) -> str:
    """Re-parse a body fragment and strip residual chrome + external links."""
    s = BeautifulSoup(html_fragment, "html.parser")
    _strip_chrome(s)
    _rewrite_links(s)
    # Drop the leading section-heading TABLE (we capture it separately as `heading`).
    first_table = s.find("table")
    if first_table and first_table.find("font", attrs={"size": re.compile(r"\+?1")}):
        first_table.decompose()
    # Strip <body> wrapper and lingering page-level chrome elements.
    body = s.find("body")
    if body:
        body.unwrap()
    for tag in s.find_all(["body", "html", "head", "title", "meta", "style", "script"]):
        tag.decompose()
    # Drop leading <hr/> and empty <center>/<a name="PageN"> wrappers.
    for hr in list(s.find_all("hr"))[:2]:
        # only strip leading hrs (siblings near top)
        if not any(prev for prev in hr.previous_siblings if isinstance(prev, Tag)):
            hr.decompose()
    for a in s.find_all("a", attrs={"name": re.compile(r"^Page\d+$", re.I)}):
        a.decompose()
    out = str(s).strip()
    # Collapse runs of blank lines and stray leading `>` chars.
    out = re.sub(r"^&gt;\s*", "", out)
    out = re.sub(r"\n\s*\n+", "\n\n", out)
    return out


def parse_chapter(path: Path, book_usfm: str, chapter: int) -> list[dict]:
    """Return list of entry dicts for a single MHC chapter file."""
    raw = path.read_text(encoding="latin-1", errors="replace")
    soup = BeautifulSoup(raw, "html.parser")

    anchors = list(_walk_anchors(soup))
    if not anchors:
        # Fallback: dump entire body as chapter_intro
        body = soup.find("body") or soup
        return [{
            "book_usfm": book_usfm, "chapter": chapter,
            "verse_start": None, "verse_end": None,
            "scope": "chapter_intro", "heading": None,
            "body_html": _clean_fragment(_inner_html(body)),
        }]

    entries: list[dict] = []

    # Build sections: each Sec[N] consumes the verse anchors that appeared
    # since the previous Sec (or start of file).
    pending_verses: list[int] = []
    sec_groups: list[tuple[int, list[int]]] = []  # (sec_idx, verses)
    pre_sec_verses: list[int] = []
    saw_first_sec = False
    for kind, value, _tag in anchors:
        if kind == "verse":
            if not saw_first_sec:
                pre_sec_verses.append(value)
            pending_verses.append(value)
        elif kind == "sec":
            saw_first_sec = True
            sec_groups.append((value, pending_verses))
            pending_verses = []

    # Some chapters end with trailing verse anchors after the last Sec — fold
    # them into the last sec_group if any, otherwise into a synthetic group.
    if pending_verses and sec_groups:
        last_sec, last_verses = sec_groups[-1]
        # Trailing verses past the last Sec usually belong to the next (missing)
        # section but in practice they're commentary continuation — attach to last.
        sec_groups[-1] = (last_sec, last_verses + pending_verses)

    # Locate chapter intro: HTML between body start and the first verse anchor
    body_html_str = str(soup.find("body") or soup)
    first_verse_anchor = None
    for kind, _v, tag in anchors:
        if kind == "verse":
            first_verse_anchor = str(tag)
            break

    if first_verse_anchor:
        intro_frag = body_html_str[: body_html_str.find(first_verse_anchor)]
        intro_clean = _clean_fragment(intro_frag)
        # Only emit if it has actual prose (skip if just nav chrome).
        text_only = BeautifulSoup(intro_clean, "html.parser").get_text(" ", strip=True)
        if len(text_only) > 80:
            entries.append({
                "book_usfm": book_usfm, "chapter": chapter,
                "verse_start": None, "verse_end": None,
                "scope": "chapter_intro", "heading": None,
                "body_html": intro_clean,
            })

    # Now slice body_html_str by Sec anchors.
    for i, (sec_idx, verses) in enumerate(sec_groups):
        if not verses:
            continue
        # bs4 lowercases attr names on serialization, so anchors render as
        # `name="Sec1"` even when the source HTML had `NAME="Sec1"`.
        start_marker = f'name="Sec{sec_idx}"'
        end_marker = f'name="Sec{sec_idx + 1}"' if i + 1 < len(sec_groups) else None

        frag = _slice_html_between(body_html_str, start_marker, end_marker)
        if not frag.strip():
            continue
        frag_soup = BeautifulSoup(frag, "html.parser")
        heading = _extract_heading(frag_soup)
        body_html = _clean_fragment(frag)
        text_only = BeautifulSoup(body_html, "html.parser").get_text(" ", strip=True)
        if len(text_only) < 20:
            continue
        entries.append({
            "book_usfm": book_usfm, "chapter": chapter,
            "verse_start": min(verses), "verse_end": max(verses),
            "scope": "verses", "heading": heading,
            "body_html": body_html,
        })

    return entries


def parse_book_intro(path: Path, book_usfm: str) -> dict | None:
    raw = path.read_text(encoding="latin-1", errors="replace")
    soup = BeautifulSoup(raw, "html.parser")
    body = soup.find("body") or soup
    body_html = _clean_fragment(_inner_html(body))
    text_only = BeautifulSoup(body_html, "html.parser").get_text(" ", strip=True)
    if len(text_only) < 100:
        return None
    return {
        "book_usfm": book_usfm, "chapter": 0,
        "verse_start": None, "verse_end": None,
        "scope": "book_intro", "heading": None,
        "body_html": body_html,
    }


# -----------------------------------------------------------------------------
# Driver

def build(db_path: Path = DB_PATH, src_dir: Path = SRC_DIR) -> None:
    if not src_dir.is_dir():
        sys.exit(f"Source dir not found: {src_dir}")

    conn = sqlite3.connect(db_path)
    # Drop existing tables so a re-run is idempotent without needing to delete
    # the file (avoids Windows file-lock issues if a viewer has it open).
    conn.executescript("""
        DROP TABLE IF EXISTS commentary_entries_fts;
        DROP TABLE IF EXISTS commentary_entries;
        DROP TABLE IF EXISTS commentaries;
    """)
    conn.executescript(SCHEMA)

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO commentaries(slug, name, author, year, language, license, source_url) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "matthew_henry",
            "Matthew Henry's Complete Commentary on the Whole Bible",
            "Matthew Henry",
            1706,
            "en",
            "public domain",
            "https://www.biblesnet.com/",
        ),
    )
    commentary_id = cur.lastrowid

    files = sorted(src_dir.glob("MHC*.HTM"))
    print(f"Found {len(files)} MHC*.HTM files")

    rows: list[tuple] = []
    counters = {"book_intro": 0, "chapter_intro": 0, "verses": 0, "skipped": 0}

    for path in files:
        m = FILENAME_RE.match(path.name)
        if not m:
            continue
        nn, ccc = int(m.group(1)), int(m.group(2))
        if not (1 <= nn <= 66):
            continue
        usfm = USFM_BY_NN[nn]

        sort_order = 0
        if ccc == 0:
            entry = parse_book_intro(path, usfm)
            if entry:
                rows.append((
                    commentary_id, entry["book_usfm"], entry["chapter"],
                    entry["verse_start"], entry["verse_end"],
                    entry["scope"], entry["heading"], entry["body_html"],
                    sort_order,
                ))
                counters["book_intro"] += 1
        else:
            entries = parse_chapter(path, usfm, ccc)
            for e in entries:
                rows.append((
                    commentary_id, e["book_usfm"], e["chapter"],
                    e["verse_start"], e["verse_end"],
                    e["scope"], e["heading"], e["body_html"],
                    sort_order,
                ))
                counters[e["scope"]] = counters.get(e["scope"], 0) + 1
                sort_order += 1
            if not entries:
                counters["skipped"] += 1

    cur.executemany(
        "INSERT INTO commentary_entries(commentary_id, book_usfm, chapter, "
        "verse_start, verse_end, scope, heading, body_html, sort_order) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        rows,
    )
    # Populate FTS.
    cur.execute(
        "INSERT INTO commentary_entries_fts(rowid, body_html, heading) "
        "SELECT id, body_html, heading FROM commentary_entries"
    )

    conn.commit()
    conn.close()

    print(f"Inserted {len(rows)} entries")
    for k, v in counters.items():
        print(f"  {k}: {v}")
    print(f"DB written to {db_path} ({db_path.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    build()
