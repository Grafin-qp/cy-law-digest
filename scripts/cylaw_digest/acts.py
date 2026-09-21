"""Parsing of Cypriot statutory texts (laws and Κ.Δ.Π.) out of Gazette / CyLaw
PDF text. Pure functions over strings – no network – so they are unit-testable
on fixtures.

What the Gazette looks like (Παράρτημα Πρώτο Ι, one law):

    N. 120(I)/2026
    ΕΠΙΣΗΜΗ ΕΦΗΜΕΡΙΔΑ ΤΗΣ ΚΥΠΡΙΑΚΗΣ ΔΗΜΟΚΡΑΤΙΑΣ
    ΠΑΡΑΡΤΗΜΑ ΠΡΩΤΟ  ΝΟΜΟΘΕΣΙΑ - ΜΕΡΟΣ Ι
    Αριθμός 5092 Παρασκευή, 26 Ιουνίου 2026 959
    Ο περί Φόρων Κατανάλωσης (Τροποποιητικός) (Αρ. 2) Νόμος του 2026 εκδίδεται με δημοσίευση ...
    Αριθμός 120(Ι) του 2026
    ΝΟΜΟΣ ΠΟΥ ΤΡΟΠΟΠΟΙΕΙ ΤΟΥΣ ΠΕΡΙ ΦΟΡΩΝ ΚΑΤΑΝΑΛΩΣΗΣ ΝΟΜΟΥΣ ΤΟΥ 2004 ΕΩΣ 2026
    ... 1. Ο παρών Νόμος θα αναφέρεται ως ο περί ... Νόμος του 2026 ...
    2. Το Πρώτο Παράρτημα του βασικού νόμου τροποποιείται ...

Παράρτημα Τρίτο Ι (regulatory acts), one per section:

    Ε.Ε. Παρ. ΙΙΙ(Ι) Κ.Δ.Π. 329/2026
    Αρ. 6045, 11.9.2026
    Αριθμός 329
    ΟΙ ΠΕΡΙ ΡΥΘΜΙΣΗΣ ΛΗΞΙΠΡΟΘΕΣΜΩΝ ΚΟΙΝΩΝΙΚΩΝ ΕΙΣΦΟΡΩΝ ΝΟΜΟΙ ΤΟΥ 2016 ΕΩΣ 2026
    Γνωματοποίηση δυνάμει του άρθρου 5
    ... 1. Το παρόν Διάταγμα θα αναφέρεται ως το περί ... Διάταγμα του 2026.
    Έναρξη ισχύος. 5. Η παρούσα Γνωστοποίηση ισχύει από ...
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Optional

from .greekdates import parse_date

# --- regexes ---------------------------------------------------------------
# Law number as printed anywhere: "Ν. 124(I)/2026", "N. 124(Ι)/2026" (Latin or Greek N/I), "Αριθμός 124(Ι) του 2026"
LAW_NO = re.compile(r"(?:[NΝ]\.\s*)?(\d+[Α-ΩA-Z]?)\s*\(\s*([IΙ]{1,3})\s*\)\s*(?:/|του\s+)(\d{4})")
LAW_NO_HEADER = re.compile(r"Αριθμός\s+(\d+[Α-ΩA-Z]?)\s*\(\s*([IΙ]{1,3})\s*\)\s+του\s+(\d{4})")
KDP_NO = re.compile(r"Κ\.\s*Δ\.\s*Π\.\s*(\d+[Α-Ω]?)\s*/\s*(\d{4})")
# Page header of an act inside annex III(I): "Ε.Ε. Παρ. ΙΙΙ(Ι) Κ.Δ.Π. 329/2026" or a bare "Κ.Δ.Π. 328/2026" first line.
# Anchored to the line so that cross-references like "(Κ.Δ.Π. 173/2024)" inside a text are not mistaken for markers.
KDP_PAGE_HEADER = re.compile(r"^\s*(?:Ε\.Ε\.\s*Παρ\.\s*[IΙ]+\s*\([IΙ]+\)\s*)?Κ\.\s*Δ\.\s*Π\.\s*(\d+[Α-Ω]?)\s*/\s*(\d{4})\s*$", re.M)
KDP_SECTION = re.compile(r"^\s*Αριθμός\s+(\d+[Α-Ω]?)\s*$", re.M)
GAZETTE_ISSUE = re.compile(r"Αριθμός\s+(\d{4})\s+(?:Δευτέρα|Τρίτη|Τετάρτη|Πέμπτη|Παρασκευή|Σάββατο|Κυριακή),?\s+(\d{1,2})(?:η|ης)?\s+([Α-Ωα-ωΆ-Ώά-ώ]+)\s+(\d{4})")
GAZETTE_SHORT = re.compile(r"Αρ\.\s*(\d{4}),\s*(\d{1,2}\.\d{1,2}\.\d{4})")
PROMULGATION = re.compile(r"((?:[OΟ]|Η|Το|Οι)\s+περί\s+.+?(?:Νόμος|Νόμοι)\s+του\s+\d{4})\s+εκδίδ[εο]", re.S)
SHORT_TITLE = re.compile(
    r"θα\s+αναφέρεται\s+ως\s+((?:ο|το|οι|η)\s+περί\s+.+?\s+(?:Νόμος|Διάταγμα|Κανονισμοί|Γνωστοποίηση|Απόφαση|Διατάγματα|Οδηγία|Κανονισμός)\s+του\s+\d{4})",
    re.S)
KDP_INSTRUMENT = re.compile(
    r"^\s*((?:Διάταγμα|Διατάγματα|Κανονισμοί|Γνωστοποίηση|Απόφαση|Οδηγία|Κανονισμός|Ειδοποίηση)\s+(?:δυνάμει|με βάση|σύμφωνα με|βάσει)\s+.+?)$",
    re.M)
CAPS_TITLE = re.compile(r"^\s*((?:Ο|ΟΙ|Η|ΤΟ|ΝΟΜΟΣ|ΝΟΜΟΙ)\s+(?:ΠΕΡΙ|ΠΟΥ)\s+.{10,400}?)$", re.M)
ENTRY_INTO_FORCE = re.compile(
    r"([^.\n]{0,120}(?:τίθεται\s+σε\s+ισχύ|έναρξη\s+της\s+ισχύος|ισχύει\s+από|λογίζεται\s+ότι\s+άρχισε\s+να\s+ισχύει|αρχίζει\s+να\s+ισχύει|θα\s+ισχύει\s+από|ισχύ\w*\s+από\s+την)[^.\n]{0,220}\.)",
    re.I)
ARTICLE_START = re.compile(r"(?m)^\s*(\d{1,3})\.\s*[-–]?\s*(?:\(\d+\)\s*)?(?=[Α-ΩA-Z«(])")

# Margin notes that pdftotext interleaves; we drop lines that are just these.
MARGIN_LINE = re.compile(
    r"^\s*(?:Συνοπτικός|τίτλος\.?|Ερμηνεία\.?|Έναρξη|ισχύος\.?|Τροποποίηση|του βασικού|νόμου\.?|Παράρτημα\.?|Επίσημη|Εφημερίδα,?|"
    r"Παράρτημα Τρίτο \(Ι\):|\d+\([IΙ]+\) του \d{4}\.?|\d+\([IΙ]+\)/\d{4}\.?|Κεφ\. \d+\.?|\d{1,2}\.\d{1,2}\.\d{4}\.?|Κ\.Δ\.Π\. \d+/\d{4}\.?|_{3,})\s*$")


def _is_margin_fragment(ln: str) -> bool:
    """Side-note fragments pdftotext interleaves before an article ('Τροποποίηση', 'του άρθρου 8',
    'του βασικού', 'νόμου.'): short, no digits except law refs, no closing punctuation other than '.'."""
    t = ln.strip()
    if not t or len(t) > 42 or "«" in t or "»" in t or t.endswith((":", ";", "·", ",")):
        return False
    words = t.split()
    if len(words) > 4:
        return False
    if re.search(r"\d", t) and not re.fullmatch(r"(?:\d+\([IΙ]+\)\s*(?:του\s+\d{4}|/\d{4})\.?|Κεφ\. \d+\.?|\d{1,2}\.\d{1,2}\.\d{4}\.?)", t):
        return False
    return True


def clean_lines(text: str) -> str:
    raw = text.splitlines()
    drop = set()
    for i, ln in enumerate(raw):
        if MARGIN_LINE.match(ln):
            drop.add(i)
        if ARTICLE_START.match(ln):
            j = i - 1
            while j >= 0 and _is_margin_fragment(raw[j]):
                drop.add(j)
                j -= 1
    out = [ln.rstrip() for i, ln in enumerate(raw) if i not in drop]
    s = "\n".join(out)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def normalise_number(num: str, part: str, year: str) -> str:
    part = part.replace("Ι", "I")
    return f"{num}({part})/{year}"


@dataclass
class ParsedAct:
    kind: str                       # law | kdp
    number: str                     # "124(I)/2026" or "329/2026"
    title: str = ""                 # title as printed (mixed case, from promulgation/short title)
    caps_title: str = ""            # long title in caps ("ΝΟΜΟΣ ΠΟΥ ΤΡΟΠΟΠΟΙΕΙ ...")
    parent_law: str = ""            # for Κ.Δ.Π.: the enabling law ("ΟΙ ΠΕΡΙ ... ΝΟΜΟΙ ΤΟΥ 2016 ΕΩΣ 2026")
    instrument: str = ""            # for Κ.Δ.Π.: "Διάταγμα δυνάμει του άρθρου 38Α"
    gazette_no: str = ""
    gazette_date: Optional[dt.date] = None
    entry_into_force: str = ""
    excerpt: str = ""               # substantive text after the short-title article
    text: str = ""                  # full cleaned text of the act
    warnings: list[str] = field(default_factory=list)


def parse_gazette_header(text: str) -> tuple[str, Optional[dt.date]]:
    m = GAZETTE_ISSUE.search(text)
    if m:
        d = parse_date(f"{m.group(2)} {m.group(3)} {m.group(4)}")
        return m.group(1), d
    m = GAZETTE_SHORT.search(text)
    if m:
        return m.group(1), parse_date(m.group(2))
    return "", None


def _excerpt(text: str, limit: int = 1800) -> str:
    """Text from the first substantive article (usually article 2, after the
    short-title article 1) – this is 'the law's own wording' for the digest."""
    body = clean_lines(text)
    # skip past the short title article if present
    m = SHORT_TITLE.search(body)
    start = m.end() if m else 0
    # find the next article start after the short title
    nxt = ARTICLE_START.search(body, start)
    if nxt:
        start = nxt.start()
    ex = body[start:start + limit].strip()
    # cut at the print footer / signature block / next act's page header if they slipped in
    ex = re.split(r"Τυπώθηκε στο Τυπογραφείο|\nΈγινε στις |\nΕ\.Ε\. Παρ\.", ex)[0].strip()
    ex = re.sub(r"\n\d{3,4}\s*$", "", ex).strip()   # trailing page number
    return ex


