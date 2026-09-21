"""gov.cy – the central government portal. Every ministry/department
announcement is a WordPress post on the root site, tagged with topic
categories; department sub-sites (e.g. /mof-tax/news/) only re-list those
posts. One API call per week therefore covers the Tax Department, Ministry of
Interior (Land Registry, migration), Labour / Social Insurance, Commerce
(Registrar's parent ministry) and the Ministry of Finance.

    https://www.gov.cy/wp-json/wp/v2/posts?after=…&before=…&categories=182,183,254,218,188&per_page=100

Categories (id → topic):
    182 Οικονομία, 183 Εσωτερικά Θέματα, 254 Μετανάστευση,
    218 Εργασία και Κοινωνικές Ασφαλίσεις, 188 Ενέργεια, Εμπόριο και Βιομηχανία,
    217 Δικαιοσύνη και Δημόσια Τάξη (added for court-fee / justice reform notices)

Department attribution is done from the title ("Ανακοίνωση του Τμήματος
Φορολογίας …"), which is how gov.cy itself names them.
"""
from __future__ import annotations

import datetime as dt
import html as htmlmod
import logging
import re

from bs4 import BeautifulSoup

from .greekdates import strip_accents
from .http import Http
from .model import Item
from .window import Window

log = logging.getLogger("cylaw_digest.govcy")

API = "https://www.gov.cy/wp-json/wp/v2/posts"
CATEGORIES = {182: "Οικονομία", 183: "Εσωτερικά Θέματα", 254: "Μετανάστευση",
              218: "Εργασία και Κοινωνικές Ασφαλίσεις", 188: "Ενέργεια, Εμπόριο και Βιομηχανία",
              217: "Δικαιοσύνη και Δημόσια Τάξη"}
DEPARTMENTS = [
    ("Τμήμα Φορολογίας", r"τμημα\w* φορολογιασ|tax department"),
    ("Τμήμα Εφόρου Εταιρειών", r"εφορ\w* εταιρειων|εφορ\w* συνεργατικων"),
    ("Τμήμα Κτηματολογίου και Χωρομετρίας", r"κτηματολογ"),
    ("Τμήμα Αρχείου Πληθυσμού και Μετανάστευσης", r"αρχει\w* πληθυσμου|μεταναστευσησ"),
    ("Υφυπουργείο Μετανάστευσης", r"υφυπουργει\w* μεταναστευσ"),
    ("Τμήμα Εργασίας", r"τμημα\w* εργασιασ"),
    ("Τμήμα Εργασιακών Σχέσεων", r"εργασιακων σχεσεων"),
    ("Υπηρεσίες Κοινωνικών Ασφαλίσεων", r"κοινωνικων ασφαλισεων"),
    ("Υπουργείο Οικονομικών", r"υπουργ\w* οικονομικων"),
    ("Υπουργείο Εσωτερικών", r"υπουργ\w* εσωτερικων"),
    ("Υπουργείο Εργασίας", r"υπουργ\w* εργασιασ"),
    ("Υπουργείο Ενέργειας, Εμπορίου και Βιομηχανίας", r"υπουργ\w* ενεργειασ"),
    ("Υπουργικό Συμβούλιο", r"υπουργικ\w* συμβουλι"),
    ("Νομική Υπηρεσία", r"νομικ\w* υπηρεσια"),
]


def department(title: str) -> str:
    t = strip_accents(title).lower().replace("ς", "σ")
    for name, pat in DEPARTMENTS:
        if re.search(pat, t):
            return name
    return ""


def clean(s: str) -> str:
    return htmlmod.unescape(BeautifulSoup(s or "", "lxml").get_text("\n")).strip()


class GovCyCollector:
    def __init__(self, http: Http, window: Window, categories: tuple[int, ...] = tuple(CATEGORIES)):
        self.http = http
        self.window = window
        self.categories = categories
        self.status: dict[str, object] = {}

    def fetch(self) -> list[dict]:
        out: list[dict] = []
        for page in range(1, 6):
            res = self.http.get(API, params={
                "after": self.window.iso_after, "before": self.window.iso_before,
                "categories": ",".join(map(str, self.categories)), "per_page": 100, "page": page,
                "orderby": "date", "order": "desc", "_fields": "id,date,modified,link,title,excerpt,content,categories",
            })
            if not res.ok:
                self.status = {"ok": False, "reason": res.reason, "url": res.url}
                return out
            try:
                data = res.json()
            except Exception:
                self.status = {"ok": False, "reason": "bad_json", "url": res.url}
                return out
            if isinstance(data, dict):
                break
            out += data
            if len(data) < 100:
                break
        self.status = {"ok": True, "posts": len(out)}
        return out

    def collect(self) -> list[Item]:
        items = []
        for p in self.fetch():
            title = re.sub(r"\s+", " ", clean(p["title"]["rendered"]))
            body = clean(p.get("content", {}).get("rendered", ""))
            excerpt = clean(p.get("excerpt", {}).get("rendered", ""))
            d = dt.datetime.fromisoformat(p["date"][:19]).date()
            cats = [int(c) for c in p.get("categories", [])]
            dept = department(title)
            items.append(Item(
                id=f"govcy-{p['id']}", contour="regulator", kind="announcement", source="govcy",
                source_label=dept or ("gov.cy — " + ", ".join(CATEGORIES.get(c, str(c)) for c in cats if c in CATEGORIES)),
                date=d, date_kind="announced", title_el=title, url=p.get("link", ""),
                verbatim={"excerpt": excerpt[:1200], "body": body[:8000]},
                extra={"department": dept, "categories": cats, "topics": [CATEGORIES.get(c, "") for c in cats if c in CATEGORIES]},
            ))
        return items
