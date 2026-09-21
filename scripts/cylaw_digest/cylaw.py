"""CyLaw (Cyprus Bar Association legal database).

Two facts about CyLaw that the old skill got wrong:

* `/nomoi/<year>_index.html` is the table of *basic* legislation only (a
  curated subset). The complete numbered list of every law of the year is
  `/nomoi/<year>_arith_index.html`, with one PDF per law at
  `/nomoi/arith/<year>_<part>_<nnn>.pdf` (three-digit, zero-padded).
* Pages are served in windows-1253 and *declare* it in a <meta> tag. They are
  perfectly readable once decoded correctly; the "garbled Greek" the old skill
  saw was a decoding artefact of the fetch tool, and titles guessed from that
  garbage were wrong.

Laws are numbered in publication order, so "what was published in the window"
= walk each part from the highest number down, read the Gazette date from the
PDF header, stop once we are past the window. Stateless, ~5–15 small PDFs per
week.

Κ.Δ.Π. (secondary legislation) has its own, richer index at `/KDP/<year>.html`:
every entry's anchor text carries the title AND the Gazette reference –
"ΚΔΠ 329/2026, <title>, E.E. Παρ.ΙΙΙ(1), Αρ. 6045, Σελ. 2088, 11/9/2026" – with
a per-act PDF at `/KDP/data/<year>_1_<n>.pdf`. It is updated the day the
Gazette issue appears, so it replaces parsing the 30-page annex PDF from
mof.gov.cy. Dates in the anchor text occasionally carry typos (11/6/2026 for
an issue dated 11/9/2026); the issue number is reliable, so the date of an
issue is taken by majority vote over its entries.

cylii.org is the same institute's new front-end (UTF-8 listings at
/cy/legis/arith and /cy/legis/kdp/arith, a daily /updates?date= feed) – handy
for the WebFetch fallback because the fetch tool cannot read windows-1253 –
but its PDF viewer returns 404, so PDFs are always taken from cylaw.org.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from . import acts
from .http import Http
from .model import Item
from .pdftext import pdf_to_text
from .window import Window

log = logging.getLogger("cylaw_digest.cylaw")

BASE = "https://www.cylaw.org"
ARITH_INDEX = BASE + "/nomoi/{year}_arith_index.html"
KDP_INDEX = BASE + "/KDP/{year}.html"
KDP_ENTRY = re.compile(
    r"^\s*ΚΔΠ[\s\u00a0]+(\d+[Α-Ω]?)\s*/\s*(\d{4})\s*,\s*(.+?)\s*,\s*E\.?E\.?\s*Παρ\.?\s*([^,]+?)\s*,\s*Αρ\.\s*(\d+)\s*,\s*Σελ\.\s*(\d+)\s*,\s*(\d{1,2}/\d{1,2}/\d{4})\s*$",
    re.S)
ENTRY = re.compile(r"^\s*[NΝ]\.\s*(\d+[Α-ΩA-Z]?)\s*\(\s*([IΙ]{1,3})\s*\)\s*/\s*(\d{4})\s*[-–]\s*(.+?)\s*$")


@dataclass
class IndexEntry:
    number: str      # "124(I)/2026"
    part: str        # I | II | III
    seq: int         # 124
    title: str
    pdf_url: str
    year: int


def parse_arith_index(html: str, base: str = BASE) -> list[IndexEntry]:
    soup = BeautifulSoup(html, "lxml")
    out: list[IndexEntry] = []
    for a in soup.find_all("a", href=True):
        if "/nomoi/arith/" not in a["href"]:
            continue
        m = ENTRY.match(a.get_text(" ", strip=True))
        if not m:
            continue
        num, part, year, title = m.groups()
        part = part.replace("Ι", "I")
        seq = int(re.sub(r"\D", "", num) or 0)
        out.append(IndexEntry(number=f"{num}({part})/{year}", part=part, seq=seq, title=title.strip(),
                              pdf_url=urljoin(base, a["href"]), year=int(year)))
    return out


@dataclass
class KdpEntry:
    number: str      # "329/2026"
    seq: int
    year: int
    title: str
    annex: str       # "ΙΙΙ(1)"
    issue: str       # "6045"
    page: str
    date: Optional[dt.date]      # as printed (may be a typo)
    pdf_url: str


def parse_kdp_index(html: str, base: str = BASE) -> list[KdpEntry]:
    soup = BeautifulSoup(html, "lxml")
    out: list[KdpEntry] = []
    for a in soup.find_all("a", href=True):
        if "/KDP/data/" not in a["href"]:
            continue
        text = a.get_text(" ", strip=True).replace("\u00a0", " ")
        m = KDP_ENTRY.match(text)
        if not m:
            # tolerate entries without the Gazette tail
            m2 = re.match(r"^\s*ΚΔΠ\s+(\d+[Α-Ω]?)\s*/\s*(\d{4})\s*,\s*(.+?)\s*$", text, re.S)
            if not m2:
                continue
            num, year, title = m2.groups()
            out.append(KdpEntry(number=f"{num}/{year}", seq=int(re.sub(r"\D", "", num) or 0), year=int(year),
                                title=re.sub(r"\s+", " ", title), annex="", issue="", page="", date=None,
                                pdf_url=urljoin(base, a["href"])))
            continue
        num, year, title, annex, issue, page, date = m.groups()
        from .greekdates import parse_date
        out.append(KdpEntry(number=f"{num}/{year}", seq=int(re.sub(r"\D", "", num) or 0), year=int(year),
                            title=re.sub(r"\s+", " ", title), annex=annex.strip(), issue=issue, page=page,
                            date=parse_date(date), pdf_url=urljoin(base, a["href"])))
    return out


def issue_dates(entries: list[KdpEntry]) -> dict[str, dt.date]:
    """Majority date per Gazette issue number – the printed per-entry date is occasionally mistyped."""
    votes: dict[str, dict[dt.date, int]] = {}
    for e in entries:
        if e.issue and e.date:
            votes.setdefault(e.issue, {})[e.date] = votes.setdefault(e.issue, {}).get(e.date, 0) + 1
    return {iss: max(v.items(), key=lambda kv: (kv[1], kv[0]))[0] for iss, v in votes.items()}


class CylawKdpCollector:
    """Κ.Δ.Π. of the window from CyLaw's /KDP/<year>.html + per-act PDFs."""

    def __init__(self, http: Http, window: Window, fetch_pdfs: bool = True, max_pdfs: int = 80):
        self.http = http
        self.window = window
        self.fetch_pdfs = fetch_pdfs
        self.max_pdfs = max_pdfs
        self.status: dict[str, dict] = {}

    def collect(self) -> list[Item]:
        items: list[Item] = []
        for year in sorted({self.window.start.year, self.window.end.year}):
            url = KDP_INDEX.format(year=year)
            res = self.http.get(url)
            if not res.ok:
                self.status[f"kdp_index_{year}"] = {"ok": False, "reason": res.reason, "url": url}
                continue
            entries = parse_kdp_index(res.text)
            dates = issue_dates(entries)
            chosen = []
            for e in entries:
                d = dates.get(e.issue) or e.date
                if self.window.contains(d):
                    chosen.append((e, d))
            self.status[f"kdp_index_{year}"] = {"ok": True, "entries": len(entries), "in_window": len(chosen), "url": url,
                                                 "latest": entries[-1].number if entries else None,
                                                 "issues": sorted({e.issue for e, _ in chosen})}
            fetched = 0
            for e, d in chosen:
                excerpt, eif, verbatim, warnings, text = "", "", {}, [], ""
                if self.fetch_pdfs and fetched < self.max_pdfs:
                    res = self.http.get_pdf(e.pdf_url)
                    fetched += 1
                    if res.ok:
                        p = acts.parse_kdp_section(e.number, pdf_to_text(res.content, max_pages=40), gazette_no=e.issue, gazette_date=d)
                        excerpt, eif, text = p.excerpt, p.entry_into_force, p.text
                        verbatim = {"parent_law": p.parent_law, "instrument": p.instrument, "short_title": p.title if "short_title_not_found" not in p.warnings else ""}
                        warnings = [w for w in p.warnings if w != "short_title_not_found"]
                    else:
                        warnings = [f"pdf_{res.reason}"]
                        self.status.setdefault("kdp_pdf_failures", []).append({"number": e.number, "reason": res.reason})
                if e.date and d != e.date:
                    warnings.append(f"index_date_typo:{e.date.isoformat()}->{d.isoformat()}")
                items.append(Item(
                    id=f"kdp-{e.number}", contour="adopted", kind="kdp", source="cylaw",
                    source_label=f"CyLaw / Επίσημη Εφημερίδα, Παρ. {e.annex or 'ΙΙΙ(Ι)'}, Αρ. {e.issue}",
                    date=d, date_kind="published", title_el=e.title, number=f"Κ.Δ.Π. {e.number}",
                    url=e.pdf_url, pdf_url=e.pdf_url,
                    verbatim={"title": e.title, **verbatim}, excerpt=excerpt, entry_into_force=eif,
                    extra={"gazette_no": e.issue, "gazette_page": e.page, "annex": e.annex, "seq": e.seq, "year": e.year, "full_text": text},
                    warnings=warnings,
                ))
            self.status[f"kdp_pdfs_{year}"] = {"fetched": fetched}
        return items