def parse_law_text(text: str, number_hint: str = "") -> ParsedAct:
    """Parse one law (CyLaw per-law PDF, or a slice of the Gazette annex)."""
    act = ParsedAct(kind="law", number=number_hint)
    head = text[:6000]
    m = LAW_NO_HEADER.search(head) or LAW_NO.search(head)
    if m:
        act.number = normalise_number(m.group(1), m.group(2), m.group(3))
    act.gazette_no, act.gazette_date = parse_gazette_header(head)
    m = PROMULGATION.search(head)
    if m:
        act.title = re.sub(r"\s+", " ", m.group(1)).strip()
    m = SHORT_TITLE.search(text[:12000])
    short = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    if not act.title and short:
        act.title = short[0].upper() + short[1:]
    for cm in CAPS_TITLE.finditer(head):
        cand = re.sub(r"\s+", " ", cm.group(1)).strip()
        if cand.startswith(("ΝΟΜΟΣ", "ΝΟΜΟΙ")) or " ΝΟΜΟΣ" in cand:
            act.caps_title = cand
            break
    m = ENTRY_INTO_FORCE.search(re.sub(r"\s+", " ", clean_lines(text)))
    if m:
        act.entry_into_force = m.group(1).strip()
    act.excerpt = _excerpt(text)
    act.text = clean_lines(text)
    if not act.title:
        act.warnings.append("title_not_found")
    if not act.gazette_date:
        act.warnings.append("gazette_date_not_found")
    return act


