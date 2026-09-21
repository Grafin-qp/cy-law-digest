#!/usr/bin/env python3
"""Collect everything the Opiniq Cyprus law digest needs for one reporting
window, deterministically, and write a skeleton the model turns into prose.

    python scripts/digest_collect.py --week previous            # default: previous ISO week (Mon–Sun)
    python scripts/digest_collect.py --from 2026-09-07 --to 2026-09-13
    python scripts/digest_collect.py --days 8                   # rolling window ending today
    python scripts/digest_collect.py --plan                     # print the URLs that would be fetched

Outputs (in --out/<window>/):
    items.json      kept items (relevant) + other_laws (all laws of the week, one line each)
    all_items.json  everything collected, before the relevance filter – for audit
    status.json     per-source status (ok / blocked reason / counts) – read this first
    skeleton.md     the digest skeleton: sections, verbatim fields, links – the model writes from this
    raw/            cached HTTP responses (re-run with --offline to reuse them)

Exit code 0 even when sources fail: failures are data (status.json), not crashes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cylaw_digest import window as W                     # noqa: E402
from cylaw_digest.http import Http                       # noqa: E402
from cylaw_digest.model import Item                      # noqa: E402
from cylaw_digest.relevance import classify, AREA_EN     # noqa: E402
from cylaw_digest.greekdates import strip_accents        # noqa: E402

SOURCES = ("gazette", "cylaw", "cylawkdp", "nomoplatform", "govcy", "registrar", "cbc")


def norm_title(t: str) -> str:
    t = strip_accents(t or "").lower()
    t = re.sub(r"[^a-zα-ω0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def norm_law_number(n: str) -> str:
    return re.sub(r"\s+", "", n.replace("Ν.", "").replace("N.", "").replace("Ι", "I")).upper()


# ----------------------------------------------------------------------------
def run_sources(args, http: Http, win: W.Window) -> tuple[list[Item], dict]:
    items: list[Item] = []
    import platform
    status: dict = {"window": {"start": win.start.isoformat(), "end": win.end.isoformat()},
                    "generated": dt.datetime.now().isoformat(timespec="seconds"), "host": platform.node(), "sources": {}}

    def run(name, factory):
        if name not in args.sources:
            status["sources"][name] = {"skipped": True}
            return
        try:
            c = factory()
            got = c.collect()
            for it in got:
                it.extra.setdefault("collector", name)
            items.extend(got)
            st = {"items": len(got), **getattr(c, "status", {})}
            roll_up(st)
            status["sources"][name] = st
            logging.info("%s: %d items%s", name, len(got), f" (BLOCKED: {st['reason']})" if st.get("reason") else "")
        except Exception as e:  # a broken source must not kill the digest
            logging.exception("%s failed", name)
            status["sources"][name] = {"items": 0, "error": f"{type(e).__name__}: {e}"}

    from cylaw_digest.gazette import GazetteCollector
    from cylaw_digest.cylaw import CylawCollector, CylawKdpCollector
    from cylaw_digest.nomoplatform import NomoplatformCollector
    from cylaw_digest.govcy import GovCyCollector
    from cylaw_digest.registrar import RegistrarCollector
    from cylaw_digest.cbc import CbcCollector

    run("gazette", lambda: GazetteCollector(http, win, apps=(16, 2, 3, 6) if not args.no_pdf else ()))
    run("cylaw", lambda: CylawCollector(http, win))
    run("cylawkdp", lambda: CylawKdpCollector(http, win, fetch_pdfs=not args.no_pdf))
    run("nomoplatform", lambda: NomoplatformCollector(http, win, fetch_pages=not args.no_bill_pages))
    run("govcy", lambda: GovCyCollector(http, win))
    run("registrar", lambda: RegistrarCollector(http, win))
    run("cbc", lambda: CbcCollector(http, win))
    status["http"] = http.stats
    return items, status


def roll_up(st: dict) -> None:
    """Collectors keep per-URL sub-statuses (gazette_app16, cylaw_index_2026, api_failures…).
    Lift a failure reason to the top level so the console summary and the skeleton header
    cannot show 'ok, 0 items' for a source that was in fact blocked."""
    if st.get("reason") or st.get("error"):
        return
    reasons: list[str] = []

    def walk(v):
        if isinstance(v, dict):
            if v.get("reason") and not v.get("ok", False):
                reasons.append(str(v["reason"]))
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk({k: v for k, v in st.items() if k != "items"})
    if reasons and st.get("items", 0) == 0:
        st["reason"] = max(set(reasons), key=reasons.count)
    elif reasons:
        st["partial"] = max(set(reasons), key=reasons.count)
    if st.get("blocked") and not st.get("reason"):
        st["reason"] = "cloudflare"
    if st.get("blocked_partially") and not st.get("partial"):
        st["partial"] = "cloudflare"


# ----------------------------------------------------------------------------
def merge_laws(items: list[Item]) -> list[Item]:
    """Gazette and CyLaw describe the same laws and Κ.Δ.Π.; keep one record per number,
    with CyLaw's per-act PDF as the primary link and the Gazette issue kept in extra."""
    by_num: dict[str, Item] = {}
    rest: list[Item] = []
    for it in items:
        if it.kind not in ("law", "kdp"):
            rest.append(it)
            continue
        key = it.kind + ":" + norm_law_number(it.number.replace("Κ.Δ.Π.", ""))
        cur = by_num.get(key)
        if cur is None:
            by_num[key] = it
            continue
        # merge: prefer cylaw link/title, gazette date if cylaw undated, union verbatim
        primary, other = (it, cur) if it.source == "cylaw" else (cur, it)
        primary.date = primary.date or other.date
        if not primary.title_el or (other.source == "cylaw" and other.title_el):
            primary.title_el = other.title_el or primary.title_el
        primary.verbatim = {**other.verbatim, **{k: v for k, v in primary.verbatim.items() if v}}
        primary.excerpt = primary.excerpt or other.excerpt
        primary.entry_into_force = primary.entry_into_force or other.entry_into_force
        primary.extra["gazette_issue_url"] = other.url if other.source == "gazette" else other.extra.get("gazette_issue_url", "")
        if len(other.extra.get("full_text", "")) > len(primary.extra.get("full_text", "")):
            primary.extra["full_text"] = other.extra["full_text"]
        primary.extra["also_in"] = sorted(set(primary.extra.get("also_in", [])) | {other.source})
        primary.warnings = sorted((set(primary.warnings) & set(other.warnings)) | {w for w in primary.warnings + other.warnings if w.startswith("index_date_typo")})
        by_num[key] = primary
    return list(by_num.values()) + rest


