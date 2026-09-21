#!/usr/bin/env python3
"""Build the offline fixture set for the self-test.

Creates realistic copies of every page/JSON/PDF the collectors request for the
test window 2026-09-07..2026-09-13 and stores them in an HTTP cache directory
under the same keys `cylaw_digest.http.Http` uses, so
`digest_collect.py --offline` runs the whole pipeline without network.

Page structures mirror the live sites as observed in September 2026 (see
references/sources.md). PDFs are rendered from the *.txt fixtures with
reportlab so that pdftotext sees line-oriented text similar to the Gazette's.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from cylaw_digest.http import Http  # noqa: E402
from cylaw_digest import gazette, cylaw, nomoplatform, govcy, registrar, cbc  # noqa: E402

HERE = Path(__file__).resolve().parent
FX = HERE / "fixtures"
CACHE = HERE / "offline_cache"
WIN_AFTER, WIN_BEFORE = "2026-09-07T00:00:00", "2026-09-13T23:59:59"


def put(url: str, content: bytes) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / (Http.cache_key(url) + ".bin")).write_bytes(content)
    with (CACHE / "index.txt").open("a", encoding="utf-8") as f:
        f.write(f"{Http.cache_key(url)}\t{url}\n")


def text_to_pdf(txt: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    import io
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",          # Debian/Ubuntu (fonts-dejavu-core)
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",                   # Fedora
        "/usr/share/fonts/TTF/DejaVuSans.ttf",                      # Arch
        "/opt/homebrew/share/fonts/DejaVuSans.ttf",                 # macOS (brew)
        "/Library/Fonts/DejaVuSans.ttf", str(Path.home() / "Library/Fonts/DejaVuSans.ttf"),
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",    # macOS stock Unicode font
    ]
    font_path = next((c for c in candidates if Path(c).exists()), None)
    if not font_path:
        sys.exit("build_fixtures: no Unicode TTF font found for the PDF fixtures "
                 "(install fonts-dejavu-core on Debian/Ubuntu, or DejaVuSans.ttf elsewhere)")
    pdfmetrics.registerFont(TTFont("DejaVu", font_path))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 50
    c.setFont("DejaVu", 9)
    for line in txt.splitlines():
        if y < 50:
            c.showPage()
            c.setFont("DejaVu", 9)
            y = h - 50
        c.drawString(40, y, line)
        y -= 12
    c.showPage()
    c.save()
    return buf.getvalue()


def cylaw_index_html() -> bytes:
    entries_I = [(1, "Ο περί Καθορισμού Προτύπων Χρηματοοικονομικής Πληροφόρησης Νόμος του 2026"),
                 (2, "Ο περί Εταιρειών (Τροποποιητικός) Νόμος του 2026"),
                 (3, "Ο περί Ακίνητης Ιδιοκτησίας (Διακατοχή, Εγγραφή και Εκτίμηση) (Τροποποιητικός) Νόμος του 2026"),
                 (120, "Ο περί Φόρων Κατανάλωσης (Τροποποιητικός) (Αρ. 2) Νόμος του 2026"),
                 (124, "Ο περί Κυπριακού Οργανισμού Ανάπτυξης Επιχειρήσεων Νόμος του 2026"),
                 (125, "Ο περί Φορολογίας του Εισοδήματος (Τροποποιητικός) (Αρ. 3) Νόμος του 2026"),
                 (126, "Ο περί Θήρας και Προστασίας Άγριων Πτηνών (Τροποποιητικός) Νόμος του 2026")]
    entries_II = [(41, "Ο περί Προϋπολογισμού του Γραφείου Επιτρόπου για τη Ρύθμιση Ηλεκτρονικών Επικοινωνιών και Ταχυδρομείων του 2026 Νόμος του 2026"),
                  (42, "Ο περί Προϋπολογισμού του Συμβουλίου της Ιατρικώς Υποβοηθούμενης Αναπαραγωγής του 2026 Νόμος του 2026")]
    entries_III = [(6, "Ο περί της Συμφωνίας μεταξύ της Κυβέρνησης της Κυπριακής Δημοκρατίας και της Κυβέρνησης της Δημοκρατίας της Σερβίας σχετικά με το Καθεστώς των Δυνάμεων τους (Κυρωτικός) Νόμος του 2026")]

    def part(n, roman, entries):
        lis = "\n".join(
            f'\t\t\t\t\t<li>\n\t\t\t\t\t\t<p>\n\t\t\t\t\t\t\t[pdf] <a href="/nomoi/arith/2026_{n}_{seq:03d}.pdf">Ν. {seq}({roman})/2026 - {title}</a>\n\t\t\t\t\t\t</p>\n\t\t\t\t\t</li>'
            for seq, title in entries)
        return f"\t\t\t<li>\n\t\t\t\t<p>\n\t\t\t\t\t<b>Μέρος {n}</b>\n\t\t\t\t</p>\n\t\t\t\t<ul>\n{lis}\n\t\t\t\t</ul>\n\t\t\t</li>"

    html = ("<html>\n\t\t<head>\n\t\t\t<meta http-equiv=Content-Type content=\"text/html; charset=windows-1253\">\n"
            "\t\t\t<title>Πίνακας Κυπριακής Αριθμημένης Νομοθεσίας για το έτος 2026</title>\n\t\t</head>\n\t\t<body>\n"
            "\t\t<font size=\"-1\"><a href=\"/nomoi/index.html\">Κατάλογος Ενοποιημένης Νομοθεσίας</a> <a href=\"/nomoi/arith_index.html\">Κατάλογος Αριθμημένης Νομοθεσίας</a></font>\n"
            "\t\t<form method=\"get\" action=\"/cgi-bin/nomoi/findlaw.pl\"><input name=\"title\"/></form>\n\t\t<hr size=\"1\"/>\n"
            "\t\t<p>\n\t\t\t<b>Πίνακας Κυπριακής Αριθμημένης Νομοθεσίας για το έτος 2026</b>\n\t\t</p>\n\t\t<ul>\n"
            + part(1, "I", entries_I) + "\n" + part(2, "II", entries_II) + "\n" + part(3, "III", entries_III) +
            "\n\t\t</ul>\n\t\t<font size=\"-1\"><a href=\"/index.html\">cylaw.org</a>: Από το ΚΙΝOΠ/CyLii για τον <a href=\"http://www.cyprusbarassociation.org/\">Παγκύπριο Δικηγορικό Σύλλογο</a></font>\n\t</body>\n</html>")
    return html.encode("windows-1253")


def cylaw_kdp_index_html() -> bytes:
    rows = [
        (325, "Γνωστοποίηση σύμφωνα με το άρθρο 60 δυνάμει του περί Σχολών Τριτοβάθμιας Εκπαίδευσης Νόμου", "6042", "2078", "28/8/2026"),
        (326, "Το περί Τροποποίησης των Παραρτημάτων των περί Μελιού Κανονισμών, Διάταγμα του 2026", "6043", "2081", "4/9/2026"),
        (327, "Το περί Οδικής Ασφάλειας (Ζώνες Ασφαλείας) Διάταγμα του 2026", "6044", "2083", "7/9/2026"),
        (328, "Το περί Ασφάλειας και Υγείας στην Εργασία (Καθορισμός Τελών για την υποβολή Γνωστοποίησης εγκαταστάσεων υγρών πετρελαιοειδών) Διάταγμα του 2026", "6045", "2087", "11/6/2026"),
        (329, "Γνωστοποίηση δυνάμει του άρθρου 5 του περί Ρύθμισης Ληξιπρόθεσμων Κοινωνικών Εισφορών Νόμου", "6045", "2088", "11/9/2026"),
        (330, "Το περί Ελέγχου της Ρύπανσης της Ατμόσφαιρας (Καθορισμός Γενικών Όρων Λειτουργίας για Εγκαταστάσεις Επεξεργασίας Ξυλείας) Διάταγμα του 2026", "6045", "2089", "11/9/2026"),
        (331, "Το περί Φόρου Προστιθέμενης Αξίας (Τροποποίηση του Πέμπτου Παραρτήματος) Διάταγμα του 2026", "6045", "2090", "11/9/2026"),
    ]
    lis = "\n".join(f'\t\t\t<li>\n\t\t\t\t<p>\n\t\t\t\t[pdf] <a href="/KDP/data/2026_1_{n}.pdf">ΚΔΠ&nbsp;{n}/2026, {t}, E.E. Παρ.ΙΙΙ(1), Αρ. {iss}, Σελ. {pg}, {d}</a></p>\n\t\t\t</li>'
                    for n, t, iss, pg, d in rows)
    html = ("<html>\n\t<head>\n\t\t<meta http-equiv=Content-Type content=\"text/html; charset=windows-1253\">\n"
            "\t\t<title>Πίνακας Κανονιστικών Διοικητικών Πράξεων για το έτος 2026</title>\n\t</head>\n\t<body>\n"
            "\t\t<font size=\"-1\"><a href=\"/KDP/index.html\">Κατάλογος Κανονιστικών Διοικητικών Πράξεων</a></font>\n\t\t<ul>\n"
            + lis + "\n\t\t</ul>\n\t</body>\n</html>")
    return html.encode("windows-1253")


def gazette_listing(app: int, rows: list[tuple[str, str, str, str]]) -> bytes:
    trs = "\n".join(
        f'<tr valign="top"><td nowrap><img width="16" height="1" src="/icons/ecblank.gif" border="0" alt=""><tr>'
        f'<td><a href="/mof/gpo/gazette.nsf/All/{unid}?OpenDocument">{num}</a></td>'
        f'<td><a href="/mof/gpo/gazette.nsf/All/{unid}?OpenDocument">{date}</a></td>'
        f'<td><a href="/mof/gpo/gazette.nsf/All/{unid}?OpenDocument">{pages}</a><br/></td></tr></td></tr>\n'
        for num, date, pages, unid in rows)
    html = (f'<html><head><meta charset="utf-8"><title>Παραρτήματα</title></head><body>'
            f'<a href="../dmlgaz_app_gr/dmlgaz_app_gr?OpenDocument">Παραρτήματα</a>'
            f'<table><tr><th><a href=./dmlgaz_appsw_gr?OpenDocument&OpenView&Count=1000&cp=11&app={app}>Ταξινόμηση - Τεύχος ↓ </a></th>'
            f'<th><a href=./dmlgaz_appsw_gr?OpenDocument&OpenView&Count=1000&cp=21&app={app}>Ταξινόμηση - Ημερομηνία</a></th><th>Σελίδες</th></tr>'
            f'<p><table border="0" cellpadding="2" cellspacing="0">\n{trs}</table></table></body></html>')
    return html.encode("utf-8")


def gazette_issue_page(num: str, pages: str, date: str, annex_title: str, unid: str, filename: str) -> bytes:
    html = (f'<html><head><meta charset="utf-8"><title>{num} - {annex_title}</title></head><body>'
            f'<h1>Τεύχος : {num} - {annex_title}</h1><p>Αριθμός Εφημερίδας: {num}</p><p>Σελίδες: {pages}</p>'
            f'<p>Ημερομηνία: {date}</p><p>{annex_title}:</p>'
            f'<p><a href="../{unid}/$file/{filename}">{filename}</a> (Μέγεθος Αρχείου: 771.59Kb)</p></body></html>')
    return html.encode("utf-8")


def build():
    if CACHE.exists():
        for p in CACHE.iterdir():
            p.unlink()

    # --- CyLaw ---------------------------------------------------------
    put(cylaw.ARITH_INDEX.format(year=2026), cylaw_index_html())
    for n in (120, 124, 125, 126):
        put(f"{cylaw.BASE}/nomoi/arith/2026_1_{n:03d}.pdf", text_to_pdf((FX / f"law_{n}.txt").read_text(encoding="utf-8")))
    # parts II/III: a budget law (undated fixture? – give it a real header far in the past so the walk stops)
    put(f"{cylaw.BASE}/nomoi/arith/2026_2_042.pdf", text_to_pdf(
        "N. 42(II)/2026\nΕΠΙΣΗΜΗ ΕΦΗΜΕΡΙΔΑ\nΠΑΡΑΡΤΗΜΑ ΠΡΩΤΟ\nΝΟΜΟΘΕΣΙΑ - ΜΕΡΟΣ ΙΙ\nΑριθμός 4555 Παρασκευή, 17 Ιουλίου 2026 887\n"
        "Ο περί Προϋπολογισμού του Συμβουλίου της Ιατρικώς Υποβοηθούμενης Αναπαραγωγής του 2026 Νόμος του 2026 εκδίδεται με δημοσίευση\n"
        "Αριθμός 42(ΙΙ) του 2026\nΝΟΜΟΣ ΠΟΥ ΠΡΟΝΟΕΙ ΓΙΑ ΤΟΝ ΠΡΟΫΠΟΛΟΓΙΣΜΟ\n1. Ο παρών Νόμος θα αναφέρεται ως ο περί Προϋπολογισμού Νόμος του 2026.\n"))
    put(f"{cylaw.BASE}/nomoi/arith/2026_2_041.pdf", text_to_pdf(
        "N. 41(II)/2026\nΑριθμός 4555 Παρασκευή, 17 Ιουλίου 2026 880\nΟ περί Προϋπολογισμού Νόμος του 2026 εκδίδεται με δημοσίευση\nΑριθμός 41(ΙΙ) του 2026\n"))
    put(f"{cylaw.BASE}/nomoi/arith/2026_3_006.pdf", text_to_pdf(
        "N. 6(III)/2026\nΑριθμός 4319 Παρασκευή, 24 Ιουλίου 2026 199\nΟ περί της Συμφωνίας (Κυρωτικός) Νόμος του 2026 εκδίδεται με δημοσίευση\nΑριθμός 6(ΙΙΙ) του 2026\n"))

    # --- CyLaw Κ.Δ.Π. index + per-act PDFs -------------------------------
    put(cylaw.KDP_INDEX.format(year=2026), cylaw_kdp_index_html())
    annex3 = (FX / "annex3_6045.txt").read_text(encoding="utf-8")
    import re as _re
    parts = _re.split(r"(?m)^(?=Ε\.Ε\. Παρ\. ΙΙΙ\(Ι\) Κ\.Δ\.Π\. \d+/2026)", annex3)
    for seg in parts:
        m = _re.search(r"Κ\.Δ\.Π\.\s*(\d+)/2026", seg)
        if m:
            put(f"{cylaw.BASE}/KDP/data/2026_1_{m.group(1)}.pdf", text_to_pdf(seg))
    put(f"{cylaw.BASE}/KDP/data/2026_1_327.pdf", text_to_pdf(
        "Κ.Δ.Π. 327/2026\nΕΠΙΣΗΜΗ ΕΦΗΜΕΡΙΔΑ\nΠΑΡΑΡΤΗΜΑ ΤΡΙΤΟ\nΜΕΡΟΣ Ι\nΑριθμός 6044 Δευτέρα, 7 Σεπτεμβρίου 2026 2083\nΑριθμός 327\n"
        "ΟΙ ΠΕΡΙ ΟΔΙΚΗΣ ΑΣΦΑΛΕΙΑΣ ΝΟΜΟΙ ΤΟΥ 1986 ΕΩΣ 2026\n______________\nΔιάταγμα δυνάμει του άρθρου 4\n"
        "1. Το παρόν Διάταγμα θα αναφέρεται ως το περί Οδικής Ασφάλειας (Ζώνες Ασφαλείας) Διάταγμα του 2026.\n2. Ο Πίνακας τροποποιείται.\n2084\n"))

    # --- Gazette -------------------------------------------------------
    unid_5096, unid_6045, unid_5095 = "AAAA1111BBBB2222CCCC3333DDDD4444", "4A7D42DCE00D6D38C2258E6F001E4045", "7D1AC5B1BA38E87DC2258E5A001C3FCC"
    put(gazette.VIEW.format(app=16), gazette_listing(16, [("5096", "11/09/2026", "1069-1072", unid_5096), ("5095", "21/08/2026", "1067", unid_5095),
                                                           ("5094", "24/07/2026", "1039-1065", "2625069EE0685A5EC2258E3E002AC275")]))
    put(gazette.VIEW.format(app=2), gazette_listing(2, [("4555", "17/07/2026", "887-899", "2E99552D41C14982C2258E37003569CB")]))
    put(gazette.VIEW.format(app=3), gazette_listing(3, [("4319", "24/07/2026", "199-224", "31271384ACFFBF52C2258E3E002B640B")]))
    put(gazette.VIEW.format(app=6), gazette_listing(6, [("6045", "11/09/2026", "2087-2120", unid_6045), ("6044", "07/09/2026", "2083-2085", "26BBD4EAEE7B4AD5C2258E6B0052CC30"),
                                                         ("6043", "04/09/2026", "2081-2082", "524451930248E73EC2258E68001E5F34")]))
    issue_url = lambda unid: f"{gazette.BASE}All/{unid}?OpenDocument"  # noqa: E731
    put(issue_url(unid_5096), gazette_issue_page("5096", "1069-1072", "11/09/2026", "ΠΑΡΑΡΤΗΜΑ ΠΡΩΤΟ - ΜΕΡΟΣ (Ι)", unid_5096, "5096 11 9 2026 PARARTIMA 1o MEROS I.pdf"))
    put(f"{gazette.BASE}{unid_5096}/$file/5096%2011%209%202026%20PARARTIMA%201o%20MEROS%20I.pdf", text_to_pdf((FX / "annex1_5096.txt").read_text(encoding="utf-8")))
    put(issue_url(unid_6045), gazette_issue_page("6045", "2087-2120", "11/09/2026", "ΠΑΡΑΡΤΗΜΑ ΤΡΙΤΟ - ΜΕΡΟΣ (Ι)", unid_6045, "6045 11 9 2026 PARARTIMA 3o MEROS I.pdf"))
    put(f"{gazette.BASE}{unid_6045}/$file/6045%2011%209%202026%20PARARTIMA%203o%20MEROS%20I.pdf", text_to_pdf((FX / "annex3_6045.txt").read_text(encoding="utf-8")))
    # 6044 (07/09) in window too: an issue page with a tiny PDF containing one irrelevant Κ.Δ.Π.
    unid_6044 = "26BBD4EAEE7B4AD5C2258E6B0052CC30"
    put(issue_url(unid_6044), gazette_issue_page("6044", "2083-2085", "07/09/2026", "ΠΑΡΑΡΤΗΜΑ ΤΡΙΤΟ - ΜΕΡΟΣ (Ι)", unid_6044, "6044 7 9 2026 PARARTIMA 3o MEROS I.pdf"))
    put(f"{gazette.BASE}{unid_6044}/$file/6044%207%209%202026%20PARARTIMA%203o%20MEROS%20I.pdf", text_to_pdf(
        "Κ.Δ.Π. 327/2026\nΕΠΙΣΗΜΗ ΕΦΗΜΕΡΙΔΑ\nΠΑΡΑΡΤΗΜΑ ΤΡΙΤΟ\nΜΕΡΟΣ Ι\nΑριθμός 6044 Δευτέρα, 7 Σεπτεμβρίου 2026 2083\nΑριθμός 327\n"
        "ΟΙ ΠΕΡΙ ΟΔΙΚΗΣ ΑΣΦΑΛΕΙΑΣ ΝΟΜΟΙ ΤΟΥ 1986 ΕΩΣ 2026\n______________\nΔιάταγμα δυνάμει του άρθρου 4\n"
        "1. Το παρόν Διάταγμα θα αναφέρεται ως το περί Οδικής Ασφάλειας (Ζώνες Ασφαλείας) Διάταγμα του 2026.\n2. Ο Πίνακας τροποποιείται.\n2084\n"))

    # --- Nomoplatform --------------------------------------------------
    api = nomoplatform.API
    terms = {
        "bill-status": [{"id": 238, "name": "Εκκρεμεί", "slug": "ekkremei"}, {"id": 239, "name": "Υπερψηφίστηκε", "slug": "yperpsifistike"},
                        {"id": 240, "name": "Καταψηφίστηκε", "slug": "katapsifistike"}, {"id": 242, "name": "Απόσυρση", "slug": "aposyrsi"}, {"id": 364, "name": "Αναβολή", "slug": "anavoli"}],
        "thematic-unit": [{"id": 301, "name": "Ακίνητα", "slug": "akinita"}, {"id": 332, "name": "Φορολογία", "slug": "forologia"}, {"id": 354, "name": "Οικοδομές", "slug": "oikodomes"},
                          {"id": 52, "name": "Τοπική Αυτοδιοίκηση", "slug": "topiki-aytodioikisi"}, {"id": 643, "name": "Αλλοδαποί", "slug": "allodapoi"}, {"id": 42, "name": "Παιδεία", "slug": "paideia"},
                          {"id": 369, "name": "Εταιρείες", "slug": "etaireies"}],
        "type-of-legislation": [{"id": 34, "name": "Νομοσχέδιο", "slug": "nomosxedio"}, {"id": 74, "name": "Πρόταση Νόμου", "slug": "protasi-nomou"}, {"id": 326, "name": "Κανονισμός", "slug": "kanonismos"}],
        "competent-ministry": [{"id": 111, "name": "Κοινοβουλευτική Επιτροπή Εσωτερικών", "slug": "epitropi-esoterikon"}, {"id": 610, "name": "Κοινοβουλευτική Επιτροπή Οικονομικών και Προϋπολογισμού", "slug": "oikonomikon"},
                               {"id": 755, "name": "Λίνος Ιωάννης Χατζηγεωργίου", "slug": "linos"}],
    }
    for tax, rows in terms.items():
        put(Http.full_url(f"{api}{tax}", {"_fields": "id,name,slug", "per_page": 100, "page": 1}), json.dumps(rows, ensure_ascii=False).encode("utf-8"))

    def bill(id_, date, modified, slug, title, purpose, status, ministry, themes, typ):
        return {"id": id_, "date": date, "date_gmt": date, "modified": modified, "modified_gmt": modified, "slug": slug, "status": "publish", "type": "bills",
                "link": f"https://www.nomoplatform.cy/bills/{slug}/", "title": {"rendered": title}, "content": {"rendered": f"<p>{purpose}</p>", "protected": False},
                "bill-status": [status], "competent-ministry": [ministry], "thematic-unit": themes, "type-of-legislation": [typ]}

    bills = [
        bill(62536, "2026-08-17T12:46:47", "2026-09-08T11:28:35", "o-peri-rythmiseos-odon-kai-oikodomon-tropopoiitikos-ar-2-nomos-tou-2026",
             "Ο περί Ρυθμίσεως Οδών και Οικοδομών (Τροποποιητικός) (Αρ. 2) Νόμος του 2026",
             "Σκοπός της πρότασης νόμου είναι η τροποποίηση του περί Ρυθμίσεως Οδών και Οικοδομών Νόμου, ώστε να καταστεί δυνατή η αποτελεσματική διαχείριση των κινδύνων για τη δημόσια ασφάλεια και υγεία από επικίνδυνες οικοδομές σε αστικές περιοχές.",
             238, 111, [354, 52], 74),
        bill(62540, "2026-07-14T10:00:00", "2026-09-10T09:00:00", "o-peri-forologias-kefalaiouchikon-kerdon-tropopoiitikos-nomos-tou-2026",
             "Ο περί Φορολογίας Κεφαλαιουχικών Κερδών (Τροποποιητικός) Νόμος του 2026",
             "Σκοπός της πρότασης νόμου είναι η τροποποίηση του περί Φορολογίας Κεφαλαιουχικών Κερδών Νόμου, ώστε να διορθωθούν στρεβλώσεις αναφορικά με την προθεσμία αποπεράτωσης της ανέγερσης οικοδομής στο πλαίσιο ανταλλαγής ακινήτων.",
             238, 755, [301, 332], 74),
        bill(62550, "2026-06-01T10:00:00", "2026-07-20T09:00:00", "o-peri-ethnikou-systimatos-vivliothikon-nomos-tou-2026",
             "Ο περί Εθνικού Συστήματος Βιβλιοθηκών Νόμος του 2026", "Σκοπός του νομοσχεδίου είναι η θέσπιση εθνικού συστήματος βιβλιοθηκών.", 238, 111, [42], 34),
        bill(62560, "2026-09-09T12:00:00", "2026-09-09T12:00:00", "o-peri-allodapon-kai-metanastefseos-tropopoiitikos-ar-3-nomos-tou-2026",
             "Ο περί Αλλοδαπών και Μεταναστεύσεως (Τροποποιητικός) (Αρ. 3) Νόμος του 2026",
             "Σκοπός του νομοσχεδίου είναι η τροποποίηση του περί Αλλοδαπών και Μεταναστεύσεως Νόμου, ώστε να ρυθμιστεί η διαδικασία έκδοσης άδειας διαμονής σε υπηκόους τρίτων χωρών που εργοδοτούνται σε εταιρείες ξένων συμφερόντων.",
             238, 111, [643], 34),
        bill(62570, "2026-05-05T12:00:00", "2026-09-11T15:00:00", "o-peri-etaireion-tropopoiitikos-ar-2-nomos-tou-2026",
             "Ο περί Εταιρειών (Τροποποιητικός) (Αρ. 2) Νόμος του 2026",
             "Σκοπός του νομοσχεδίου είναι η τροποποίηση του περί Εταιρειών Νόμου για την ενσωμάτωση της Οδηγίας (ΕΕ) 2019/2121 όσον αφορά τις διασυνοριακές μετατροπές, συγχωνεύσεις και διασπάσεις.",
             239, 610, [369], 34),
    ]
    put(Http.full_url(f"{api}bills", {"modified_after": WIN_AFTER, "orderby": "modified", "order": "desc", "_fields": nomoplatform.BILL_FIELDS, "per_page": 100, "page": 1}),
        json.dumps([b for b in bills if b["modified"] >= WIN_AFTER], ensure_ascii=False).encode("utf-8"))
    put(Http.full_url(f"{api}bills", {"after": WIN_AFTER, "before": WIN_BEFORE, "orderby": "date", "order": "desc", "_fields": nomoplatform.BILL_FIELDS, "per_page": 100, "page": 1}),
        json.dumps([b for b in bills if WIN_AFTER <= b["date"] <= WIN_BEFORE], ensure_ascii=False).encode("utf-8"))

    def bill_page(title, file_no, purpose, timeline: list[tuple[str, str]], docs: list[str]):
        tl = "\n".join(f'<div class="jet-listing-dynamic-repeater__item"><span class="date">{d}</span><span class="event">{e}</span></div>' for d, e in timeline)
        dl = "\n".join(f'<li><a href="{u}">{u.rsplit("/", 1)[-1]}</a></li>' for u in docs)
        return (f'<html><head><meta charset="utf-8"><title>{title} - Nomoplatform</title></head><body><main><h1>{title}</h1>'
                f'<div class="meta"><span>Αρ. Φακέλου</span><span>{file_no}</span><span>Στάδιο</span><span>Εκκρεμεί</span></div>'
                f'<section><h3>Σκοπός</h3><p>{purpose}</p></section><section><h3>Πορεία</h3>{tl}</section>'
                f'<section><h3>Έγγραφα</h3><ul>{dl}</ul></section></main></body></html>').encode("utf-8")

    put(bills[0]["link"], bill_page(bills[0]["title"]["rendered"], "23.02.067.080-2026", "Σκοπός της πρότασης νόμου είναι η τροποποίηση του περί Ρυθμίσεως Οδών και Οικοδομών Νόμου.",
                                    [("14 Ιουλίου 2026", "Κατάθεση και παραπομπή στην Κοινοβουλευτική Επιτροπή Εσωτερικών"), ("08/09/2026", "Συζήτηση στην Κοινοβουλευτική Επιτροπή Εσωτερικών")],
                                    ["https://www.nomoplatform.cy/wp-content/uploads/2026/08/23.02.067.080-2026.pdf"]))
    put(bills[1]["link"], bill_page(bills[1]["title"]["rendered"], "23.02.067.081-2026", "Σκοπός της πρότασης νόμου είναι η τροποποίηση του περί Φορολογίας Κεφαλαιουχικών Κερδών Νόμου.",
                                    [("14 Ιουλίου 2026", "Κατάθεση και παραπομπή στην Κοινοβουλευτική Επιτροπή Οικονομικών και Προϋπολογισμού"), ("10 Σεπτεμβρίου 2026", "Συζήτηση στην Κοινοβουλευτική Επιτροπή Οικονομικών και Προϋπολογισμού")],
                                    ["https://www.nomoplatform.cy/wp-content/uploads/2026/08/23.02.067.081-2026.pdf", "https://www.cylaw.org/nomoi/indexes/1980_1_52.html"]))
    put(bills[3]["link"], bill_page(bills[3]["title"]["rendered"], "23.01.067.101-2026", "Σκοπός του νομοσχεδίου είναι η τροποποίηση του περί Αλλοδαπών και Μεταναστεύσεως Νόμου.",
                                    [("9 Σεπτεμβρίου 2026", "Κατάθεση και παραπομπή στην Κοινοβουλευτική Επιτροπή Εσωτερικών")], []))
    put(bills[4]["link"], bill_page(bills[4]["title"]["rendered"], "23.01.067.055-2026", "Σκοπός του νομοσχεδίου είναι η τροποποίηση του περί Εταιρειών Νόμου.",
                                    [("5 Μαΐου 2026", "Κατάθεση και παραπομπή στην Κοινοβουλευτική Επιτροπή Οικονομικών και Προϋπολογισμού"), ("11 Σεπτεμβρίου 2026", "Τέθηκε προς ψήφιση στην Ολομέλεια και υπερψηφίστηκε")], []))

    posts = [
        {"id": 70001, "date": "2026-09-11T19:30:00", "modified": "2026-09-11T19:30:00", "slug": "apofaseis-olomeleias-11-9-2026", "link": "https://www.nomoplatform.cy/apofaseis-olomeleias-11-9-2026/",
         "title": {"rendered": "Αποφάσεις Ολομέλειας 11/09/2026"}, "categories": [488, 278],
         "content": {"rendered": "<p>Η Ολομέλεια της Βουλής υπερψήφισε τον περί Εταιρειών (Τροποποιητικό) (Αρ. 2) Νόμο του 2026 και ανέβαλε τη συζήτηση του περί Φορολογίας Κεφαλαιουχικών Κερδών (Τροποποιητικού) Νόμου του 2026.</p>"},
         "excerpt": {"rendered": ""}},
        {"id": 70002, "date": "2026-09-07T09:00:00", "modified": "2026-09-07T09:00:00", "slug": "programma-epitropon-7-11-9", "link": "https://www.nomoplatform.cy/programma-7-11-9-2026/",
         "title": {"rendered": "Πρόγραμμα Κοινοβουλευτικών Επιτροπών 7–11 Σεπτεμβρίου 2026"}, "categories": [309],
         "content": {"rendered": "<p>Επιτροπή Οικονομικών: συζήτηση νομοσχεδίων για τη φορολογία. Επιτροπή Παιδείας: σχολικές εφορείες.</p>"}, "excerpt": {"rendered": ""}},
    ]
    cats = [nomoplatform.CAT_PLENARY, nomoplatform.CAT_PROGRAMME] + list(nomoplatform.CAT_COMMITTEES)
    put(Http.full_url(f"{api}posts", {"after": WIN_AFTER, "before": WIN_BEFORE, "categories": ",".join(map(str, cats)), "orderby": "date", "order": "desc",
                                      "_fields": nomoplatform.POST_FIELDS, "per_page": 100, "page": 1}),
        json.dumps(posts, ensure_ascii=False).encode("utf-8"))

    # --- gov.cy --------------------------------------------------------
    gposts = [
        {"id": 130010, "date": "2026-09-11T10:00:00", "modified": "2026-09-11T10:00:00", "link": "https://www.gov.cy/ergasia-kai-koinonikes-asfaliseis/anakoinosi-tis-ypiresias-koinonikon-asfaliseon-anaforika-me-tin-paratasi-gia-ti-rythmisi-lixiprothesmon-koinonikon-eisforon/",
         "title": {"rendered": "Ανακοίνωση της Υπηρεσίας Κοινωνικών Ασφαλίσεων αναφορικά με την παράταση για τη ρύθμιση Ληξιπρόθεσμων Κοινωνικών Εισφορών"}, "categories": [218],
         "excerpt": {"rendered": "<p>Οι Υπηρεσίες Κοινωνικών Ασφαλίσεων ανακοινώνουν την παράταση της προθεσμίας υποβολής αιτήσεων για ένταξη στη ρύθμιση ληξιπρόθεσμων κοινωνικών εισφορών μέχρι τις 31 Οκτωβρίου 2026.</p>"},
         "content": {"rendered": "<p>Οι Υπηρεσίες Κοινωνικών Ασφαλίσεων ανακοινώνουν την παράταση της προθεσμίας υποβολής αιτήσεων για ένταξη στη ρύθμιση ληξιπρόθεσμων κοινωνικών εισφορών μέχρι τις 31 Οκτωβρίου 2026, σύμφωνα με την Κ.Δ.Π. 329/2026.</p>"}},
        {"id": 130011, "date": "2026-09-09T15:26:00", "modified": "2026-09-09T15:26:00", "link": "https://www.gov.cy/oikonomia/prosorini-diakopi-sti-leitourgia-michanografikon-systimaton-tou-tmimatos-forologias-3/",
         "title": {"rendered": "Προσωρινή διακοπή στη λειτουργία Μηχανογραφικών Συστημάτων του Τμήματος Φορολογίας"}, "categories": [182],
         "excerpt": {"rendered": "<p>Το Τμήμα Φορολογίας ενημερώνει ότι την Παρασκευή, 11/9/2026 θα πραγματοποιηθεί προσωρινή διακοπή.</p>"}, "content": {"rendered": "<p>…</p>"}},
        {"id": 130012, "date": "2026-09-11T11:00:00", "modified": "2026-09-11T11:00:00", "link": "https://www.gov.cy/oikonomia/kratikoi-ypalliloi-kata-katigoria-avgoustos-2026/",
         "title": {"rendered": "Κρατικοί Υπάλληλοι κατά Κατηγορία: Αύγουστος 2026"}, "categories": [182], "excerpt": {"rendered": "<p>Στατιστική Υπηρεσία.</p>"}, "content": {"rendered": "<p>…</p>"}},
        {"id": 130013, "date": "2026-09-10T12:00:00", "modified": "2026-09-10T12:00:00", "link": "https://www.gov.cy/oikonomia/anakoinosi-tou-tmimatos-forologias-gia-paratasi-fpa/",
         "title": {"rendered": "Ανακοίνωση του Τμήματος Φορολογίας για παράταση της ημερομηνίας υποβολής της Δήλωσης ΦΠΑ για την περίοδο που έληξε στις 31/8/2026"}, "categories": [182],
         "excerpt": {"rendered": "<p>Το Τμήμα Φορολογίας ανακοινώνει ότι η ημερομηνία υποβολής της Δήλωσης ΦΠΑ και πληρωμής του οφειλόμενου ΦΠΑ για την περίοδο που έληξε στις 31/8/2026 παρατείνεται μέχρι τις 20/10/2026.</p>"}, "content": {"rendered": "<p>…</p>"}},
        {"id": 130014, "date": "2026-09-13T09:00:00", "modified": "2026-09-13T09:00:00", "link": "https://www.gov.cy/ergasia-kai-koinonikes-asfaliseis/o-ypourgos-ergasias-anachorei-gia-ti-vienni/",
         "title": {"rendered": "Ο Υπουργός Εργασίας και Κοινωνικών Ασφαλίσεων αναχωρεί για τη Βιέννη"}, "categories": [218], "excerpt": {"rendered": "<p>…</p>"}, "content": {"rendered": "<p>…</p>"}},
    ]
    put(Http.full_url(govcy.API, {"after": WIN_AFTER, "before": WIN_BEFORE, "categories": ",".join(map(str, govcy.CATEGORIES)), "per_page": 100, "page": 1,
                                  "orderby": "date", "order": "desc", "_fields": "id,date,modified,link,title,excerpt,content,categories"}),
        json.dumps(gposts, ensure_ascii=False).encode("utf-8"))

    # --- Registrar -----------------------------------------------------
    reg_html = ('<html><head><meta charset="utf-8"></head><body>'
                '<article class="item-box"><div class="date-box"><time class="showdate-a" pubdate="pubdate" datetime="2026-09-10">10 ΣΕΠ 2026</time></div>'
                '<h4 class="category"><a href="/gr/βάση-πληροφοριών/νέα">Νέα</a></h4>'
                '<h2 class="bold link-b fs_m"><a href="/gr/βάση-πληροφοριών/νέα/epikairopoiisi-mitroou-pragmatikon-dikaiouchon-2026" title="Επικαιροποίηση Μητρώου Πραγματικών Δικαιούχων 2026">Επικαιροποίηση Μητρώου Πραγματικών Δικαιούχων 2026</a></h2>'
                '<summary class="summary"> Το Τμήμα Εφόρου Εταιρειών και Διανοητικής Ιδιοκτησίας υπενθυμίζει ότι η ετήσια επιβεβαίωση στοιχείων πραγματικών δικαιούχων πρέπει να ολοκληρωθεί μέχρι 31/12/2026. <a href="/gr/βάση-πληροφοριών/νέα/epikairopoiisi-mitroou-pragmatikon-dikaiouchon-2026">περισσότερα</a></summary></article>'
                '<article class="item-box"><div class="date-box"><time class="showdate-a" pubdate="pubdate" datetime="2026-09-04">04 ΣΕΠ 2026</time></div>'
                '<h4 class="category"><a href="/gr/βάση-πληροφοριών/νέα">Νέα</a></h4>'
                '<h2 class="bold link-b fs_m"><a href="/gr/βάση-πληροφοριών/νέα/υποβολή-οφειλόμενων-ετησίων-εκθέσεων-παράταση" title="Υποβολή Οφειλόμενων Ετησίων Εκθέσεων - Παράταση">Υποβολή Οφειλόμενων Ετησίων Εκθέσεων και αντίστοιχων Οικονομικών Καταστάσεων - Παράταση</a></h2>'
                '<summary class="summary"> Παράταση μέχρι και την 31η Δεκεμβρίου 2026. </summary></article></body></html>')
    put(registrar.NEWS, reg_html.encode("utf-8"))
    put(registrar.BASE + "/gr/βάση-πληροφοριών/νέα/epikairopoiisi-mitroou-pragmatikon-dikaiouchon-2026",
        '<html><head><meta charset="utf-8"></head><body><article><h1>Επικαιροποίηση Μητρώου Πραγματικών Δικαιούχων 2026</h1><p>Το Τμήμα Εφόρου Εταιρειών και Διανοητικής Ιδιοκτησίας υπενθυμίζει ότι, σύμφωνα με την Οδηγία Κ.Δ.Π. 112/2021, η ετήσια επιβεβαίωση των στοιχείων των πραγματικών δικαιούχων στο Μητρώο Πραγματικών Δικαιούχων πρέπει να ολοκληρωθεί μέχρι την 31η Δεκεμβρίου 2026. Μη συμμόρφωση επιφέρει χρηματικό πρόστιμο €100 και €50 για κάθε ημέρα συνέχισης της παράβασης.</p></article></body></html>'.encode("utf-8"))

    # --- CBC -----------------------------------------------------------
    def art(date, title, slug):
        return f'<article class="text-center"><span class="date">{date}</span><h5>{title}</h5><a href="/en/announcements/{slug}" title="{title}"><span class="glyphicon"></span></a></article>'
    cbc_html = ('<html><head><meta charset="utf-8"></head><body><div class="announcement-list">' +
                art("14 September 2026", "The Rise and Fall of NPLs in Cyprus: Solved, Transferred or Transformed?", "npls-14-09-2026") +
                art("11 September 2026", "CBC Governor’s statement regarding yesterday’s monetary policy decision", "governor-statement-11-09-2026") +
                art("10 September 2026", "Amendment of the Directive on the Opening and Maintaining of Payment Accounts with Basic Features", "payment-accounts-directive-10-09-2026") +
                art("9 September 2026", "CIR Statistics August 2026", "cir-statistics-august-2026-09-09-2026") +
                art("3 September 2026", "Statistics on Interest Rates applied by Monetary Financial Institutions", "interest-rates-applied-by-mfis-03-09-2026") +
                '</div></body></html>')
    put(cbc.ANNOUNCEMENTS, cbc_html.encode("utf-8"))
    put(cbc.BASE + "/en/announcements/payment-accounts-directive-10-09-2026",
        '<html><head><meta charset="utf-8"></head><body><main><h1>Amendment of the Directive on the Opening and Maintaining of Payment Accounts with Basic Features</h1><p>The Central Bank of Cyprus announces the issue of the Directive (Amendment) of 2026 on the opening and maintaining of payment accounts with basic features, which enters into force on 1 November 2026. Credit institutions must decide on an application within ten business days.</p></main></body></html>'.encode("utf-8"))
    put(cbc.BASE + "/en/announcements/governor-statement-11-09-2026", b"<html><body><main><p>statement</p></main></body></html>")
    put(cbc.BASE + "/en/announcements/cir-statistics-august-2026-09-09-2026", b"<html><body><main><p>stats</p></main></body></html>")

    print(f"fixtures written to {CACHE} ({len(list(CACHE.glob('*.bin')))} responses)")


if __name__ == "__main__":
    build()
