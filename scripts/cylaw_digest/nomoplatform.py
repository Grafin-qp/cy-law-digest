"""Nomoplatform (nomoplatform.cy) – the parliamentary observatory. It is a
WordPress site with an open REST API, which beats scraping its "Load more"
listing:

    /wp-json/wp/v2/bills            custom post type, one per bill / regulation
        taxonomies: bill-status, thematic-unit, type-of-legislation, competent-ministry
        content.rendered = the Σκοπός (purpose) paragraph as published
    /wp-json/wp/v2/posts            news; category 488 = Αποφάσεις Ολομέλειας (plenary decisions),
                                    277.. = committee news, 309 = Πρόγραμμα (weekly agenda)
    /wp-json/wp/v2/<taxonomy>       term lists (id → name)

The bill *page* (HTML) additionally carries the dated timeline (submission,
committee discussion, plenary vote) and the file number; the API does not
expose those, so we fetch the page for candidates only.

The site sits behind Cloudflare. Plain HTTP clients may get the "Just a
moment…" challenge; the collector reports that as reason=cloudflare and the
skill falls back to WebFetch for these URLs (see SKILL.md, fallback mode).
"""
from __future__ import annotations

import datetime as dt
import html as htmlmod
import json
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from .greekdates import find_all_dates, strip_accents
from .http import Http
from .model import Item
from .window import Window

log = logging.getLogger("cylaw_digest.nomoplatform")

BASE = "https://www.nomoplatform.cy"
API = BASE + "/wp-json/wp/v2/"
BILL_FIELDS = "id,date,modified,link,slug,title,content,bill-status,thematic-unit,type-of-legislation,competent-ministry"
POST_FIELDS = "id,date,modified,link,slug,title,content,excerpt,categories"

CAT_PLENARY = 488
CAT_PROGRAMME = 309
CAT_OTHER_NEWS = 310
CAT_COMMITTEES = {484: "Οικονομικών", 473: "Εσωτερικών", 477: "Νομικών", 480: "Εργασίας", 479: "Ενέργειας-Εμπορίου"}
TAXONOMIES = ("bill-status", "thematic-unit", "type-of-legislation", "competent-ministry")

EVENT_PATTERNS = [   # order matters: "Κατάθεση και παραπομπή στην Επιτροπή" is a submission, not a committee session
    ("voted", r"υπερψηφ|καταψηφ|ψηφισ|ψηφιση απο την ολομελεια"),
    ("withdrawn", r"αποσυρσ|αποσυρ"),
    ("postponed", r"αναβολ|αναβλ"),
    ("submitted", r"καταθεσ|παραπομπ|κατατεθηκε"),
    ("committee", r"συζητησ|συζητ|εξετασ|επιτροπ"),
]


def html_to_text(s: str) -> str:
    if not s:
        return ""
    soup = BeautifulSoup(s, "lxml")
    t = soup.get_text("\n")
    t = htmlmod.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


def classify_event(text: str) -> str:
    t = strip_accents(text).lower()
    for kind, pat in EVENT_PATTERNS:
        if re.search(strip_accents(pat), t):
            return kind
    return "event"


def extract_timeline(page_text: str) -> list[dict]:
    """Return [{date, text, kind}] for every dated line in a bill page's text.

    We do not know (and do not want to depend on) the exact HTML of the theme:
    any line containing a date, together with its neighbours, is an event.
    """
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
    out = []
    for i, ln in enumerate(lines):
        dates = find_all_dates(ln)
        if not dates:
            continue
        # the event text is on the date's own line or the next undated line (Nomoplatform lists
        # "date / event"); the previous line belongs to the previous event and must not leak in
        own = re.sub(r"\s+", " ", ln).strip()
        nxt = lines[i + 1] if i + 1 < len(lines) and not find_all_dates(lines[i + 1]) else ""
        ctx = (own + " " + nxt).strip()
        if len(re.sub(r"[\d./\s]+|[A-Za-zΑ-Ωα-ωΆ-Ώά-ώ]+ \d{4}", "", ctx)) < 4 and i > 0 and not find_all_dates(lines[i - 1]):
            ctx = lines[i - 1] + " " + ctx
        ctx = re.sub(r"\s+", " ", ctx)[:400]
        out.append({"date": dates[0].isoformat(), "text": ctx, "kind": classify_event(ctx)})
    # dedupe by (date, kind)
    seen, res = set(), []
    for e in out:
        k = (e["date"], e["kind"])
        if k in seen:
            continue
        seen.add(k)
        res.append(e)
    return res


def extract_file_number(page_text: str) -> str:
    m = re.search(r"\b(23\.\d{2}\.\d{3}\.\d{3}-\d{4})\b", page_text)
    return m.group(1) if m else ""