def split_kdp_sections(text: str) -> list[tuple[str, str]]:
    """Split annex III(I) text into (kdp_number, section_text) pairs.

    Each act starts with a line 'Αριθμός NNN' (its Κ.Δ.Π. number within the
    year); page headers 'Ε.Ε. Παρ. ΙΙΙ(Ι) Κ.Δ.Π. NNN/YYYY' repeat on every page
    of the act. An act's section runs from its first marker (page header or
    'Αριθμός N' line, whichever comes first) to the first marker of a different
    number.
    """
    year_m = KDP_PAGE_HEADER.search(text) or KDP_NO.search(text)
    year = year_m.group(2) if year_m else str(dt.date.today().year)
    markers: list[tuple[int, str]] = []
    for m in KDP_PAGE_HEADER.finditer(text):
        if m.group(2) == year:
            markers.append((m.start(), m.group(1)))
    for m in KDP_SECTION.finditer(text):
        markers.append((m.start(), m.group(1)))
    markers.sort()
    sections: dict[str, list[str]] = {}
    order: list[str] = []
    i = 0
    while i < len(markers):
        pos, num = markers[i]
        j = i + 1
        while j < len(markers) and markers[j][1] == num:
            j += 1
        end = markers[j][0] if j < len(markers) else len(text)
        # the page header that opens the *next* act sits right before its 'Αριθμός' line: keep it out
        seg = text[pos:end]
        if num not in sections:
            order.append(num)
        sections.setdefault(num, []).append(seg)
        i = j
    return [(f"{n}/{year}", "\n".join(sections[n])) for n in order]