def dedupe_bills_vs_laws(items: list[Item]) -> list[Item]:
    law_titles = {norm_title(i.title_el) for i in items if i.kind == "law"}
    out = []
    for it in items:
        if it.kind == "bill" and it.extra.get("adopted_by_vote") and norm_title(it.title_el) in law_titles:
            it.extra["superseded_by_gazette"] = True
            continue
        out.append(it)
    return out


def classify_all(items: list[Item]) -> None:
    for it in items:
        if it.relevance and it.practice_areas:
            continue  # pre-classified (registrar)
        term_ids = set(it.extra.get("thematic_ids", []) or [])
        names = it.extra.get("thematic", []) or []
        title = it.title_el or it.title_en
        body_parts = [it.verbatim.get(k, "") for k in ("long_title", "parent_law", "purpose", "excerpt", "summary", "event")]
        body = "\n".join(p for p in body_parts if p)
        if it.kind in ("plenary", "committee"):
            body = it.verbatim.get("body", "")[:6000]
        elif it.kind == "announcement":
            body = (it.verbatim.get("excerpt", "") or it.verbatim.get("body", "")[:1500])
        r = classify(title, body, term_ids=term_ids, term_names=names,
                     title_weight_only=(it.kind == "announcement" and it.source == "cbc"))
        it.relevance, it.practice_areas, it.relevance_hits = r.score, r.areas, r.hits


SECTION_ORDER = {("adopted", "law"): 0, ("adopted", "kdp"): 1, ("adopted", "bill"): 2,
                 ("in_progress", "bill"): 3, ("in_progress", "plenary"): 4, ("in_progress", "committee"): 5,
                 ("regulator", "announcement"): 6, ("regulator", "circular"): 6, ("regulator", "guidance"): 6}


def sort_key(it: Item):
    return (SECTION_ORDER.get((it.contour, it.kind), 9), -(it.relevance), it.date or dt.date.min, it.number, it.title_el)


