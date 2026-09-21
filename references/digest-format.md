# Digest format

Version: CY_LAW_DIGEST_V2 / 2026-09. The single source of truth for structure, density and language.

## Language

The digest is written in **English** regardless of the language of the request (a request in Russian still gets an English digest). Titles of acts, names of bodies and quotations stay in the original language (Greek; the Central Bank publishes in English). The first mention of a Greek title gets an English rendering in brackets. Every item ends with a plain-English summary, so that colleagues who do not read Greek can use the digest on its own. A Russian version is produced only when the user explicitly asks for one — same structure, same quotations, Russian prose.

Terminology: Επίσημη Εφημερίδα — Official Gazette; Κ.Δ.Π. (Κανονιστική Διοικητική Πράξη) — regulatory administrative act (secondary legislation); Ολομέλεια — plenary of the House of Representatives; Νομοσχέδιο — government bill; Πρόταση Νόμου — private member's bill; Αρ. Φακ. — House file number; Παρ. Ι(Ι) / ΙΙΙ(Ι) — Gazette Annex I Part I / Annex III Part I.

## Principle

The digest is distilled from `skeleton.md`, never written from memory. Each item follows one pattern:

1. **Identification** — number, original title (+ English rendering), source, date, practice area, link.
2. **Wording of the act** — the operative sentence quoted verbatim in Greek, followed by a faithful English translation. Not a paraphrase: the sentence that actually changes the law — a new rate, deadline, obligation, or the entry-into-force clause.
3. **Summary** — 2–4 English sentences: what changes, for whom, from when. This block closes the item.
4. **Practice note** (inside the summary, one or two sentences) — where it surfaces in the department's work (SPA, structuring, banking referrals, hiring foreigners). Where a conclusion depends on local practice: "to be confirmed with the Cyprus team".

Order 2 → 3 is deliberate: the law's own words first, our interpretation after. The reader must see where the statute ends and the summary begins.

## Template

```markdown
# Cyprus Law Digest — <date from> – <date to>

Window: DD.MM.YYYY – DD.MM.YYYY · Sources: Επίσημη Εφημερίδα, CyLaw, Nomoplatform / House of Representatives, gov.cy, Registrar of Companies, Central Bank of Cyprus
<if a source was unavailable — one line: "Not verified: … (reason)">

## At a glance
- <practice area> — <one line on the week's most important event, with the act number>
- …                                             (3–6 lines; nothing to report — "No material changes")

## 1. Enacted and published

### 1.1 Laws (Official Gazette, Annex I)

**Ν. 125(I)/2026 — Ο περί Φορολογίας του Εισοδήματος (Τροποποιητικός) (Αρ. 3) Νόμος του 2026** (Income Tax (Amendment) (No. 3) Law of 2026)
Ε.Ε. Παρ. Ι(Ι), No. 5096, 11.09.2026 · Tax · [PDF](link)
> **Wording.** «…operative sentence, verbatim Greek…»
> *Translation:* "…faithful English…"
> **Entry into force.** «Ο παρών Νόμος τίθεται σε ισχύ από την 1η Ιανουαρίου 2027.» — from 1 January 2027.

Summary: … Practice note: …

### 1.2 Secondary legislation — Κ.Δ.Π. (Annex III(I))
<same block, shorter: one quotation + a 1–2 sentence summary>

### 1.3 Voted by the plenary, not yet in the Gazette
<same block; instead of Gazette details — vote date and Αρ. Φακ.; the quotation is the Σκοπός (purpose)>

## 2. In progress (bills)

**Ο περί … Νόμος του 2026** (English rendering) — Πρόταση Νόμου / Νομοσχέδιο, Αρ. Φακ. …, <committee or author> · <practice area>
Event of the week: DD.MM.YYYY — <submitted / discussed in committee / postponed / withdrawn>. Status: <Εκκρεμεί …>. [Nomoplatform](link)
> **Σκοπός.** «…verbatim…» — *"translation"*.

Summary: …

Parliament round-up (skeleton section B2 — plenary-decision and committee posts): one line per post — date, what was voted / discussed that touches the practice areas, link. If a post contradicts a bill's own timeline, say so in the bill's item and cite both.

## 3. Regulators and departments

**<Body> — <original title>** (English rendering) · DD.MM.YYYY · <practice area> · [link]
> «…key sentence verbatim…» — *"translation"*.

Summary: …

## 4. Other laws of the week
- Ν. 126(I)/2026 — Ο περί Θήρας και Προστασίας Άγριων Πτηνών (Τροποποιητικός) Νόμος του 2026 (Game and Wild Birds (Amendment) Law) (11.09.2026)

## Verification
Checked: Ε.Ε. Παρ. Ι(Ι) up to No. …; Παρ. ΙΙΙ(Ι) up to No. …; CyLaw up to Ν. …; Nomoplatform, gov.cy, Registrar, CBC — as of <date>.   ← take issue numbers, "walked down to" and the run timestamp from the skeleton's "Coverage" line
Collected by: <script in session | remote run (GitHub Actions / local) fetched with fetch_run.py | WebFetch fallback>.
Dropped by the relevance filter: N items (see `skeleton.md`, section E).
```

