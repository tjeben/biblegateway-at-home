"""Book name mappings and order — brukt både av scraperen og CLI-verktøyet."""

NORWEGIAN = {
    "GEN": "1. Mosebok",      "EXO": "2. Mosebok",      "LEV": "3. Mosebok",
    "NUM": "4. Mosebok",      "DEU": "5. Mosebok",       "JOS": "Josva",
    "JDG": "Dommerne",        "RUT": "Rut",              "1SA": "1. Samuelsbok",
    "2SA": "2. Samuelsbok",   "1KI": "1. Kongebok",      "2KI": "2. Kongebok",
    "1CH": "1. Krønikebok",   "2CH": "2. Krønikebok",    "EZR": "Esra",
    "NEH": "Nehemja",         "EST": "Ester",             "JOB": "Job",
    "PSA": "Salme",           "PRO": "Ordspråkene",       "ECC": "Forkynneren",
    "SNG": "Høysangen",       "ISA": "Jesaja",            "JER": "Jeremia",
    "LAM": "Klagesangene",    "EZK": "Esekiel",           "DAN": "Daniel",
    "HOS": "Hosea",           "JOL": "Joel",              "AMO": "Amos",
    "OBA": "Obadja",          "JON": "Jona",              "MIC": "Mika",
    "NAM": "Nahum",           "HAB": "Habakkuk",          "ZEP": "Sefanja",
    "HAG": "Haggai",          "ZEC": "Sakarja",           "MAL": "Malaki",
    "MAT": "Matteus",         "MRK": "Markus",            "LUK": "Lukas",
    "JHN": "Johannes",        "ACT": "Apostlenes gjerninger",
    "ROM": "Romerne",         "1CO": "1. Korinterbrev",   "2CO": "2. Korinterbrev",
    "GAL": "Galaterne",       "EPH": "Efeserne",          "PHP": "Filipperne",
    "COL": "Kolosserne",      "1TH": "1. Tessalonikerbrev", "2TH": "2. Tessalonikerbrev",
    "1TI": "1. Timoteus",     "2TI": "2. Timoteus",       "TIT": "Titus",
    "PHM": "Filemon",         "HEB": "Hebreerne",         "JAS": "Jakob",
    "1PE": "1. Peter",        "2PE": "2. Peter",          "1JN": "1. Johannesbrev",
    "2JN": "2. Johannesbrev", "3JN": "3. Johannesbrev",   "JUD": "Judas",
    "REV": "Åpenbaringen",
}

ENGLISH = {
    "GEN": "Genesis",         "EXO": "Exodus",           "LEV": "Leviticus",
    "NUM": "Numbers",         "DEU": "Deuteronomy",      "JOS": "Joshua",
    "JDG": "Judges",          "RUT": "Ruth",             "1SA": "1 Samuel",
    "2SA": "2 Samuel",        "1KI": "1 Kings",          "2KI": "2 Kings",
    "1CH": "1 Chronicles",    "2CH": "2 Chronicles",     "EZR": "Ezra",
    "NEH": "Nehemiah",        "EST": "Esther",            "JOB": "Job",
    "PSA": "Psalms",          "PRO": "Proverbs",          "ECC": "Ecclesiastes",
    "SNG": "Song of Solomon", "ISA": "Isaiah",            "JER": "Jeremiah",
    "LAM": "Lamentations",    "EZK": "Ezekiel",           "DAN": "Daniel",
    "HOS": "Hosea",           "JOL": "Joel",              "AMO": "Amos",
    "OBA": "Obadiah",         "JON": "Jonah",             "MIC": "Micah",
    "NAM": "Nahum",           "HAB": "Habakkuk",          "ZEP": "Zephaniah",
    "HAG": "Haggai",          "ZEC": "Zechariah",         "MAL": "Malachi",
    "MAT": "Matthew",         "MRK": "Mark",              "LUK": "Luke",
    "JHN": "John",            "ACT": "Acts",
    "ROM": "Romans",          "1CO": "1 Corinthians",     "2CO": "2 Corinthians",
    "GAL": "Galatians",       "EPH": "Ephesians",         "PHP": "Philippians",
    "COL": "Colossians",      "1TH": "1 Thessalonians",   "2TH": "2 Thessalonians",
    "1TI": "1 Timothy",       "2TI": "2 Timothy",         "TIT": "Titus",
    "PHM": "Philemon",         "HEB": "Hebrews",           "JAS": "James",
    "1PE": "1 Peter",         "2PE": "2 Peter",           "1JN": "1 John",
    "2JN": "2 John",          "3JN": "3 John",            "JUD": "Jude",
    "REV": "Revelation",
}

# Kanonisk bokrekkefølge (GT deretter NT)
BOOK_ORDER = [
    "GEN", "EXO", "LEV", "NUM", "DEU",
    "JOS", "JDG", "RUT", "1SA", "2SA",
    "1KI", "2KI", "1CH", "2CH", "EZR",
    "NEH", "EST", "JOB", "PSA", "PRO",
    "ECC", "SNG", "ISA", "JER", "LAM",
    "EZK", "DAN", "HOS", "JOL", "AMO",
    "OBA", "JON", "MIC", "NAM", "HAB",
    "ZEP", "HAG", "ZEC", "MAL",
    "MAT", "MRK", "LUK", "JHN", "ACT",
    "ROM", "1CO", "2CO", "GAL", "EPH",
    "PHP", "COL", "1TH", "2TH", "1TI",
    "2TI", "TIT", "PHM", "HEB", "JAS",
    "1PE", "2PE", "1JN", "2JN", "3JN",
    "JUD", "REV",
]

CHAPTER_COUNT = {
    "GEN": 50, "EXO": 40, "LEV": 27, "NUM": 36, "DEU": 34,
    "JOS": 24, "JDG": 21, "RUT":  4, "1SA": 31, "2SA": 24,
    "1KI": 22, "2KI": 25, "1CH": 29, "2CH": 36, "EZR": 10,
    "NEH": 13, "EST":  10, "JOB": 42, "PSA": 150, "PRO": 31,
    "ECC": 12, "SNG":  8, "ISA": 66, "JER": 52, "LAM":  5,
    "EZK": 48, "DAN": 12, "HOS": 14, "JOL":  3, "AMO":  9,
    "OBA":  1, "JON":  4, "MIC":  7, "NAM":  3, "HAB":  3,
    "ZEP":  3, "HAG":  2, "ZEC": 14, "MAL":  4,
    "MAT": 28, "MRK": 16, "LUK": 24, "JHN": 21, "ACT": 28,
    "ROM": 16, "1CO": 16, "2CO": 13, "GAL":  6, "EPH":  6,
    "PHP":  4, "COL":  4, "1TH":  5, "2TH":  3, "1TI":  6,
    "2TI":  4, "TIT":  3, "PHM":  1, "HEB": 13, "JAS":  5,
    "1PE":  5, "2PE":  3, "1JN":  5, "2JN":  1, "3JN":  1,
    "JUD":  1, "REV": 22,
}

# bible.com translation IDs for versjonene vi støtter
# Legg til flere her når du oppdager/verifiserer ID-en (sjekk URL på bible.com)
TRANSLATION_IDS = {
    "NB88":       102,   # Bibelen 1988/2007 (Norsk Bibel)
    "Bibel2011":  29,    # Bibel 2011 (Bibelselskapet)
    "Bibel1930":  121,   # Bibelen 1930 (DNB30)
    "BGO":        2216,  # Bibelen Guds Ord 2017 (Hermon Forlag)
    "NASB1995":   100,
    "ESV":        59,
    "KJV":        1,
    "NIV":        111,
    "NKJV":       114,
}