# ----------------------------------------------------------------------------
def write_skeleton(path: Path, win: W.Window, kept: list[Item], other_laws: list[Item], dropped: list[Item], status: dict) -> None:
    L: list[str] = []
    a = L.append
    a(f"# Skeleton — Cyprus law digest, window {win.start.strftime('%d.%m.%Y')} – {win.end.strftime('%d.%m.%Y')}")
    a(f"Generated {status['generated']} by digest_collect.py on {status.get('host', '?')}. Sources: " + "; ".join(
        f"{k}: {'skip' if v.get('skipped') else (v.get('error') or ('BLOCKED ' + str(v.get('reason')) if v.get('reason') else str(v.get('items', 0)) + ' items' + (' (partial: ' + str(v['partial']) + ')' if v.get('partial') else '')))}"
        for k, v in status["sources"].items()))
    a("")
    # coverage facts for the Verification block
    gz = status["sources"].get("gazette", {})
    cov = []
    for k, v in gz.items():
        if isinstance(v, dict) and v.get("label"):
            iss = ", ".join(f"No. {i['number']} ({i['date'][8:10]}.{i['date'][5:7]})" if i.get("date") else f"No. {i['number']}" for i in v.get("issues", []))
            cov.append(f"{v['label']}: {iss or 'no issue in window'} (live list up to {v.get('latest_listed')})")
    cy = status["sources"].get("cylaw", {})
    for k, v in cy.items():
        if isinstance(v, dict) and "checked_down_to" in v:
            cov.append(f"CyLaw {k.split('_')[-1]}: highest {v.get('highest')}, walked down to {v.get('checked_down_to')}")
    ck = status["sources"].get("cylawkdp", {})
    for k, v in ck.items():
        if isinstance(v, dict) and "in_window" in v:
            cov.append(f"CyLaw Κ.Δ.Π. index: latest {v.get('latest')}, {v['in_window']} in window (issues {', '.join(v.get('issues', []))})")
    if cov:
        a("Coverage: " + "; ".join(cov))
    a("Rules: write only from the fields below (verbatim = exact source wording). Invent nothing; an empty field means "
      "'not found' – say so or open the link / texts/<id>.txt.")
    a("")

    def block(it: Item, full: bool = True):
        title = it.title_el or it.title_en
        a(f"#### [{it.id}] {it.number + ' — ' if it.number else ''}{title}")
        a(f"- practice areas: {', '.join(AREA_EN[x] for x in it.practice_areas) or '—'} (score {it.relevance}; hits: {', '.join(it.relevance_hits[:4])})")
        d = it.date.strftime('%d.%m.%Y') if it.date else 'date not confirmed'
        a(f"- date / event: {d} — {it.date_kind}; source: {it.source_label}")
        if it.status:
            a(f"- status: {it.status}")
        a(f"- link: {it.url}" + (f"; PDF: {it.pdf_url}" if it.pdf_url and it.pdf_url != it.url else ""))
        if it.extra.get("gazette_issue_url"):
            a(f"- Gazette issue page: {it.extra['gazette_issue_url']}")
        if it.extra.get("department"):
            a(f"- department: {it.extra['department']}")
        if it.extra.get("text_file"):
            a(f"- full text of the act: {it.extra['text_file']}")
        if it.extra.get("thematic"):
            a(f"- Nomoplatform topics: {', '.join(it.extra['thematic'])}; type: {it.verbatim.get('type', '')}; ministry/author: {', '.join(it.extra.get('ministry', []))}")
        for k in ("long_title", "parent_law", "instrument", "promulgation_title"):
            if it.verbatim.get(k) and it.verbatim[k] != title:
                a(f"- {k} (verbatim): {it.verbatim[k]}")
        if it.entry_into_force:
            a(f"- entry into force (verbatim): {it.entry_into_force}")
        if it.verbatim.get("purpose"):
            a(f"- Σκοπός / purpose (verbatim): {it.verbatim['purpose'][:1500]}")
        if it.verbatim.get("event"):
            a(f"- event (verbatim): {it.verbatim['event']}")
        if it.extra.get("timeline"):
            tl = "; ".join(f"{e['date']} {e['kind']}" for e in it.extra["timeline"][:8])
            a(f"- timeline: {tl}")
        if full and it.excerpt:
            a(f"- text of the act (verbatim, opening): {it.excerpt[:1800]}")
        if full:
            for k in ("summary", "excerpt", "body"):
                if it.verbatim.get(k):
                    a(f"- {k} (verbatim): {it.verbatim[k][:2500]}")
        if it.warnings:
            a(f"- ⚠ parser warnings: {', '.join(it.warnings)}")
        a("")

    def section(title: str, sel):
        rows = [i for i in kept if sel(i)]
        a(f"## {title} ({len(rows)})")
        a("")
        if not rows:
            a("_no items in the window_")
            a("")
        for it in rows:
            block(it)

    section("A1. Enacted and published — laws (Επίσημη Εφημερίδα, Παρ. Ι)", lambda i: i.contour == "adopted" and i.kind == "law")
    section("A2. Enacted and published — Κ.Δ.Π. (regulations, orders, notices; Παρ. ΙΙΙ(Ι))", lambda i: i.contour == "adopted" and i.kind == "kdp")
    section("A3. Voted by the plenary (Ολομέλεια), not yet in the Gazette", lambda i: i.contour == "adopted" and i.kind == "bill")
    section("B1. In progress — bills and private members' bills (events of the week)", lambda i: i.contour == "in_progress" and i.kind == "bill")
    section("B2. In progress — plenary decisions and committee posts (Nomoplatform)", lambda i: i.contour == "in_progress" and i.kind in ("plenary", "committee"))
    section("C. Regulators and departments", lambda i: i.contour == "regulator")

    a(f"## D. Other laws of the week (outside the practice areas) — one line each ({len(other_laws)})")
    a("")
    for it in other_laws:
        d = it.date.strftime('%d.%m.%Y') if it.date else '?'
        a(f"- {it.number} — {it.title_el} ({d}) {it.url}")
    a("")
    a(f"## E. Dropped by the relevance filter — for review ({len(dropped)})")
    a("")
    by = {}
    for it in dropped:
        by.setdefault(it.source, []).append(it)
    for src, rows in by.items():
        a(f"- {src}: {len(rows)}")
        for it in rows[:40]:
            a(f"    - {(it.date.isoformat() if it.date else '?')} {it.kind} {it.number} {(it.title_el or it.title_en)[:110]}")
    path.write_text("\n".join(L), encoding="utf-8")


