"""CLI: scrape en hel Bibel-oversettelse fra bible.com med tekst + fotnoter + xrefs + seksjoner.

Eksempel:
    python scrape_entire_bible.py --version Bibel2011
    python scrape_entire_bible.py --translation-id 29 --lang norwegian
    python scrape_entire_bible.py --version NB88 --output-dir ../bible_versions/NB88_v2

Allerede ferdige bøker hoppes over ved reruns (basert på filnavn), så det er trygt
å avbryte og gjenoppta senere.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Sørg for at scraperen kan importeres når kjøres som modul
sys.path.insert(0, str(Path(__file__).parent))

from bible_scraper import fetch_book  # noqa: E402
from book_maps import BOOK_ORDER, CHAPTER_COUNT, ENGLISH, NORWEGIAN, TRANSLATION_IDS  # noqa: E402

LANG_MAP = {"norwegian": NORWEGIAN, "english": ENGLISH}


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape en hel Bibel-oversettelse til JSON.")
    parser.add_argument("--version", type=str, default=None,
                        help="Versjonsnavn fra TRANSLATION_IDS (f.eks. Bibel2011, NB88, ESV).")
    parser.add_argument("--translation-id", type=int, default=None,
                        help="bible.com translation ID (overstyrer --version).")
    parser.add_argument("--lang", choices=LANG_MAP.keys(), default="norwegian",
                        help="Boknavn-språk for filnavn (default: norwegian).")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Mål-katalog (default: ../bible_versions/<version>).")
    parser.add_argument("--only", type=str, default=None,
                        help="Kommaseparert liste med USFM-koder (f.eks. 'JHN,ROM') — kun disse bøkene scrapes.")
    parser.add_argument("--sleep", type=float, default=0.1,
                        help="Sekunder mellom kapittel-requests (standard 0.1).")
    args = parser.parse_args()

    # Avgjør translation ID og versjonsnavn
    version_name = args.version
    if args.translation_id is not None:
        translation_id = args.translation_id
        if not version_name:
            # Prøv å finne version fra ID
            for name, tid in TRANSLATION_IDS.items():
                if tid == translation_id:
                    version_name = name
                    break
            version_name = version_name or f"bible_{translation_id}"
    elif version_name:
        if version_name not in TRANSLATION_IDS:
            sys.exit(f"Ukjent versjon '{version_name}'. Registrert: {', '.join(TRANSLATION_IDS.keys())}")
        translation_id = TRANSLATION_IDS[version_name]
    else:
        sys.exit("Spesifiser enten --version eller --translation-id.")

    lang = LANG_MAP[args.lang]
    default_output = Path(__file__).parent.parent / "bible_versions" / version_name
    output_dir = Path(args.output_dir) if args.output_dir else default_output
    output_dir.mkdir(parents=True, exist_ok=True)

    books_to_do = args.only.split(",") if args.only else BOOK_ORDER
    existing = set(os.listdir(output_dir))

    print(f"Version: {version_name} (translation_id={translation_id})")
    print(f"Output:  {output_dir}")
    print(f"Books:   {len(books_to_do)}")
    print()

    for book in books_to_do:
        book = book.strip().upper()
        if book not in CHAPTER_COUNT:
            print(f"  hopper over {book} (ukjent bok)")
            continue
        idx = BOOK_ORDER.index(book) + 1
        name = lang.get(book, book)
        filename = f"{idx:02d}_{book}_{name}.json"

        if filename in existing:
            print(f"[hoppet over] {filename} (finnes allerede)")
            continue

        print(f"[henter]      {name} ({book}, {CHAPTER_COUNT[book]} kapitler) ...")
        try:
            verses = fetch_book(book, translation_id, sleep=args.sleep)
        except Exception as e:
            print(f"  FEIL: {e}", file=sys.stderr)
            print("  Venter 5 sek og fortsetter med neste bok ...")
            time.sleep(5)
            continue

        path = output_dir / filename
        with path.open("w", encoding="utf-8") as f:
            json.dump(verses, f, ensure_ascii=False, indent=2)
        print(f"  Lagret {len(verses)} vers -> {path}")

    print("\nFerdig!")


if __name__ == "__main__":
    main()