## Density rules

- "At a glance" — 3–6 lines, one thought per line, with the act number. Do not repeat the items' text.
- A law item — up to 120 words of prose plus quotations. One or two quotations, up to 60 Greek words each. Never quote preambles, references to «ο βασικός νόμος» or the lists of earlier amending laws.
- A Κ.Δ.Π. item — up to 80 words plus one quotation (two only when the entry-into-force clause matters).
- A bill item — up to 80 words plus the Σκοπός.
- A regulator item — up to 60 words plus one quotation.
- Items with relevance score 1 (weak match) — the writer decides: keep only if the act touches the practice areas on reading; otherwise leave it out and count it among the dropped items in the Verification block. Never mark items as "low relevance" inside the digest.
- A field the parser could not find (⚠ warning) that is genuinely absent from the act (e.g. a Γνωστοποίηση without a short title) — use the descriptive form "<instrument> under s. N of <parent law>" and say nothing about the parser.
- Empty section — one line "No changes". Do not delete the section: the reader must see it was checked.
- A section whose source was unavailable — one line "Not verified: <source> (<reason>)", never "No changes": "none" may only be said about what was actually looked at. Repeat in the header line ("Not verified: …") and in the Verification block.
- A source marked `partial` in the skeleton whose failed requests lie outside the window (typical: CyLaw's walk into older laws) does not change coverage — one clause in the Verification block ("CyLaw: 3 older PDFs not retrieved, window unaffected"), nothing in the header.
- An item outside the window is not news. If the digest would otherwise be empty and the deadline matters to the practice, one line at the end of section 3 marked "outside the window, for reference".
- Section 4 — one line per law, no commentary. This is the completeness guarantee: the reader sees every law of the week and can ask about any of them.
- No introductions, no conclusions, no "it is worth noting", no "we will keep monitoring". The digest starts with the title and ends with the Verification block.

## What counts as an event of the week

An item belongs to the digest when the window contains:
- the date of the Gazette issue in which the act was published (laws, Κ.Δ.Π.);
- the entry-into-force date of an act published earlier — only when the skeleton shows it (field "entry into force") and it falls in the window; mark such items "entered into force DD.MM.YYYY, published earlier";
- the date of a plenary vote, of submission or of a committee discussion (bills). A bill record merely *modified* in the window without a dated event in its timeline is not an event;
- the publication date of a departmental announcement.

If a date is not confirmed, the item is not presented as news (the skeleton marks these "date not confirmed").

## An empty week

The parliamentary summer recess (July–September) and unavailable sources produce "empty" digests. They are still issued — short, without padding:

```markdown
# Cyprus Law Digest — 7–13 September 2026

Window: 07.09.2026 – 13.09.2026 · Sources: Επίσημη Εφημερίδα, CyLaw, Nomoplatform / House of Representatives, gov.cy, Registrar of Companies, Central Bank of Cyprus
Not verified: Επίσημη Εφημερίδα (mof.gov.cy — TLS error of the fetch tool), gov.cy (HTTP 403).

## At a glance
- No material changes in the available sources; the Gazette and gov.cy announcements for the window were not verified — Κ.Δ.Π. and Tax Department notices may be missing.

## 1. Enacted and published
### 1.1 Laws — Not verified: Ε.Ε. Παρ. Ι(Ι). CyLaw shows no law dated in the window (latest: Ν. 124(I)/2026, 24.07.2026).
### 1.2 Κ.Δ.Π. — Not verified: Ε.Ε. Παρ. ΙΙΙ(Ι); CyLaw's Κ.Δ.Π. index stops at 08.05.2026.
### 1.3 Voted — No changes (Nomoplatform: no plenary-decision posts in the window).
## 2. In progress — No changes (one record modified on 08.09 with no dated event in the window).
## 3. Regulators and departments
Tax Department and other gov.cy bodies — not verified. Registrar of Companies — no notices in the window. CBC — statistics and statements only.
## 4. Other laws of the week — No changes (per CyLaw).
## Verification
Checked: CyLaw up to Ν. 124(I)/2026; Nomoplatform bills/posts; Registrar; CBC — as of 15.09.2026. Not verified: Ε.Ε., gov.cy. Dropped: 3 CBC notices, 2 Nomoplatform posts.
```

## Example (window 07.09.2026 – 13.09.2026, test data)

**The data below are test fixtures (`tests/`), partly invented (Ν. 125(I)/2026, Κ.Δ.Π. 331/2026, the CBC directive, the VAT deadline extension were made up to exercise the parser). This is a specimen of the form, not a source of facts — never reuse its sentences or glosses for a real run; every real item is written from that run's skeleton.**

# Cyprus Law Digest — 7–13 September 2026

Window: 07.09.2026 – 13.09.2026 · Sources: Επίσημη Εφημερίδα, CyLaw, Nomoplatform / House of Representatives, gov.cy, Registrar of Companies, Central Bank of Cyprus

## At a glance
- Tax — Ν. 125(I)/2026 published: 50% income-tax exemption for newly relocated employees earning above €55,000, from 01.01.2027.
- Tax / real estate — Κ.Δ.Π. 331/2026: reduced VAT rate on the first 130 m² of a primary residence; in force from publication (11.09.2026).
- Corporate — the plenary voted on 11.09 for the Companies (Amendment) (No. 2) Law implementing Directive (EU) 2019/2121 on cross-border conversions; not yet gazetted.
- Employment — settlement scheme for overdue social-insurance contributions: applications until 31.10.2026 (Κ.Δ.Π. 329/2026).
- Banking — CBC amended the directive on payment accounts with basic features; in force 01.11.2026.

## 1. Enacted and published

### 1.1 Laws (Official Gazette, Annex I)

**Ν. 125(I)/2026 — Ο περί Φορολογίας του Εισοδήματος (Τροποποιητικός) (Αρ. 3) Νόμος του 2026** (Income Tax (Amendment) (No. 3) Law of 2026)
Ε.Ε. Παρ. Ι(Ι), No. 5096, 11.09.2026 · Tax · [PDF](https://www.cylaw.org/nomoi/arith/2026_1_125.pdf)
> **Wording (new para. (24) of s. 8).** «Ποσό ίσο με το πενήντα τοις εκατόν (50%) της αμοιβής από την άσκηση οποιασδήποτε εργοδότησης στη Δημοκρατία, από άτομο το οποίο ήταν κάτοικος εκτός της Δημοκρατίας πριν από την έναρξη της εργοδότησής του στη Δημοκρατία, νοουμένου ότι η ετήσια αμοιβή υπερβαίνει τις πενήντα πέντε χιλιάδες ευρώ (€55.000).»
> *Translation:* "An amount equal to fifty per cent (50%) of the remuneration from any employment exercised in the Republic by an individual who was resident outside the Republic before the commencement of that employment, provided the annual remuneration exceeds fifty-five thousand euro (€55,000)."
> **Entry into force.** «Ο παρών Νόμος τίθεται σε ισχύ από την 1η Ιανουαρίου 2027.» — from 1 January 2027.

Summary: a new exemption is added to s. 8 of the Income Tax Law: half of the salary of an employee who was not a Cyprus resident before taking up employment here is exempt, provided the annual salary exceeds €55,000. The threshold and mechanics come from the text; the duration of the relief and its interaction with the existing exemption in para. (23) are not visible in the excerpt — read the full text. Practice note: relocation cases and employment contracts with foreign staff from 2027; the interplay with existing reliefs to be confirmed with the Cyprus tax team.

### 1.2 Secondary legislation — Κ.Δ.Π. (Annex III(I))

**Κ.Δ.Π. 331/2026 — Το περί Φόρου Προστιθέμενης Αξίας (Τροποποίηση του Πέμπτου Παραρτήματος) Διάταγμα του 2026** (VAT (Amendment of the Fifth Schedule) Order of 2026)
Ε.Ε. Παρ. ΙΙΙ(Ι), No. 6045, 11.09.2026 · Tax, real estate · [issue](https://www.mof.gov.cy/mof/gpo/gazette.nsf/All/4A7D42DCE00D6D38C2258E6F001E4045?OpenDocument)
> «Η παράδοση ή η ανέγερση κατοικίας που χρησιμοποιείται ως κύριος και μόνιμος χώρος διαμονής στη Δημοκρατία, για τα πρώτα εκατόν τριάντα τετραγωνικά μέτρα (130 τ.μ.) δομήσιμου εμβαδού.» — *"The supply or construction of a dwelling used as the principal and permanent place of residence in the Republic, for the first one hundred and thirty square metres (130 m²) of buildable area."*
> In force from publication in the Gazette (11.09.2026).

Summary: Table C of the Fifth Schedule to the VAT Law (reduced-rate supplies) gains a new para. 12 — a dwelling used as the principal residence, for its first 130 m². Council of Ministers order under s. 54. Practice note: VAT computation in SPAs for new-build property; the conditions for proving "principal and permanent residence" — see the full text of the order.

**Κ.Δ.Π. 329/2026 — Γνωστοποίηση δυνάμει του άρθρου 5 των περί Ρύθμισης Ληξιπρόθεσμων Κοινωνικών Εισφορών Νόμων του 2016 έως 2026** (Notice under s. 5 of the Settlement of Overdue Social Insurance Contributions Laws)
Ε.Ε. Παρ. ΙΙΙ(Ι), No. 6045, 11.09.2026 · Employment & social insurance
> «Οφειλέτης, ο οποίος επιθυμεί να προβεί σε ρύθμιση της οφειλής του υποβάλλει, μέχρι τις 31 Οκτωβρίου 2026, ηλεκτρονικά την αίτηση.» — *"A debtor who wishes to settle the debt submits the application electronically by 31 October 2026."*

Summary: applications for settlement of overdue social-insurance contributions under the 2016–2026 Laws are accepted electronically until 31.10.2026; the notice applies from publication. The Social Insurance Services' announcement on the same deadline is in section 3.

### 1.3 Voted by the plenary, not yet in the Gazette

**Ο περί Εταιρειών (Τροποποιητικός) (Αρ. 2) Νόμος του 2026** (Companies (Amendment) (No. 2) Law of 2026) — Νομοσχέδιο, Αρ. Φακ. 23.01.067.055-2026 · Corporate
Voted 11.09.2026 (Υπερψηφίστηκε). [Nomoplatform](https://www.nomoplatform.cy/bills/o-peri-etaireion-tropopoiitikos-ar-2-nomos-tou-2026/)
> **Σκοπός.** «Σκοπός του νομοσχεδίου είναι η τροποποίηση του περί Εταιρειών Νόμου για την ενσωμάτωση της Οδηγίας (ΕΕ) 2019/2121 όσον αφορά τις διασυνοριακές μετατροπές, συγχωνεύσεις και διασπάσεις.» — *"The purpose of the bill is to amend the Companies Law to transpose Directive (EU) 2019/2121 on cross-border conversions, mergers and divisions."*

Summary: the law has passed; awaiting publication in the Gazette and the text on CyLaw — then a separate item with the operative provisions.

## 2. In progress (bills)

**Ο περί Φορολογίας Κεφαλαιουχικών Κερδών (Τροποποιητικός) Νόμος του 2026** (Capital Gains Tax (Amendment) Law of 2026) — Πρόταση Νόμου, Αρ. Φακ. 23.02.067.081-2026, Committee on Financial and Budgetary Affairs · Tax, real estate
Event of the week: 10.09.2026 — discussed in committee. Status: Εκκρεμεί (pending). [Nomoplatform](https://www.nomoplatform.cy/bills/o-peri-forologias-kefalaiouchikon-kerdon-tropopoiitikos-nomos-tou-2026/)
> **Σκοπός.** «…να διορθωθούν στρεβλώσεις αναφορικά με την προθεσμία αποπεράτωσης της ανέγερσης οικοδομής στο πλαίσιο ανταλλαγής ακινήτων.» — *"…to correct distortions regarding the deadline for completing the construction of a building in the context of an exchange of immovable property."*

Summary: a private member's bill on the Capital Gains Tax Law — the completion deadline for buildings in property-exchange transactions. Submitted 14.07.2026.

**Ο περί Αλλοδαπών και Μεταναστεύσεως (Τροποποιητικός) (Αρ. 3) Νόμος του 2026** (Aliens and Immigration (Amendment) (No. 3) Law of 2026) — Νομοσχέδιο, Αρ. Φακ. 23.01.067.101-2026, Committee on Internal Affairs · Immigration
Event of the week: 09.09.2026 — submitted and referred to committee. Status: Εκκρεμεί.
> **Σκοπός.** «…να ρυθμιστεί η διαδικασία έκδοσης άδειας διαμονής σε υπηκόους τρίτων χωρών που εργοδοτούνται σε εταιρείες ξένων συμφερόντων.» — *"…to regulate the procedure for issuing residence permits to third-country nationals employed by companies of foreign interests."*

Summary: concerns the foreign-interest-company employment route; watch the text after the committee stage.

**Ο περί Ρυθμίσεως Οδών και Οικοδομών (Τροποποιητικός) (Αρ. 2) Νόμος του 2026** (Streets and Buildings Regulation (Amendment) (No. 2) Law of 2026) — Πρόταση Νόμου, Αρ. Φακ. 23.02.067.080-2026, Committee on Internal Affairs · Real estate
Event of the week: 08.09.2026 — discussed in committee. Status: Εκκρεμεί.
> **Σκοπός.** «…η αποτελεσματική διαχείριση των κινδύνων για τη δημόσια ασφάλεια και υγεία από επικίνδυνες οικοδομές σε αστικές περιοχές.» — *"…the effective management of risks to public safety and health from dangerous buildings in urban areas."*

Summary: dangerous buildings; for transactions — potential owner obligations, text not yet published.

Nomoplatform's "Αποφάσεις Ολομέλειας 11/09/2026": the Companies bill passed (see 1.3); consideration of the capital-gains amendment was postponed.

## 3. Regulators and departments

**Τμήμα Φορολογίας (Tax Department) — Ανακοίνωση για παράταση της ημερομηνίας υποβολής της Δήλωσης ΦΠΑ** (Announcement on the extension of the VAT return deadline) · 10.09.2026 · Tax · [gov.cy](https://www.gov.cy/oikonomia/anakoinosi-tou-tmimatos-forologias-gia-paratasi-fpa/)
> «…η ημερομηνία υποβολής της Δήλωσης ΦΠΑ και πληρωμής του οφειλόμενου ΦΠΑ για την περίοδο που έληξε στις 31/8/2026 παρατείνεται μέχρι τις 20/10/2026.» — *"…the deadline for filing the VAT return and paying the VAT due for the period ended 31/8/2026 is extended to 20/10/2026."*

Summary: VAT return and payment for the period ended 31.08.2026 are due by 20.10.2026.

**Τμήμα Εφόρου Εταιρειών (Registrar of Companies) — Επικαιροποίηση Μητρώου Πραγματικών Δικαιούχων 2026** (Update of the Register of Beneficial Owners 2026) · 10.09.2026 · Corporate · [companies.gov.cy](https://www.companies.gov.cy/gr/βάση-πληροφοριών/νέα/epikairopoiisi-mitroou-pragmatikon-dikaiouchon-2026)
> «…η ετήσια επιβεβαίωση των στοιχείων των πραγματικών δικαιούχων … πρέπει να ολοκληρωθεί μέχρι την 31η Δεκεμβρίου 2026.» — *"…the annual confirmation of beneficial-owner details … must be completed by 31 December 2026."*

Summary: the Registrar's reminder of the annual confirmation deadline; the notice's body states the penalty for non-compliance (€100 plus €50 per day of continuing breach — quoted from the notice, not from the law).

**Υπηρεσίες Κοινωνικών Ασφαλίσεων (Social Insurance Services) — παράταση για τη ρύθμιση Ληξιπρόθεσμων Κοινωνικών Εισφορών** (extension for the settlement of overdue contributions) · 11.09.2026 · Employment · [gov.cy](https://www.gov.cy/ergasia-kai-koinonikes-asfaliseis/anakoinosi-tis-ypiresias-koinonikon-asfaliseon-anaforika-me-tin-paratasi-gia-ti-rythmisi-lixiprothesmon-koinonikon-eisforon/)
Summary: the announcement of the same application period as Κ.Δ.Π. 329/2026 (until 31.10.2026).

**Central Bank of Cyprus — Amendment of the Directive on the Opening and Maintaining of Payment Accounts with Basic Features** · 10.09.2026 · Banking · [CBC](https://www.centralbank.cy/en/announcements/payment-accounts-directive-10-09-2026)
> "…the Directive (Amendment) of 2026 on the opening and maintaining of payment accounts with basic features, which enters into force on 1 November 2026. Credit institutions must decide on an application within ten business days."

Summary: banks must decide on an application for a basic payment account within 10 business days; from 01.11.2026. Practice note: a useful argument in banking referrals when account opening is refused or stalled.

## 4. Other laws of the week
- Ν. 126(I)/2026 — Ο περί Θήρας και Προστασίας Άγριων Πτηνών (Τροποποιητικός) Νόμος του 2026 (Game and Wild Birds (Amendment) Law) (11.09.2026)

## Verification
Checked: Ε.Ε. Παρ. Ι(Ι) — No. 5096 (11.09.2026); Παρ. ΙΙΙ(Ι) — Nos. 6044, 6045; CyLaw — up to Ν. 126(I)/2026; Nomoplatform, gov.cy, Registrar of Companies, CBC — as of 14.09.2026.
Dropped by the relevance filter: 8 items (CBC statistics, HR and IT notices, Κ.Δ.Π. on road safety and the environment).
