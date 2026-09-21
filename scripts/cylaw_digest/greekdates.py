"""Greek date parsing: '24 Ιουλίου 2026', '11.9.2026', '11/09/2026', '04 ΣΕΠ 2026'."""
from __future__ import annotations

import datetime as dt
import re
import unicodedata

_MONTHS = {
    # genitive / nominative / abbreviations, accent-stripped, lower-case
    "ιανουαριου": 1, "ιανουαριος": 1, "ιαν": 1,
    "φεβρουαριου": 2, "φεβρουαριος": 2, "φεβ": 2,
    "μαρτιου": 3, "μαρτιος": 3, "μαρ": 3,
    "απριλιου": 4, "απριλιος": 4, "απρ": 4,
    "μαιου": 5, "μαιος": 5, "μαι": 5,
    "ιουνιου": 6, "ιουνιος": 6, "ιουν": 6,
    "ιουλιου": 7, "ιουλιος": 7, "ιουλ": 7,
    "αυγουστου": 8, "αυγουστος": 8, "αυγ": 8,
    "σεπτεμβριου": 9, "σεπτεμβριος": 9, "σεπ": 9, "σεπτ": 9,
    "οκτωβριου": 10, "οκτωβριος": 10, "οκτ": 10,
    "νοεμβριου": 11, "νοεμβριος": 11, "νοε": 11,
    "δεκεμβριου": 12, "δεκεμβριος": 12, "δεκ": 12,
    # English (CBC site)
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def month_number(word: str) -> int | None:
    key = strip_accents(word).lower().strip(".")
    return _MONTHS.get(key)


_NUMERIC = re.compile(r"(?<![\d.])(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})(?![\d./])")
_WORDY = re.compile(r"\b(\d{1,2})(?:η|ης|ας)?\s+([A-Za-zΑ-Ωα-ωΆ-Ώά-ώ]+)\.?\s+(\d{4})\b")


def parse_date(text: str) -> dt.date | None:
    """Return the first date found in text, or None."""
    m = _NUMERIC.search(text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        try:
            return dt.date(y, mo, d)
        except ValueError:
            pass
    m = _WORDY.search(text)
    if m:
        mo = month_number(m.group(2))
        if mo:
            try:
                return dt.date(int(m.group(3)), mo, int(m.group(1)))
            except ValueError:
                return None
    return None


def find_all_dates(text: str) -> list[dt.date]:
    out: list[dt.date] = []
    for m in _NUMERIC.finditer(text):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        try:
            out.append(dt.date(y, mo, d))
        except ValueError:
            pass
    for m in _WORDY.finditer(text):
        mo = month_number(m.group(2))
        if mo:
            try:
                out.append(dt.date(int(m.group(3)), mo, int(m.group(1))))
            except ValueError:
                pass
    return out