def parse_kdp_section(number: str, section: str, gazette_no: str = "", gazette_date: Optional[dt.date] = None) -> ParsedAct:
    act = ParsedAct(kind="kdp", number=number, gazette_no=gazette_no, gazette_date=gazette_date)
    lines = [ln.strip() for ln in section.splitlines() if ln.strip()]
    # parent law: first all-caps line(s) after 'Αριθμός N'
    caps: list[str] = []
    for ln in lines[1:8]:
        if re.match(r"^(?:Ο|ΟΙ|Η|ΤΟ)\s+ΠΕΡΙ\s", ln) or (caps and ln.isupper() and not ln.startswith("_")):
            caps.append(ln)
        elif caps:
            break
    act.parent_law = re.sub(r"\s+", " ", " ".join(caps)).strip()
    m = KDP_INSTRUMENT.search(section)
    if m:
        act.instrument = re.sub(r"\s+", " ", m.group(1)).strip()
    m = SHORT_TITLE.search(section)
    if m:
        t = re.sub(r"\s+", " ", m.group(1)).strip()
        act.title = t[0].upper() + t[1:]
    else:
        # fallback: instrument + parent law
        act.title = (act.instrument + " — " + act.parent_law).strip(" —")
        act.warnings.append("short_title_not_found")
    body = clean_lines(section)
    m = ENTRY_INTO_FORCE.search(re.sub(r"\s+", " ", body))
    if m:
        act.entry_into_force = m.group(1).strip()
    act.excerpt = _excerpt(section, limit=1500)
    act.text = body
    if not gazette_date:
        act.gazette_no, act.gazette_date = parse_gazette_header(section)
    return act


def split_laws_in_annex(text: str) -> list[tuple[str, str]]:
    """Split annex I(I) text into (law_number, text) using 'Αριθμός N(I) του YYYY' markers."""
    starts = list(LAW_NO_HEADER.finditer(text))
    out = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        prev_end = starts[i - 1].end() if i > 0 else 0
        head_zone = text[prev_end:m.start()]
        # the law's own front matter precedes the 'Αριθμός N(I) του YYYY' marker: its page header
        # ("N. 126(I)/2026" / "Ε.Ε. Παρ. Ι(Ι) Ν. 126(Ι)/2026") and the promulgation sentence ("Ο περί … εκδίδεται …").
        num_pat = re.compile(r"[NΝ]\.\s*" + re.escape(m.group(1)) + r"\s*\(\s*[IΙ]{1,3}\s*\)\s*/\s*" + m.group(3))
        cands = [x.start() for x in num_pat.finditer(head_zone)]
        prom = [x.start() for x in re.finditer(r"(?m)^\s*(?:[OΟ]|Η|Το|Οι)\s+περί\s", head_zone)]
        if cands:
            seg_start = prev_end + cands[-1]
        elif prom:
            seg_start = prev_end + prom[-1]
        else:
            seg_start = max(prev_end, m.start() - 600)
        out.append((normalise_number(m.group(1), m.group(2), m.group(3)), text[seg_start:end]))
    return out