# ----------------------------------------------------------------------------
def webfetch_plan(win: W.Window) -> str:
    """Fallback for sandboxes whose egress policy blocks the Cyprus sites: the model fetches
    these URLs with its WebFetch tool using the given prompts and files the answers by hand
    (see references/fallback-webfetch.md)."""
    from cylaw_digest import gazette, cylaw, nomoplatform, govcy, registrar, cbc
    fmt = "DATE(YYYY-MM-DD) | NUMBER | TITLE (verbatim, original language) | URL"
    steps = [
        ("gazette laws (Παρ. Ι(Ι))", gazette.VIEW.format(app=16),
         f"List every row as: ISSUE_NUMBER | DATE | PAGES | LINK. Keep only dates between {win.start} and {win.end}."),
        ("gazette Κ.Δ.Π. (Παρ. ΙΙΙ(Ι))", gazette.VIEW.format(app=6),
         f"List every row as: ISSUE_NUMBER | DATE | PAGES | LINK. Keep only dates between {win.start} and {win.end}."),
        ("gazette issue → PDF", "<issue link from the previous step>",
         "Return the PDF link on the page verbatim. Then fetch the PDF itself with the prompt: 'List every act in this annex as: NUMBER | SHORT TITLE (the sentence after \"θα αναφέρεται ως\", verbatim) | ENTRY-INTO-FORCE clause verbatim if present'."),
        ("laws index (CyLII, UTF-8 – readable titles)", "https://www.cylii.org/cy/legis/arith",
         "List the LAST 12 entries of each part (I, II, III) as: NUMBER (e.g. Ν. 125(I)/2026) | TITLE verbatim. The PDF of law N is https://www.cylaw.org/nomoi/arith/<year>_<part>_<NNN>.pdf (three-digit)."),
        ("Κ.Δ.Π. index (CyLII, UTF-8 – title + Gazette issue/date in every line)", "https://www.cylii.org/cy/legis/kdp/arith",
         f"List every entry whose Gazette date lies between {win.start} and {win.end} (or whose Αρ. equals an issue of that week) as: ΚΔΠ NUMBER | TITLE verbatim | Αρ. | date. Dates occasionally have typos – trust the Αρ. The PDF of ΚΔΠ N is https://www.cylaw.org/KDP/data/<year>_1_<N>.pdf."),
        ("CyLII daily updates (cross-check what was added each day)", "https://www.cylii.org/updates?date=<YYYY-MM-DD>",
         "One call per day of the window. List every entry under Αριθμημένη Νομοθεσία and Κανονιστικές Διοικητικές Πράξεις verbatim with its link."),
        ("cylaw per-law PDF", f"{cylaw.BASE}/nomoi/arith/{win.end.year}_1_NNN.pdf",
         "Quote verbatim: the line 'Αριθμός NNNN <weekday>, <day> <month> <year>' (gazette issue and date), the title sentence ending in 'εκδίδεται με δημοσίευση', the caps long title, and articles 2–3 in full."),
        ("nomoplatform bills (changed in window)", nomoplatform.API + f"bills?modified_after={win.iso_after}&per_page=50&_fields=id,date,modified,link,title,bill-status,thematic-unit,type-of-legislation",
         "This is public JSON metadata. For EVERY element output one line: id | date | modified | title.rendered | bill-status ids | thematic-unit ids | link."),
        ("nomoplatform bill page", "<bill link>",
         "Quote verbatim: Αρ. Φακέλου, Στάδιο, the full Σκοπός paragraph, and every dated timeline entry as DATE | EVENT."),
        ("nomoplatform plenary decisions", nomoplatform.API + f"posts?after={win.iso_after}&before={win.iso_before}&categories=488&per_page=20&_fields=id,date,link,title,content",
         "For every element: date | title.rendered | link, then the plain text of content.rendered (verbatim, strip HTML)."),
        ("gov.cy announcements", govcy.API + f"?after={win.iso_after}&before={win.iso_before}&categories=182,183,254,218,188,217&per_page=100&_fields=id,date,link,title,excerpt",
         "This is public JSON. For EVERY element output one line: date | title.rendered | link | excerpt (plain text). Do not skip elements."),
        ("registrar of companies news", registrar.NEWS,
         f"List every news item as: DATE | TITLE | LINK | SUMMARY. Keep only dates between {win.start} and {win.end}."),
        ("central bank announcements", cbc.ANNOUNCEMENTS,
         f"List every announcement dated between {win.start} and {win.end} as: DATE | TITLE | LINK."),
    ]
    out = [f"WebFetch fallback plan for window {win.start}..{win.end} (line format for lists: {fmt})",
           "Known limits of the fetch tool: mof.gov.cy (Gazette) fails TLS verification and www.gov.cy answers 403 – "
           "those sources cannot be verified in this mode; say so in the digest. Budget ~40 calls: CyLaw index+PDFs, "
           "Nomoplatform bills API + ≤8 bill pages + plenary posts, Registrar, CBC – in this order. See references/fallback-webfetch.md.", ""]
    for name, url, prompt in steps:
        out += [f"### {name}", f"URL: {url}", f"PROMPT: {prompt}", ""]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--week", choices=["previous", "current"], help="calendar window (default: previous)")
    g.add_argument("--days", type=int, help="rolling window of N days ending today")
    g.add_argument("--from", dest="from_", help="window start YYYY-MM-DD (with --to)")
    ap.add_argument("--to", help="window end YYYY-MM-DD")
    ap.add_argument("--today", help="override 'today' (YYYY-MM-DD) – for tests and re-runs")
    ap.add_argument("--out", default="~/digest_out", help="output directory (default: ~/digest_out; never inside the skill folder – it may be read-only)")
    ap.add_argument("--sources", default=",".join(SOURCES), help="comma list of sources to run")
    ap.add_argument("--no-pdf", action="store_true", help="skip Gazette PDFs (CyLaw still fetches per-law PDFs)")
    ap.add_argument("--no-bill-pages", action="store_true", help="do not fetch Nomoplatform bill pages (API only)")
    ap.add_argument("--all-areas", action="store_true", help="keep items with relevance 0 too")
    ap.add_argument("--min-relevance", type=int, default=1)
    ap.add_argument("--cache-dir", help="extra read-only HTTP cache (e.g. tests/offline_cache or a previous run's raw/)")
    ap.add_argument("--offline", action="store_true", help="never touch the network: serve only from --cache-dir / raw/ (tests, re-runs)")
    ap.add_argument("--insecure-hosts", default="", help="comma list of hosts to fetch without TLS verification (opt-in)")
    ap.add_argument("--plan", action="store_true", help="print the fetch plan and exit")
    ap.add_argument("--webfetch-plan", action="store_true",
                    help="print the fallback plan (URL + extraction prompt per source) for environments where scripts cannot reach the sites")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    args.sources = [s.strip() for s in args.sources.split(",") if s.strip()]

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    today = dt.date.fromisoformat(args.today) if args.today else W.today_cy()
    if args.from_ and args.to:
        win = W.explicit(args.from_, args.to)
    elif args.days:
        win = W.last_days(args.days, today)
    elif args.week == "current":
        win = W.current_week(today)
    else:
        win = W.previous_week(today)

    out_dir = Path(args.out).expanduser() / win.label
    raw_dir = out_dir / "raw"

    if args.plan:
        from cylaw_digest import gazette, cylaw, nomoplatform, govcy, registrar, cbc
        print(f"window: {win.start} .. {win.end}")
        for app in (16, 2, 3, 6):
            print("gazette:", gazette.VIEW.format(app=app))
        for y in sorted({win.start.year, win.end.year}):
            print("cylaw:", cylaw.ARITH_INDEX.format(year=y), "→ per-law PDFs, walking down from the highest number")
        for y in sorted({win.start.year, win.end.year}):
            print("cylawkdp:", cylaw.KDP_INDEX.format(year=y), "→ per-act PDFs /KDP/data/<year>_1_<n>.pdf for entries dated in the window")
        print("nomoplatform:", nomoplatform.API + f"bills?modified_after={win.iso_after}&per_page=100&_fields={nomoplatform.BILL_FIELDS}")
        print("nomoplatform:", nomoplatform.API + f"posts?after={win.iso_after}&before={win.iso_before}&categories=488,309,484,473,477,480,479&per_page=100")
        print("govcy:", govcy.API + f"?after={win.iso_after}&before={win.iso_before}&categories=182,183,254,218,188,217&per_page=100")
        print("registrar:", registrar.NEWS)
        print("cbc:", cbc.ANNOUNCEMENTS)
        return 0

    if args.webfetch_plan:
        print(webfetch_plan(win))
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    http = Http(raw_dir=raw_dir, insecure_hosts={h.strip() for h in args.insecure_hosts.split(",") if h.strip()},
                cache_dir=Path(args.cache_dir) if args.cache_dir else None, offline=args.offline)
    items, status = run_sources(args, http, win)

    items = merge_laws(items)
    items = dedupe_bills_vs_laws(items)
    classify_all(items)
    items.sort(key=sort_key)

    min_rel = 0 if args.all_areas else args.min_relevance
    kept = [i for i in items if i.relevance >= min_rel]
    dropped = [i for i in items if i.relevance < min_rel]
    other_laws = [i for i in dropped if i.kind == "law" and i.extra.get("part", "I") == "I"]

    # full act texts go to texts/<id>.txt (the model reads them only when the excerpt is not enough)
    texts_dir = out_dir / "texts"
    for it in items:
        full = it.extra.pop("full_text", "")
        if full:
            texts_dir.mkdir(exist_ok=True)
            fname = re.sub(r"[^A-Za-z0-9_.-]+", "_", it.id) + ".txt"
            (texts_dir / fname).write_text(full, encoding="utf-8")
            it.extra["text_file"] = str(Path("texts") / fname)

    status["counts"] = {"collected": len(items), "kept": len(kept), "dropped": len(dropped), "other_laws": len(other_laws)}
    (out_dir / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "all_items.json").write_text(json.dumps([i.to_json() for i in items], ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "items.json").write_text(json.dumps({"window": status["window"], "items": [i.to_json() for i in kept],
                                                    "other_laws": [i.to_json() for i in other_laws]}, ensure_ascii=False, indent=1), encoding="utf-8")
    write_skeleton(out_dir / "skeleton.md", win, kept, other_laws, dropped, status)

    print(f"window {win.start}..{win.end}: collected {len(items)}, kept {len(kept)}, other laws {len(other_laws)}, dropped {len(dropped)}")
    for k, v in status["sources"].items():
        if v.get("skipped"):
            flag = "SKIP"
        elif v.get("error") or v.get("reason"):
            flag = "BLOCKED " + str(v.get("error") or v.get("reason"))
        elif v.get("partial"):
            flag = "ok (partial: " + str(v["partial"]) + ")"
        else:
            flag = "ok"
        print(f"  {k:13s} {flag:40s} items={v.get('items', 0)}")
    print(f"→ {out_dir / 'skeleton.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
