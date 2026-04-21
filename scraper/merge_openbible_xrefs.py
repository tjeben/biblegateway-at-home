"""Erstatt xrefs i alle bibel-JSON-filer med OpenBible.info sine strukturerte,
stemme-rankede kryssreferanser.

Input: ../cross_references_openbible.txt (TSV: From Verse, To Verse, Votes)
Output: oppdaterer ../bible_versions/<Versjon>/*.json in-place

Ny xref-struktur per vers:
    "xrefs": [
      {"r": "JHN.1.1-3", "v": 364},
      {"r": "HEB.11.3", "v": 267}
    ]

- r = referanse (USFM). Kan være singel (GEN.1.1) eller range (GEN.1.1-3 samme kap,
  eller GEN.1.1-2.5 på tvers av kapitler).
- v = antall stemmer hos openbible.info (kvalitetsindikator).
- Sortert etter stemmer (høyeste først).
- Negative stemmer filtreres bort.

Beholder footnotes og section fra forrige data.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent.parent
XREF_FILE = BASE / "cross_references_openbible.txt"
BIBLE_DIR = BASE / "bible_versions"

# OpenBible-bokforkortelse → USFM (vår standard)
OB_TO_USFM = {
    "Gen":"GEN","Exod":"EXO","Lev":"LEV","Num":"NUM","Deut":"DEU",
    "Josh":"JOS","Judg":"JDG","Ruth":"RUT","1Sam":"1SA","2Sam":"2SA",
    "1Kgs":"1KI","2Kgs":"2KI","1Chr":"1CH","2Chr":"2CH","Ezra":"EZR",
    "Neh":"NEH","Esth":"EST","Job":"JOB","Ps":"PSA","Prov":"PRO",
    "Eccl":"ECC","Song":"SNG","Isa":"ISA","Jer":"JER","Lam":"LAM",
    "Ezek":"EZK","Dan":"DAN","Hos":"HOS","Joel":"JOL","Amos":"AMO",
    "Obad":"OBA","Jonah":"JON","Mic":"MIC","Nah":"NAM","Hab":"HAB",
    "Zeph":"ZEP","Hag":"HAG","Zech":"ZEC","Mal":"MAL",
    "Matt":"MAT","Mark":"MRK","Luke":"LUK","John":"JHN","Acts":"ACT",
    "Rom":"ROM","1Cor":"1CO","2Cor":"2CO","Gal":"GAL","Eph":"EPH",
    "Phil":"PHP","Col":"COL","1Thess":"1TH","2Thess":"2TH",
    "1Tim":"1TI","2Tim":"2TI","Titus":"TIT","Phlm":"PHM",
    "Heb":"HEB","Jas":"JAS","1Pet":"1PE","2Pet":"2PE",
    "1John":"1JN","2John":"2JN","3John":"3JN","Jude":"JUD","Rev":"REV",
}


def parse_ref(raw):
    """Gjør om 'Gen.1.1' til ('GEN', 1, 1). None ved feil."""
    m = re.match(r"^([^.]+)\.(\d+)\.(\d+)$", raw)
    if not m:
        return None
    book = OB_TO_USFM.get(m.group(1))
    if not book:
        return None
    return book, int(m.group(2)), int(m.group(3))


def normalize_target(raw):
    """Konverter et mål (kan være range som 'John.1.1-John.1.3') til kompakt USFM-form.
    Returnerer en streng som 'JHN.1.1' eller 'JHN.1.1-3' eller 'JHN.1.1-2.5'.
    Returns None ved feil."""
    parts = raw.split("-")
    if len(parts) == 1:
        p = parse_ref(parts[0])
        if not p:
            return None
        return f"{p[0]}.{p[1]}.{p[2]}"
    if len(parts) == 2:
        a = parse_ref(parts[0])
        b = parse_ref(parts[1])
        if not a or not b:
            return None
        if a[0] != b[0]:
            return f"{a[0]}.{a[1]}.{a[2]}-{b[0]}.{b[1]}.{b[2]}"
        # Samme bok
        if a[1] == b[1]:
            # Samme kapittel
            if a[2] == b[2]:
                return f"{a[0]}.{a[1]}.{a[2]}"
            return f"{a[0]}.{a[1]}.{a[2]}-{b[2]}"
        # Kryss-kapittel samme bok
        return f"{a[0]}.{a[1]}.{a[2]}-{b[1]}.{b[2]}"
    return None


def load_xrefs():
    """Les TSV-filen, gruppér per fra-vers, sorter etter stemmer."""
    by_src = defaultdict(list)
    with XREF_FILE.open(encoding="utf-8") as f:
        next(f)  # header
        for line in f:
            parts = line.rstrip("\n\r").split("\t")
            if len(parts) < 3:
                continue
            try:
                votes = int(parts[2])
            except ValueError:
                continue
            if votes < 0:
                continue
            src = parse_ref(parts[0])
            if not src:
                continue
            tgt = normalize_target(parts[1])
            if not tgt:
                continue
            src_key = f"{src[0]}.{src[1]}.{src[2]}"
            by_src[src_key].append({"r": tgt, "v": votes})
    # Sorter hver liste etter stemmer (synkende)
    for k in by_src:
        by_src[k].sort(key=lambda x: -x["v"])
    return by_src


def update_all(by_src):
    versions = sorted([p for p in BIBLE_DIR.iterdir() if p.is_dir()])
    total_files = 0
    total_updated_verses = 0
    total_replaced = 0
    total_cleared = 0
    for vdir in versions:
        print(f"→ {vdir.name}")
        files = sorted(vdir.glob("*.json"))
        for f in files:
            with f.open(encoding="utf-8") as fh:
                data = json.load(fh)
            changed = False
            for key, entry in data.items():
                if not isinstance(entry, dict):
                    continue
                new_xrefs = by_src.get(key, [])
                old = entry.get("xrefs")
                if new_xrefs:
                    entry["xrefs"] = new_xrefs
                    total_replaced += 1
                    total_updated_verses += 1
                    changed = True
                elif old:
                    # ingen OpenBible-data for dette verset → tøm listen
                    entry["xrefs"] = []
                    total_cleared += 1
                    changed = True
            if changed:
                with f.open("w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=2)
                total_files += 1
    print(f"\nFerdig.")
    print(f"  Filer oppdatert: {total_files}")
    print(f"  Vers med nye xrefs: {total_replaced}")
    print(f"  Vers som fikk tømt xrefs: {total_cleared}")


if __name__ == "__main__":
    if not XREF_FILE.exists():
        sys.exit(f"Finner ikke {XREF_FILE}")
    print(f"Leser {XREF_FILE} ...")
    by_src = load_xrefs()
    total = sum(len(v) for v in by_src.values())
    print(f"  {len(by_src)} kilde-vers, {total} xref-par")
    update_all(by_src)
