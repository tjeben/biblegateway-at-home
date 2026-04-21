"""Bible.com (YouVersion) scraper — henter verstekst, fotnoter, kryssreferanser og seksjonsoverskrifter.

Basert på https://github.com/tobiashellerslien/bible-scraper (MIT), men utvidet til å fange alt bible.com
leverer: fotnoter (translator notes), kryssreferanser og seksjonsoverskrifter. Output lagres som
strukturert JSON med én nøkkel per vers.

JSON-struktur per vers:
    {
      "GEN.1.1": {
        "text": "I begynnelsen skapte Gud himmelen og jorden.",
        "footnotes": [{"marker": "a", "text": "Eller 'da Gud begynte å skape'"}],
        "xrefs": ["JHN.1.1", "COL.1.16", "HEB.11.3"],
        "section": "Skapelsen"
      },
      ...
    }

Verdien `section` er bare satt på vers som STARTER en ny seksjon (første vers etter overskriften).
"""

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from book_maps import CHAPTER_COUNT  # noqa: F401 — re-eksporteres for bakoverkompatibilitet

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; biblegateway-scraper/1.0)"}
BASE_URL = "https://www.bible.com/bible"
RATE_LIMIT = 0.1  # sekunder mellom kapittel-requests

# Regex for å trekke ut USFM-referanser fra xref-lenker som "/bible/102/JHN.3.16"
_XREF_URL_RE = re.compile(r"/bible/\d+/([A-Z0-9]+\.\d+(?:\.\d+)?)", re.IGNORECASE)
# Regex for å konvertere xref-tekst som "Joh 3.16" eller "Sal 119,11" til USFM
# (forenklet — bible.com bruker USFM-lenker direkte, så dette er bare en fallback)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _parse_note(note_tag: Tag) -> Dict[str, Any]:
    """Parser en <span class="note"> (fotnote eller kryssref) og returner strukturert innhold."""
    classes = note_tag.get("class") or []
    is_xref = "x" in classes
    is_footnote = "f" in classes

    marker_tag = note_tag.find(class_="label")
    marker = _collapse(marker_tag.get_text()) if marker_tag else ""

    body_tag = note_tag.find(class_="body")
    if not body_tag:
        return {"type": "unknown", "marker": marker, "text": _collapse(note_tag.get_text())}

    if is_xref:
        # Hent både strukturerte USFM-referanser fra lenker og menneskelesbart tekst
        refs: List[str] = []
        for a in body_tag.find_all("a", href=True):
            m = _XREF_URL_RE.search(a["href"])
            if m:
                refs.append(m.group(1).upper())
        # Tekstbasert form av xref (for visning)
        xt = body_tag.find(class_="xt")
        text = _collapse(xt.get_text()) if xt else _collapse(body_tag.get_text())
        return {"type": "xref", "marker": marker, "text": text, "refs": refs}
    elif is_footnote:
        ft = body_tag.find(class_="ft")
        text = _collapse(ft.get_text()) if ft else _collapse(body_tag.get_text())
        return {"type": "footnote", "marker": marker, "text": text}
    else:
        return {"type": "unknown", "marker": marker, "text": _collapse(body_tag.get_text())}


def _extract_verse_content(verse_span: Tag) -> Tuple[str, List[Dict], List[Dict]]:
    """Trekker ut verstekst, fotnoter og kryssreferanser fra en <span class="verse">-tag.

    Returnerer (text, footnotes, xrefs).
    Fotnote/xref-noder inkluderes IKKE i teksten — de separeres ut."""
    footnotes: List[Dict] = []
    xrefs: List[Dict] = []
    text_parts: List[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, NavigableString):
            return
        if not isinstance(node, Tag):
            return
        classes = node.get("class") or []

        if "note" in classes:
            parsed = _parse_note(node)
            if parsed["type"] == "footnote":
                footnotes.append({"marker": parsed["marker"], "text": parsed["text"]})
            elif parsed["type"] == "xref":
                xrefs.append({
                    "marker": parsed["marker"],
                    "text": parsed["text"],
                    "refs": parsed.get("refs", []),
                })
            return  # ikke inkluder note-teksten i selve verset

        if "label" in classes:
            return  # hopp over versnummer-etiketten (vises av klienten via USFM-nøkkelen)

        if "content" in classes:
            text_parts.append(node.get_text())
            return

        # Rekurser inn i andre tagger (wj = words-of-Jesus, nd = names-of-God, etc.)
        for child in node.children:
            walk(child)

    for child in verse_span.children:
        walk(child)

    text = _collapse("".join(text_parts))
    text = text.replace("*", "").strip()
    return text, footnotes, xrefs