def extract_purpose(page_text: str) -> str:
    m = re.search(r"Σκοπ[όο]ς\s+(?:του|της)\s+(?:προτεινόμενου\s+)?(?:νομοσχεδίου|πρότασης\s+νόμου|παρόντος|κανονισμ\w+)[^\n]*", page_text)
    if m:
        return m.group(0).strip()
    m = re.search(r"Σκοπ[όο]ς[^\n]{20,}", page_text)
    return m.group(0).strip() if m else ""


class NomoplatformCollector:
    def __init__(self, http: Http, window: Window, fetch_pages: bool = True, max_pages: int = 60):
        self.http = http
        self.window = window
        self.fetch_pages = fetch_pages
        self.max_pages = max_pages
        self.terms: dict[str, dict[int, str]] = {}
        self.status: dict[str, dict] = {}
        self.blocked = False

    # ---- API helpers ----------------------------------------------------
    def _api(self, path: str, params: dict) -> Optional[list]:
        url = API + path
        res = self.http.get(url, params=params)
        if not res.ok:
            self.status.setdefault("api_failures", []).append({"url": res.url, "reason": res.reason, "status": res.status})
            if res.reason in ("cloudflare", "proxy_denied"):
                self.blocked = True
            return None
        try:
            data = res.json()
        except Exception:
            self.status.setdefault("api_failures", []).append({"url": res.url, "reason": "bad_json"})
            return None
        if isinstance(data, dict) and data.get("code"):
            # e.g. rest_post_invalid_page_number – end of pagination
            return []
        return data

    def _paged(self, path: str, params: dict, limit_pages: int = 10) -> list:
        out: list = []
        for page in range(1, limit_pages + 1):
            data = self._api(path, {**params, "per_page": 100, "page": page})
            if data is None:
                break
            out += data
            if len(data) < 100:
                break
        return out

    def load_terms(self) -> None:
        for tax in TAXONOMIES:
            data = self._paged(tax, {"_fields": "id,name,slug"}, limit_pages=8)
            self.terms[tax] = {int(t["id"]): htmlmod.unescape(t["name"]) for t in data if "id" in t}
        self.status["terms"] = {k: len(v) for k, v in self.terms.items()}

    def term_names(self, tax: str, ids: list[int]) -> list[str]:
        m = self.terms.get(tax, {})
        return [m.get(int(i), f"#{i}") for i in ids or []]

    # ---- bills ----------------------------------------------------------
    def bills_candidates(self) -> list[dict]:
        # anything created or modified in the window (modified_after needs WP>=5.7; fall back to after)
        w = self.window
        seen: dict[int, dict] = {}
        for params in ({"modified_after": w.iso_after, "orderby": "modified", "order": "desc", "_fields": BILL_FIELDS},
                       {"after": w.iso_after, "before": w.iso_before, "orderby": "date", "order": "desc", "_fields": BILL_FIELDS}):
            for b in self._paged("bills", params, limit_pages=5):
                seen[int(b["id"])] = b
        cands = []
        for b in seen.values():
            d = dt.datetime.fromisoformat(b["date"][:19]).date()
            m = dt.datetime.fromisoformat(b["modified"][:19]).date()
            if w.contains(d) or w.contains(m) or m >= w.start:
                cands.append(b)
        self.status["bills_candidates"] = len(cands)
        return cands

    def bill_item(self, b: dict, page_text: str = "") -> Optional[Item]:
        w = self.window
        title = htmlmod.unescape(BeautifulSoup(b["title"]["rendered"], "lxml").get_text(" ", strip=True))
        purpose = html_to_text(b.get("content", {}).get("rendered", ""))
        status_names = self.term_names("bill-status", b.get("bill-status", []))
        type_names = self.term_names("type-of-legislation", b.get("type-of-legislation", []))
        theme_ids = [int(x) for x in b.get("thematic-unit", [])]
        theme_names = self.term_names("thematic-unit", theme_ids)
        ministry = self.term_names("competent-ministry", b.get("competent-ministry", []))
        created = dt.datetime.fromisoformat(b["date"][:19]).date()
        modified = dt.datetime.fromisoformat(b["modified"][:19]).date()

        timeline = extract_timeline(page_text) if page_text else []
        in_window = [e for e in timeline if w.contains(dt.date.fromisoformat(e["date"]))]
        if page_text and timeline and not in_window:
            return None  # the page dates every step; nothing happened in the window
        if in_window:
            ev = sorted(in_window, key=lambda e: e["date"])[-1]
            date, date_kind, event_text = dt.date.fromisoformat(ev["date"]), ev["kind"], ev["text"]
        elif w.contains(created):
            date, date_kind, event_text = created, "submitted", ""
        elif w.contains(modified):
            date, date_kind, event_text = modified, "modified", ""
        else:
            return None
        status = ", ".join(status_names)
        if date_kind == "modified" and re.search(r"ψηφ", strip_accents(status).lower()):
            date_kind = "voted"
        item = Item(
            id=f"bill-{b['id']}", contour="in_progress", kind="bill", source="nomoplatform",
            source_label="Nomoplatform / Βουλή των Αντιπροσώπων", date=date, date_kind=date_kind,
            title_el=title, number=("Αρ. Φακ. " + extract_file_number(page_text)) if extract_file_number(page_text) else "", url=b.get("link", ""),
            verbatim={"purpose": purpose, "event": event_text, "status": status, "type": ", ".join(type_names)},
            status=status,
            extra={"thematic_ids": theme_ids, "thematic": theme_names, "ministry": ministry, "created": created.isoformat(),
                   "modified": modified.isoformat(), "timeline": timeline},
        )
        if date_kind in ("voted",) and re.search(r"υπερψηφ", strip_accents(status + " " + event_text).lower()):
            item.contour = "adopted"   # voted by plenary → goes to "принято" even before the Gazette
            item.extra["adopted_by_vote"] = True
        return item

    def collect_bills(self) -> list[Item]:
        items = []
        pages_fetched = 0
        for b in self.bills_candidates():
            page_text = ""
            if self.fetch_pages and pages_fetched < self.max_pages and b.get("link"):
                res = self.http.get(b["link"])
                pages_fetched += 1
                if res.ok:
                    page_text = html_to_text(res.text)
                elif res.reason in ("cloudflare", "proxy_denied"):
                    self.blocked = True
                    self.fetch_pages = False   # stop hammering; API data is still usable
            it = self.bill_item(b, page_text)
            if it:
                items.append(it)
        self.status["bill_pages_fetched"] = pages_fetched
        return items

    # ---- news posts -----------------------------------------------------
    def collect_posts(self) -> list[Item]:
        w = self.window
        items = []
        cats = [CAT_PLENARY, CAT_PROGRAMME] + list(CAT_COMMITTEES)
        posts = self._paged("posts", {"after": w.iso_after, "before": w.iso_before, "categories": ",".join(map(str, cats)),
                                      "orderby": "date", "order": "desc", "_fields": POST_FIELDS}, limit_pages=3)
        for p in posts:
            cat_ids = [int(c) for c in p.get("categories", [])]
            if CAT_PLENARY in cat_ids:
                kind, label = "plenary", "Nomoplatform — Αποφάσεις Ολομέλειας"
            elif CAT_PROGRAMME in cat_ids:
                kind, label = "committee", "Nomoplatform — Πρόγραμμα Επιτροπών"
            else:
                names = [CAT_COMMITTEES[c] for c in cat_ids if c in CAT_COMMITTEES]
                kind, label = "committee", "Nomoplatform — Επιτροπή " + "/".join(names)
            title = htmlmod.unescape(BeautifulSoup(p["title"]["rendered"], "lxml").get_text(" ", strip=True))
            body = html_to_text(p.get("content", {}).get("rendered", ""))
            items.append(Item(
                id=f"nomo-post-{p['id']}", contour="in_progress", kind=kind, source="nomoplatform",
                source_label=label, date=dt.datetime.fromisoformat(p["date"][:19]).date(),
                date_kind="published", title_el=title, url=p.get("link", ""),
                verbatim={"body": body[:12000]}, extra={"categories": cat_ids},
            ))
        self.status["posts"] = len(items)
        return items

    def collect(self) -> list[Item]:
        self.load_terms()
        if self.blocked and not self.terms.get("bill-status"):
            self.status["blocked"] = True
            return []
        items = self.collect_bills() + self.collect_posts()
        if self.blocked:
            self.status["blocked_partially"] = True
        return items

    # ---- fallback ingestion --------------------------------------------
    def ingest_json(self, bills_json: list[dict], posts_json: list[dict], pages: dict[str, str]) -> list[Item]:
        """Build items from JSON/text that Claude fetched by other means (WebFetch)."""
        items = []
        for b in bills_json:
            it = self.bill_item(b, pages.get(b.get("link", ""), ""))
            if it:
                items.append(it)
        # posts share the same shape as the API
        w = self.window
        for p in posts_json:
            d = dt.datetime.fromisoformat(p["date"][:19]).date()
            if not w.contains(d):
                continue
            cat_ids = [int(c) for c in p.get("categories", [])]
            kind = "plenary" if CAT_PLENARY in cat_ids else "committee"
            title = htmlmod.unescape(BeautifulSoup(p["title"]["rendered"], "lxml").get_text(" ", strip=True))
            items.append(Item(id=f"nomo-post-{p['id']}", contour="in_progress", kind=kind, source="nomoplatform",
                              source_label="Nomoplatform", date=d, date_kind="published", title_el=title,
                              url=p.get("link", ""), verbatim={"body": html_to_text(p.get("content", {}).get("rendered", ""))[:12000]}))
        return items