class CylawCollector:
    def __init__(self, http: Http, window: Window, parts: tuple[str, ...] = ("I", "II", "III"),
                 max_pdfs_per_part: int = 60, tolerance: int = 2):
        self.http = http
        self.window = window
        self.parts = parts
        self.max_pdfs_per_part = max_pdfs_per_part
        self.tolerance = tolerance  # consecutive too-old PDFs before we stop walking down
        self.status: dict[str, dict] = {}

    def years(self) -> list[int]:
        return sorted({self.window.start.year, self.window.end.year})

    def index(self, year: int) -> list[IndexEntry]:
        url = ARITH_INDEX.format(year=year)
        res = self.http.get(url)
        if not res.ok:
            self.status[f"cylaw_index_{year}"] = {"ok": False, "reason": res.reason, "url": url}
            return []
        entries = parse_arith_index(res.text)
        self.status[f"cylaw_index_{year}"] = {"ok": True, "entries": len(entries), "url": url}
        return entries

    def collect(self) -> list[Item]:
        items: list[Item] = []
        for year in self.years():
            entries = self.index(year)
            for part in self.parts:
                part_entries = sorted((e for e in entries if e.part == part), key=lambda e: e.seq, reverse=True)
                too_old = 0
                fetched = 0
                failures = 0
                lowest_checked = None
                for e in part_entries:
                    if fetched >= self.max_pdfs_per_part or too_old > self.tolerance or failures >= 3:
                        break
                    res = self.http.get_pdf(e.pdf_url)
                    fetched += 1
                    if not res.ok:
                        failures += 1
                        self.status.setdefault("cylaw_pdf_failures", []).append({"number": e.number, "reason": res.reason})
                        continue
                    failures = 0
                    text = pdf_to_text(res.content, max_pages=12)
                    p = acts.parse_law_text(text, number_hint=e.number)
                    d = p.gazette_date
                    lowest_checked = e.number
                    if d is None:
                        # cannot date it – keep walking, but flag
                        items.append(self._item(e, p, None, ["gazette_date_not_found"]))
                        continue
                    if d < self.window.start:
                        too_old += 1
                        continue
                    too_old = 0
                    if d > self.window.end:
                        continue
                    items.append(self._item(e, p, d, []))
                self.status[f"cylaw_walk_{year}_{part}"] = {"fetched": fetched, "listed": len(part_entries),
                                                             "highest": part_entries[0].number if part_entries else None,
                                                             "checked_down_to": lowest_checked}
        # drop undated items unless nothing else is known about that number
        dated = {i.number for i in items if i.date}
        return [i for i in items if i.date or i.number not in dated]

    def _item(self, e: IndexEntry, p: acts.ParsedAct, d: Optional[dt.date], warnings: list[str]) -> Item:
        return Item(
            id=f"law-{e.number}", contour="adopted", kind="law", source="cylaw",
            source_label=f"CyLaw / Επίσημη Εφημερίδα, Παρ. Ι({e.part}), Αρ. {p.gazette_no or '?'}",
            date=d, date_kind="published", title_el=e.title, number=f"Ν. {e.number}",
            url=e.pdf_url, pdf_url=e.pdf_url,
            verbatim={"title": e.title, "long_title": p.caps_title, "promulgation_title": p.title},
            excerpt=p.excerpt, entry_into_force=p.entry_into_force,
            extra={"part": e.part, "gazette_no": p.gazette_no, "seq": e.seq, "year": e.year, "full_text": p.text},
            warnings=warnings + p.warnings,
        )