def fetch_chapter(book: str, chapter: int, translation_id: int) -> Dict[str, Dict[str, Any]]:
    """Henter et helt kapittel med tekst + fotnoter + xrefs + seksjonsoverskrifter.

    Returnerer dict som ligner:
        {
          "GEN.1.1": {"text": "...", "footnotes": [...], "xrefs": [...], "section": "Skapelsen"},
          "GEN.1.2": {"text": "...", "footnotes": [], "xrefs": [], "section": null},
          ...
        }
    """
    url = f"{BASE_URL}/{translation_id}/{book}.{chapter}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ConnectionError(f"Failed to fetch {book}.{chapter}: {e}")

    soup = BeautifulSoup(resp.text, "html.parser")
    script = soup.find("script", {"id": "__NEXT_DATA__"})
    if not script:
        raise ValueError(f"Fant ikke __NEXT_DATA__ på {url}")
    data = json.loads(script.get_text())
    html_content = data["props"]["pageProps"]["chapterInfo"]["content"]

    inner = BeautifulSoup(html_content, "html.parser")
    result: Dict[str, Dict[str, Any]] = {}

    # Psalme-intro (class="d") — lagres som vers 0
    intro_div = inner.find("div", class_="d")
    if intro_div:
        content_spans = intro_div.find_all("span", class_="content")
        intro_text = _collapse("".join(span.get_text() for span in content_spans))
        if intro_text:
            result[f"{book}.{chapter}.0"] = {
                "text": intro_text,
                "footnotes": [],
                "xrefs": [],
                "section": None,
            }

    # Itererer over alle topp-nivå children for å samle opp seksjonsoverskrifter
    # i riktig rekkefølge før verset som følger etter
    pending_section: Optional[str] = None

    def walk_top_level(root: Tag) -> None:
        nonlocal pending_section
        for node in root.children:
            if not isinstance(node, Tag):
                continue
            classes = node.get("class") or []
            # Seksjonsoverskrifter: <div class="s">, <div class="s1">, <h3>
            if node.name == "div" and any(c in classes for c in ("s", "s1", "s2", "ms", "mr", "r")):
                heading = node.find(class_="heading") or node
                text = _collapse(heading.get_text())
                if text:
                    pending_section = text
            elif "verse" in classes:
                usfm = node.get("data-usfm")
                if not usfm:
                    continue
                text, footnotes, xrefs = _extract_verse_content(node)
                if usfm in result:
                    # Vers som deles over flere tags — konkateneres
                    existing = result[usfm]
                    existing["text"] = _collapse(existing["text"] + " " + text)
                    existing["footnotes"].extend(footnotes)
                    existing["xrefs"].extend(xrefs)
                    # pending_section bør ikke overskrive en eksisterende seksjon
                else:
                    result[usfm] = {
                        "text": text,
                        "footnotes": footnotes,
                        "xrefs": xrefs,
                        "section": pending_section,
                    }
                    pending_section = None
            elif node.name in ("div", "p"):
                # Rekurserer inn i blokk-elementer (vers kan være nøstet i <p class="p">, etc.)
                walk_top_level(node)

    walk_top_level(inner)
    return result


def fetch_book(book: str, translation_id: int, sleep: float = RATE_LIMIT) -> Dict[str, Dict[str, Any]]:
    """Henter hele boken ved å kalle fetch_chapter for alle kapitler."""
    if book not in CHAPTER_COUNT:
        raise KeyError(f"Ukjent bok '{book}'. Bruk USFM-forkortelse (f.eks. 'GEN').")

    result: Dict[str, Dict[str, Any]] = {}
    total = CHAPTER_COUNT[book]
    for ch in range(1, total + 1):
        data = fetch_chapter(book, ch, translation_id)
        result.update(data)
        print(f"  {book} kapittel {ch}/{total} ({len(data)} vers)")
        if ch < total:
            time.sleep(sleep)
    return result


if __name__ == "__main__":
    # Quick test
    print("Tester: henter Johannes 3 i NB88...")
    chapter = fetch_chapter("JHN", 3, 102)
    for usfm, entry in list(chapter.items())[:3]:
        print(f"\n{usfm}:")
        print(f"  Tekst: {entry['text'][:80]}...")
        print(f"  Fotnoter: {len(entry['footnotes'])}")
        print(f"  Xrefs: {len(entry['xrefs'])}")
        print(f"  Seksjon: {entry['section']}")
