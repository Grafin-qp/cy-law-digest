"""Επίσημη Εφημερίδα της Κυπριακής Δημοκρατίας (Official Gazette) – Government
Printing Office site (Lotus Domino).

Annex views (Count=1000 lists every issue currently held in the 'live' view,
roughly the last three months; older issues live in the yearly archive):

    https://www.mof.gov.cy/mof/gpo/gazette.nsf/dmlgaz_appsw_gr/dmlgaz_appsw_gr?OpenDocument&OpenView&Count=1000&cp=12&app=<N>

    app=16  ΠΑΡΑΡΤΗΜΑ ΠΡΩΤΟ Ι    – laws (general legislation)          → kind=law
    app=2   ΠΑΡΑΡΤΗΜΑ ΠΡΩΤΟ ΙΙ   – budget laws                          → kind=law (part II)
    app=3   ΠΑΡΑΡΤΗΜΑ ΠΡΩΤΟ ΙΙΙ  – ratification laws (treaties)         → kind=law (part III)
    app=6   ΠΑΡΑΡΤΗΜΑ ΤΡΙΤΟ Ι    – Κανονιστικές Διοικητικές Πράξεις    → kind=kdp
    app=13  ΠΑΡΑΡΤΗΜΑ ΕΚΤΟ       – bills as deposited in Parliament     → kind=bill (used as cross-check)

Each row: issue number, date (dd/mm/yyyy), page range, link to an issue page
that carries a single PDF ("$file/<name>.pdf").
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
from .greekdates import parse_date
from .http import Http
from .model import Item
from .pdftext import pdf_to_text
from .window import Window

log = logging.getLogger("cylaw_digest.gazette")

BASE = "https://www.mof.gov.cy/mof/gpo/gazette.nsf/"
VIEW = BASE + "dmlgaz_appsw_gr/dmlgaz_appsw_gr?OpenDocument&OpenView&Count=1000&cp=12&app={app}"

ANNEXES = {
    16: ("Παρ. Ι(Ι)", "law", "I"),
    2: ("Παρ. Ι(ΙΙ)", "law", "II"),
    3: ("Παρ. Ι(ΙΙΙ)", "law", "III"),
    6: ("Παρ. ΙΙΙ(Ι)", "kdp", ""),
    13: ("Παρ. VI", "bill", ""),
}


@dataclass
class Issue:
    app: int
    number: str
    date: Optional[dt.date]
    pages: str
    url: str
    pdf_url: str = ""


def parse_listing(html: str, app: int, base: str = BASE) -> list[Issue]:
    soup = BeautifulSoup(html, "lxml")
    issues: list[Issue] = []
    seen = set()
    for a in soup.select('a[href*="/All/"]'):
        href = a.get("href", "")
        if href in seen:
            continue
        tr = a.find_parent("tr")
        if tr is None:
            continue
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(cells) < 2:
            continue
        seen.add(href)
        num = cells[0]
        date = parse_date(cells[1]) if len(cells) > 1 else None
        pages = cells[2] if len(cells) > 2 else ""
        if not re.fullmatch(r"\d{3,5}", num):
            continue
        issues.append(Issue(app=app, number=num, date=date, pages=pages, url=urljoin(base, href)))
    return issues


def parse_issue_page(html: str, page_url: str) -> tuple[str, dict]:
    soup = BeautifulSoup(html, "lxml")
    meta = {}
    text = soup.get_text("\n")
    for key, pat in (("number", r"Αριθμός Εφημερίδας:\s*(\d+)"), ("pages", r"Σελίδες:\s*([\d\-–]+)"),
                     ("date", r"Ημερομηνία:\s*(\d{1,2}/\d{1,2}/\d{4})")):
        m = re.search(pat, text)
        if m:
            meta[key] = m.group(1)
    pdf = ""
    for a in soup.find_all("a", href=True):
        if re.search(r"\.pdf$", a["href"], re.I) or "$file" in a["href"].lower():
            pdf = urljoin(page_url, a["href"]).replace(" ", "%20")
            break
    return pdf, meta


class GazetteCollector:
    def __init__(self, http: Http, window: Window, apps: tuple[int, ...] = (16, 2, 3, 6), max_pdf_pages: int = 400):
        self.http = http
        self.window = window
        self.apps = apps
        self.max_pdf_pages = max_pdf_pages
        self.status: dict[str, dict] = {}

    def issues_in_window(self, app: int) -> list[Issue]:
        url = VIEW.format(app=app)
        res = self.http.get(url)
        key = f"gazette_app{app}"
        if not res.ok:
            self.status[key] = {"ok": False, "reason": res.reason, "url": url}
            return []
        issues = parse_listing(res.text, app)
        oldest = min((i.date for i in issues if i.date), default=None)
        coverage_warning = None
        if oldest and oldest > self.window.start:
            coverage_warning = (f"live view starts at {oldest.isoformat()}, window starts {self.window.start.isoformat()} – "
                                f"older issues are only in the yearly archive")
        chosen = [i for i in issues if self.window.contains(i.date)]
        self.status[key] = {"ok": True, "listed": len(issues), "in_window": len(chosen), "url": url,
                            "warning": coverage_warning, "label": ANNEXES[app][0],
                            "issues": [{"number": i.number, "date": i.date.isoformat() if i.date else None} for i in chosen],
                            "latest_listed": max((i.date for i in issues if i.date), default=None).isoformat() if issues else None}
        return chosen

    def resolve_pdf(self, issue: Issue) -> Optional[str]:
        res = self.http.get(issue.url)
        if not res.ok:
            issue.pdf_url = ""
            return None
        pdf, meta = parse_issue_page(res.text, issue.url)
        issue.pdf_url = pdf
        if meta.get("date") and not issue.date:
            issue.date = parse_date(meta["date"])
        return pdf or None

    def collect(self) -> list[Item]:
        items: list[Item] = []
        for app in self.apps:
            label, kind, part = ANNEXES[app]
            for issue in self.issues_in_window(app):
                pdf_url = self.resolve_pdf(issue)
                if not pdf_url:
                    log.warning("no pdf for issue %s (%s)", issue.number, label)
                    continue
                res = self.http.get_pdf(pdf_url)
                if not res.ok:
                    self.status.setdefault("gazette_pdf_failures", []).append({"issue": issue.number, "reason": res.reason})
                    continue
                text = pdf_to_text(res.content, max_pages=self.max_pdf_pages)
                if kind == "law":
                    items += self._laws(issue, text, label, part)
                elif kind == "kdp":
                    items += self._kdps(issue, text, label)
        return items

    def _laws(self, issue: Issue, text: str, label: str, part: str) -> list[Item]:
        out = []
        for number, seg in acts.split_laws_in_annex(text):
            p = acts.parse_law_text(seg, number_hint=number)
            it = Item(
                id=f"law-{number}", contour="adopted", kind="law", source="gazette",
                source_label=f"Επίσημη Εφημερίδα, {label}, Αρ. {issue.number}",
                date=issue.date, date_kind="published", title_el=p.title or p.caps_title,
                number=f"Ν. {number}", url=issue.url, pdf_url=issue.pdf_url,
                verbatim={"title": p.title, "long_title": p.caps_title},
                excerpt=p.excerpt, entry_into_force=p.entry_into_force,
                extra={"part": part, "gazette_no": issue.number, "gazette_pages": issue.pages, "full_text": p.text},
                warnings=p.warnings,
            )
            out.append(it)
        if not out:
            log.warning("annex %s issue %s: no laws parsed (text length %d)", label, issue.number, len(text))
        return out

    def _kdps(self, issue: Issue, text: str, label: str) -> list[Item]:
        out = []
        for number, seg in acts.split_kdp_sections(text):
            p = acts.parse_kdp_section(number, seg, gazette_no=issue.number, gazette_date=issue.date)
            it = Item(
                id=f"kdp-{number}", contour="adopted", kind="kdp", source="gazette",
                source_label=f"Επίσημη Εφημερίδα, {label}, Αρ. {issue.number}",
                date=issue.date, date_kind="published", title_el=p.title,
                number=f"Κ.Δ.Π. {number}", url=issue.url, pdf_url=issue.pdf_url,
                verbatim={"title": p.title, "parent_law": p.parent_law, "instrument": p.instrument},
                excerpt=p.excerpt, entry_into_force=p.entry_into_force,
                extra={"gazette_no": issue.number, "gazette_pages": issue.pages, "full_text": p.text},
                warnings=p.warnings,
            )
            out.append(it)
        if not out:
            log.warning("annex %s issue %s: no Κ.Δ.Π. parsed (text length %d)", label, issue.number, len(text))
        return out
