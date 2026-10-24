"""
Compact evidence digest ("dossier") of one ticker's IDX announcements.

Does the mechanical part of a deal check so a reader (human or LLM) only has to judge:

1. classify filings by title (takeover, tender offer, rights issue, ...) and drop noise
   (monthly registry reports, newspaper-ad proofs, financial statements);
2. keep only the latest of a filing and its "(KOREKSI)" corrections;
3. download PDFs only for deal-relevant filings and cache their text next to the PDF;
4. keep sentences that contain a deal term *and* a figure (Rp, %, share count, date), Indonesian only,
   and for newspaper-page attachments only the part around the company's own notice;
5. fold KSEI ownership-change forms (5% reports) into one row per holder;
6. render markdown within a character budget.

Scanned (image-only) PDFs are read with Tesseract OCR (Indonesian + English, first OCR_MAX_PAGES pages)
when it is installed; such filings are marked "(OCR)". Without Tesseract they are counted as unread.
"""

import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from pypdf import PdfReader

from idx.core.client import IDXClient
from idx.core.utils import DATA_DIR, get_logger
from idx.pipelines.announcements import AnnouncementStore, _now, collect

log = get_logger("idx.pipelines.dossier")

DOSSIER_DIR = os.path.join(DATA_DIR, "dossiers")

# Order matters: first match wins.
CATEGORIES: list[tuple[str, str]] = [
    ("tender_offer", r"tender"),
    (
        "private_placement",
        r"tanpa\s+(memberikan\s+)?h(ak\s+memesan|metd)|pmthmetd|private placement",
    ),
    ("rights_issue", r"hmetd|hak memesan efek|prospektus|rights issue"),
    (
        "takeover",
        r"pengambil\s?alihan|akuisisi|negosiasi|pengendali|pengendalian|jual beli|pengalihan saham",
    ),
    (
        "material_transaction",
        r"transaksi material|transaksi afiliasi|kegiatan usaha|inbreng|penggabungan|peleburan|pengalihan (aset|perjanjian|usaha)",
    ),
    ("ownership", r"laporan kepemilikan"),
    (
        "exchange",
        r"permintaan penjelasan|volatilitas|suspensi|penghentian sementara|unusual market|pemantauan khusus|notasi",
    ),
    ("gms", r"rapat umum|\brups"),
    ("board", r"pengurus|direksi|komisaris|corporate secretary|sekretaris perusahaan|komite"),
    ("listing", r"pencatatan"),
    ("proceeds", r"penggunaan dana"),
    ("dividend", r"dividen"),
]
NOISE = re.compile(
    r"(?i)bukti iklan|laporan bulanan registrasi|laporan keuangan|laporan tahunan|laporan keberlanjutan"
    r"|public expose|paparan publik|alamat|nomor telepon|website|surat keterangan lunas"
)
# Categories whose PDFs are read; the rest are listed by title only.
DEEP = {
    "tender_offer",
    "private_placement",
    "rights_issue",
    "takeover",
    "material_transaction",
    "exchange",
}
# Extraordinary / independent GMS notices are worth reading (agenda, results); annual ones are routine.
GMS_DEEP = re.compile(r"(?i)luar biasa|independen|penundaan")

# IDX e-reporting cover letters: header, issuer block and letterhead repeat in every filing.
BOILERPLATE = [
    re.compile(r"(?s)^.*?Go To English Page"),  # header before the Indonesian body
    re.compile(r"(?s)Go To Indonesian Page.*$"),  # English half
    re.compile(
        r"(?s)Dengan ini kami untuk dan atas nama perusahaan menyampaikan.*?(?=Tanggal Kejadian)"
    ),
    re.compile(r"(?i)Nama Emiten atau Perusahaan Publik.*?(?=Tanggal Kejadian|Jenis Informasi)"),
    re.compile(r"(?i)(Telp?\.?|Telepon|Fax|Faksimili)\s*:?\s*\(?\+?\d[\d\s()\-]{5,}"),
    re.compile(r"(?i)e-?mail\s*:?\s*\S+@\S+(\s*/\s*\S+@\S+)?"),
    # "Jenis Informasi ... <title again> Uraian Informasi atau Fakta Material" → keep only the date and the body
    re.compile(r"(?s)Jenis Informasi atau Fakta Material.*?Uraian Informasi atau Fakta Material"),
    re.compile(r"Uraian Informasi atau Fakta Material"),
]
# Sentences that only say "this corrects letter no. X", and share-capital tables, carry no deal facts.
# Letter headers ("Nomor : ... Kepada Yth ...") show up once scanned letters are OCR'd.
FILLER = re.compile(
    r"(?i)^(mengoreksi surat|dengan ini perseroan menyampaikan hal sebagaimana)|nilai nominal.{0,120}modal dasar"
    r"|kepada yth"
)
PRIORITY = {"takeover", "tender_offer", "material_transaction", "rights_issue", "private_placement"}
# Replies to IDX's questions often hold the key answers (valuation, funding); "volatility" replies rarely do.
PRIORITY_TITLE = re.compile(r"(?i)permintaan penjelasan")
IDX_FILES = "https://www.idx.co.id/StaticData/NewsAndAnnouncement/ANNOUNCEMENTSTOCK/"

DEAL_TERMS = re.compile(
    r"(?i)pengambil\s?alih|pengendali|tender|harga|per saham|sebanyak-banyaknya|nilai (transaksi|emisi|penawaran)"
    r"|rasio|hmetd|pembeli siaga|inbreng|afiliasi|kegiatan usaha|aset dan usaha|penjual|pembeli|perjanjian"
    r"|periode|jadwal|dilusi|penggunaan dana|ojk|ditunda|penundaan|menyetujui|mengangkat|memberhentikan"
    r"|ekuitas|pendapatan|laba|valuasi|penilaian|dcf|arus kas|modal dasar|modal ditempatkan|persen"
)
# Terms that mark the facts a deal judgement needs; weighted when ranking sentences.
STRONG_TERMS = re.compile(
    r"(?i)nilai transaksi|nilai emisi|nilai penawaran|harga (pengambilalihan|penawaran|pelaksanaan|pengalihan)"
    r"|per saham|afiliasi|calon pengendali|pengendali baru|pembeli siaga|inbreng|rasio|sebanyak-banyaknya"
    r"|penjual|pembeli|wajib melakukan pembayaran|pemegang saham utama|kegiatan usaha (baru|perseroan)"
    r"|estimasi nilai|nilai pengalihan|lebih tinggi dari|sumber dana|didirikan pada tanggal"
)
FIGURE = re.compile(
    r"Rp\s?[\d.,]{2,}|\d+(?:[.,]\d+)?\s?%|\b\d{1,3}(?:\.\d{3}){2,}\b|USD\s?[\d.,]+|US\$\s?[\d.,]+"
    r"|\b\d{1,2}\s+(?:januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember)\s+\d{4}",
    re.I,
)
ID_WORDS = re.compile(
    r"(?i)\b(yang|dan|dengan|untuk|dalam|sebesar|atas|pada|tersebut|perseroan|saham)\b"
)
EN_WORDS = re.compile(r"(?i)\b(the|of|and|which|with|shares|company|will|has|been|for)\b")
NEWSPAPER = re.compile(r"Edisi\s*:\s*\d+|\bThn\.\s*\d+")

MAX_SENTENCES_PER_FILING = 8
MAX_SENTENCE_CHARS = 320


@dataclass
class Filing:
    row: dict
    category: str
    superseded: bool = False
    originals: list["Filing"] = field(default_factory=list)  # filings this correction replaces
    snippets: list[str] = field(default_factory=list)
    needs_ocr: list[str] = field(default_factory=list)  # attachments with no text even after OCR
    ocr: bool = False  # some text came from OCR (may contain recognition errors)


def _all_originals(f: Filing) -> list[Filing]:
    """Filings replaced by this correction, newest first, following chains of corrections."""
    out: list[Filing] = []
    for orig in sorted(f.originals, key=lambda o: o.row["publish_time"], reverse=True):
        out += [orig, *_all_originals(orig)]
    return out


def classify(title: str) -> str | None:
    """Category for a filing title, or None for noise."""
    if NOISE.search(title):
        return None
    for name, pattern in CATEGORIES:
        if re.search(pattern, title, re.I):
            return name
    return "other"


def _base_title(title: str) -> str:
    return re.sub(r"\s*\(koreksi\)\s*$", "", title, flags=re.I).strip().lower()


def mark_superseded(filings: list[Filing], window_days: int = 14) -> None:
    """A filing is superseded by a later "(KOREKSI)" filing with the same base title within window_days.

    Repeated filings with identical titles (daily ownership reports, listing notices) are not corrections.
    """
    by_title: dict[str, list[Filing]] = defaultdict(list)
    for f in filings:
        by_title[_base_title(f.row["title"])].append(f)
    for group in by_title.values():
        group.sort(key=lambda f: f.row["publish_time"])
        for i, earlier in enumerate(group):
            for later in group[i + 1 :]:
                gap = date.fromisoformat(later.row["publish_time"][:10]) - date.fromisoformat(
                    earlier.row["publish_time"][:10]
                )
                if gap > timedelta(days=window_days):
                    break
                if re.search(r"\(koreksi\)", later.row["title"], re.I):
                    earlier.superseded = True
                    later.originals.append(earlier)
                    break


def is_indonesian(sentence: str) -> bool:
    return len(ID_WORDS.findall(sentence)) >= len(EN_WORDS.findall(sentence))


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text)
    # Split after ". " / "; " but not inside numbers like "1.075.000" or "Rp23,5".
    return [
        s.strip() for s in re.split(r"(?<=[a-z0-9\)\]])[.;]\s+(?=[A-Z0-9(])", text) if s.strip()
    ]


def strip_boilerplate(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    for pattern in BOILERPLATE:
        text = pattern.sub(" ", text)
    return text


def restrict_newspaper(text: str, anchors: list[str], radius: int = 2500) -> str:
    """For a scanned newspaper page, keep only the windows around the company's own notice."""
    if not NEWSPAPER.search(text):
        return text
    flat = re.sub(r"\s+", " ", text)
    spans = []
    for anchor in anchors:
        for m in re.finditer(re.escape(anchor), flat, re.I):
            # Start at the sentence containing the anchor, not in the preceding article.
            start = max(flat.rfind(". ", 0, m.start()) + 2, m.start() - 400, 0)
            spans.append((start, min(len(flat), m.end() + radius)))
    if not spans:
        return ""
    spans.sort()
    merged = [spans[0]]
    for s, e in spans[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return " … ".join(flat[s:e] for s, e in merged)


def _window(s: str) -> str:
    """Cut a long sentence to MAX_SENTENCE_CHARS around its first strong deal term (else its first figure)."""
    if len(s) <= MAX_SENTENCE_CHARS:
        return s
    strong = list(STRONG_TERMS.finditer(s))
    # Prefer a deal term followed closely by a figure ("Nilai Transaksi ... sebesar Rp113.500.000.000").
    m = next((t for t in strong if FIGURE.search(s, t.end(), t.end() + 150)), None)
    m = m or (strong[0] if strong else FIGURE.search(s))
    start = max(0, (m.start() if m else 0) - 60)
    start = min(start, len(s) - MAX_SENTENCE_CHARS)
    return ("…" if start else "") + s[start : start + MAX_SENTENCE_CHARS] + "…"


def _shingles(sentence: str) -> set[str]:
    words = re.findall(r"\w+", sentence.lower())
    return {" ".join(words[i : i + 3]) for i in range(max(1, len(words) - 2))}


def key_sentences(
    text: str, anchors: list[str], seen: set[str], limit: int = MAX_SENTENCES_PER_FILING
) -> list[str]:
    """Indonesian sentences with a deal term and a figure; near-duplicates of earlier ones are skipped.

    ``seen`` holds word trigrams of everything already quoted in the dossier.
    """
    if limit <= 0:
        return []
    candidates = []  # (score, position, sentence)
    for pos, s in enumerate(split_sentences(strip_boilerplate(restrict_newspaper(text, anchors)))):
        if (
            len(s) < 40
            or FILLER.search(s)
            or not (DEAL_TERMS.search(s) and FIGURE.search(s) and is_indonesian(s))
        ):
            continue
        letters = [c for c in s if c.isalpha()]
        if letters and sum(c.isupper() for c in letters) > 0.6 * len(letters):
            continue  # all-caps headings and legal disclaimers
        s = _window(s)
        # Strong deal terms dominate; figures count but are capped so number-dense tables don't win.
        score = 3 * len(STRONG_TERMS.findall(s)) + min(len(FIGURE.findall(s)), 3)
        candidates.append((score, pos, s))
    picked = []
    for _score, pos, s in sorted(candidates, key=lambda c: (-c[0], c[1])):
        grams = _shingles(s)
        if len(grams & seen) > 0.6 * len(grams):
            continue
        seen |= grams
        picked.append((pos, s))
        if len(picked) >= limit:
            break
    return [s for _, s in sorted(picked)]  # document order


# ---------- PDF text (cached next to the PDF) ----------


MIN_TEXT = 40  # fewer characters than this = no usable text layer
OCR_LANG = "ind+eng"
OCR_MAX_PAGES = 8  # scanned prospectuses can run to 50+ pages; the facts are almost always up front
OCR_DPI = 200
OCR_ENABLED = True  # set False (CLI --no-ocr) to skip OCR
OCR_URLS: set[str] = set()  # attachments whose text came from OCR in this process


def ocr_available() -> bool:
    if not OCR_ENABLED:
        return False
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_pdf(pdf_path: str, max_pages: int = OCR_MAX_PAGES) -> str:
    """Render the first pages with pdfium and read them with Tesseract (Indonesian + English)."""
    import pypdfium2 as pdfium
    import pytesseract

    pdf = pdfium.PdfDocument(pdf_path)
    try:
        pages = []
        for i in range(min(len(pdf), max_pages)):
            image = pdf[i].render(scale=OCR_DPI / 72).to_pil()
            pages.append(pytesseract.image_to_string(image, lang=OCR_LANG))
        if len(pdf) > max_pages:
            pages.append(f"[OCR stopped after {max_pages} of {len(pdf)} pages]")
        return "\n".join(pages)
    finally:
        pdf.close()


def pdf_text(store: AnnouncementStore, client, url: str) -> str | None:
    """Text of an attachment, downloading it if needed.

    Falls back to OCR for scanned PDFs (text cached as ``<sha>.ocr.txt``; the URL is added to OCR_URLS).
    None when there is no text layer and OCR is unavailable or finds nothing.
    """
    rec = store.attachment(url)
    if rec is None:
        response = client.get(url)
        if response is None or response.status_code != 200:
            log.warning("Attachment download failed: %s", url)
            return None
        rec = store.save_attachment(
            url, response.content, response.headers.get("content-type"), _now()
        )
    pdf_path = os.path.join(store.base_dir, rec["path"])
    txt_path = os.path.splitext(pdf_path)[0] + ".txt"
    if os.path.exists(txt_path):
        with open(txt_path, encoding="utf-8") as f:
            text = f.read()
    else:
        try:
            text = "\n".join((p.extract_text() or "") for p in PdfReader(pdf_path).pages)
        except Exception as exc:  # broken PDF
            log.warning("Text extraction failed for %s: %s", url, exc)
            text = ""
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)
    if len(text.strip()) >= MIN_TEXT:
        return text

    ocr_path = os.path.splitext(pdf_path)[0] + ".ocr.txt"
    if os.path.exists(ocr_path):
        with open(ocr_path, encoding="utf-8") as f:
            text = f.read()
    elif ocr_available():
        try:
            text = _ocr_pdf(pdf_path)
        except Exception as exc:  # unreadable image, tesseract crash
            log.warning("OCR failed for %s: %s", url, exc)
            return None
        with open(ocr_path, "w", encoding="utf-8") as f:
            f.write(text)
        log.info("OCR %s: %d chars", url, len(text))
    else:
        return None
    if len(text.strip()) < MIN_TEXT:
        return None
    OCR_URLS.add(url)
    return text


# ---------- KSEI ownership forms ----------

OWN_NAME = re.compile(r"Nama \(sesuai SID\)\s*:\s*(.+?)\s+Anggota")
OWN_BEFORE = re.compile(r"Hak Suara Sebelum Transaksi\s*:\s*([\d.,]+)\s*%")
OWN_AFTER = re.compile(r"Hak Suara Setelah Transaksi\s*:\s*([\d.,]+)\s*%")
OWN_TRADE = re.compile(
    r"(Pembelian|Penjualan)\s+(?:Ya\s+|Tidak\s+)?(?:Langsung|Tidak Langsung)\s+(?:-\s+)*([\d.]+,\d{2})\s+Saham\s+\w+\s+"
    r"([\d.]+,\d{2})\s+(\d{2}-\w{3}-\d{4})\s+(.{0,80}?)(?=\s+(?:Pembelian|Penjualan|Saya|Nama|$))"
)


def _num(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def parse_ownership(text: str) -> dict | None:
    flat = re.sub(r"\s+", " ", text.split("Go To English Page")[0])
    name, before, after = OWN_NAME.search(flat), OWN_BEFORE.search(flat), OWN_AFTER.search(flat)
    if not (name and before and after):
        return None
    trades = [
        {
            "side": m[1],
            "shares": _num(m[2]),
            "price": _num(m[3]),
            "date": m[4],
            "purpose": m[5].strip(),
        }
        for m in OWN_TRADE.finditer(flat)
    ]
    return {
        "holder": name[1].strip(),
        "before_pct": _num(before[1]),
        "after_pct": _num(after[1]),
        "trades": trades,
    }


def summarise_ownership(reports: list[tuple[str, dict]]) -> list[dict]:
    """One row per holder: first → last stake, buy/sell share totals, price range, purposes."""
    by_holder: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for published, rep in reports:
        by_holder[rep["holder"]].append((published, rep))
    rows = []
    for holder, items in by_holder.items():
        items.sort(key=lambda x: x[0])
        trades = [t for _, r in items for t in r["trades"]]
        prices = [t["price"] for t in trades if t["price"] > 0]
        rows.append(
            {
                "holder": holder,
                "first": items[0][0][:10],
                "last": items[-1][0][:10],
                "from_pct": items[0][1]["before_pct"],
                "to_pct": items[-1][1]["after_pct"],
                "bought": sum(t["shares"] for t in trades if t["side"] == "Pembelian"),
                "sold": sum(t["shares"] for t in trades if t["side"] == "Penjualan"),
                "price_min": min(prices) if prices else None,
                "price_max": max(prices) if prices else None,
                "purposes": sorted({t["purpose"] for t in trades if t["purpose"]})[:2],
                "reports": len(items),
            }
        )
    return sorted(rows, key=lambda r: -abs(r["to_pct"] - r["from_pct"]))


# ---------- dossier ----------


def company_name(texts: list[str], ticker: str) -> str | None:
    names: Counter[str] = Counter()
    for t in texts:
        for m in re.finditer(r"\b(PT\.?\s+[A-Z][A-Za-z.&'\- ]{2,60}?\s+Tbk)\b", t):
            names[re.sub(r"\s+", " ", m[1]).replace("PT. ", "PT ")] += 1
    return names.most_common(1)[0][0] if names else None


def build_dossier(
    ticker,
    date_from=None,
    max_chars=20000,
    fetch=True,
    client=None,
    store=None,
):
    """Collect (optional), digest and render one ticker's filings. Returns the markdown text."""
    ticker = ticker.strip().upper()
    client = client or IDXClient()
    store = store or AnnouncementStore()
    if fetch:
        collect(
            keywords=ticker,
            date_from=date_from or "20250101",
            download=False,
            client=client,
            store=store,
        )

    start = (date_from or "2025-01-01").replace("-", "")
    start = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
    rows = sorted(
        (
            r
            for r in store.iter_rows()
            if r.get("ticker") == ticker and (r.get("publish_time") or "") >= start
        ),
        key=lambda r: r["publish_time"],
    )
    noise = 0
    filings: list[Filing] = []
    seen_docs: set[str] = set()
    for r in rows:
        first_url = r["attachments"][0]["url"] if r["attachments"] else r["id"]
        if first_url in seen_docs:  # same document filed twice
            noise += 1
            continue
        seen_docs.add(first_url)
        cat = classify(r["title"])
        if cat is None:
            noise += 1
        else:
            filings.append(Filing(r, cat))
    mark_superseded(filings)
    live = [f for f in filings if not f.superseded]

    # Read PDFs of the filings that matter; ownership forms are parsed, not quoted.
    texts_for_name: list[str] = []
    ownership: list[tuple[str, dict]] = []
    unparsed_ownership = 0
    to_read = [
        f
        for f in live
        if f.category in DEEP or (f.category == "gms" and GMS_DEEP.search(f.row["title"]))
    ]
    raw: dict[int, list[str]] = {}
    for f in to_read + [f for f in live if f.category == "ownership"]:
        texts = []
        for att in f.row["attachments"]:
            text = pdf_text(store, client, att["url"])
            if text is None:
                f.needs_ocr.append(att["url"])
            else:
                texts.append(text)
                f.ocr = f.ocr or att["url"] in OCR_URLS
        raw[id(f)] = texts
        if f.category == "ownership":
            reps = [parse_ownership(t) for t in texts]
            parsed = [p for p in reps if p]
            ownership += [(f.row["publish_time"], p) for p in parsed]
            unparsed_ownership += not parsed
        else:
            texts_for_name += texts[:1]

    name = company_name(texts_for_name, ticker)
    anchors = [a for a in (name, name and name.replace(" Tbk", "").upper(), ticker) if a]
    seen: set[str] = set()
    for f in to_read:
        for text in raw[id(f)]:
            f.snippets += key_sentences(
                text, anchors, seen, MAX_SENTENCES_PER_FILING - len(f.snippets)
            )
        # A correction that is scanned or says only "we correct letter X": quote the original instead.
        for orig in _all_originals(f) if len(f.snippets) < 2 else []:
            for att in orig.row["attachments"]:
                text = pdf_text(store, client, att["url"])
                if text:
                    found = key_sentences(
                        text, anchors, seen, MAX_SENTENCES_PER_FILING - len(f.snippets)
                    )
                    f.snippets += [f"(original {orig.row['publish_time'][:10]}) {s}" for s in found]
                    f.ocr = f.ocr or bool(found and att["url"] in OCR_URLS)

    md = render(
        ticker,
        name,
        start,
        rows,
        noise,
        filings,
        live,
        to_read,
        ownership,
        unparsed_ownership,
        max_chars,
    )
    os.makedirs(DOSSIER_DIR, exist_ok=True)
    out_path = os.path.join(DOSSIER_DIR, f"{ticker}_{date.today():%Y%m%d}.md")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(md)
    log.info("Dossier for %s: %d chars → %s", ticker, len(md), out_path)
    return md


def _pct(x):
    return f"{x:.2f}%".replace(".00%", "%")


def render(
    ticker,
    name,
    start,
    rows,
    noise,
    filings,
    live,
    to_read,
    ownership,
    unparsed_ownership,
    max_chars,
):
    end = rows[-1]["publish_time"][:10] if rows else "—"
    lines = [
        f"# {ticker} dossier — {name or 'company name not found'}",
        f"Filings {start}..{end}: {len(rows)} total, {noise} noise/duplicate, {sum(f.superseded for f in filings)} "
        f"superseded by corrections, {len(to_read)} read. Quotes: sentences with a deal term and a figure, "
        f"Indonesian only. Links are relative to {IDX_FILES}",
    ]
    # Ownership first: compact and must survive truncation.
    if ownership:
        lines += [
            "",
            "## Ownership changes (KSEI 5% reports)",
            "| holder | first | last | stake | bought | sold | price Rp | purpose | n |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for o in summarise_ownership(ownership):
            if o["price_min"] is None:
                price = "—"
            elif o["price_min"] == o["price_max"]:
                price = f"{o['price_min']:g}"
            else:
                price = f"{o['price_min']:g}–{o['price_max']:g}"
            lines.append(
                f"| {o['holder']} | {o['first']} | {o['last']} | {_pct(o['from_pct'])} → {_pct(o['to_pct'])} | "
                f"{o['bought']:,.0f} | {o['sold']:,.0f} | {price} | {'; '.join(o['purposes'])[:60]} | {o['reports']} |"
            )
    if unparsed_ownership:
        lines.append(f"\n{unparsed_ownership} ownership report(s) could not be parsed.")

    deal_section_at = len(lines)
    deal = sorted(to_read, key=lambda f: f.row["publish_time"])
    other = [f for f in live if f not in to_read and f.category != "ownership"]
    if other:
        lines += ["", "## Other filings (titles only)"]
        by_cat: dict[str, list[Filing]] = defaultdict(list)
        for f in other:
            by_cat[f.category].append(f)
        for cat, items in by_cat.items():
            if len(items) > 4:
                titles = Counter(_base_title(f.row["title"])[:60] for f in items).most_common(3)
                lines.append(
                    f"- {cat} ×{len(items)} ({items[0].row['publish_time'][:10]}..{items[-1].row['publish_time'][:10]}): "
                    + "; ".join(f"{t} ×{n}" for t, n in titles)
                )
            else:
                lines += [
                    f"- {f.row['publish_time'][:10]} [{cat}] {f.row['title'][:120]}" for f in items
                ]

    unread = sum(len(f.needs_ocr) for f in live if f.category != "ownership")
    ocr_read = sum(f.ocr for f in live)
    if ocr_read:
        lines += [
            "",
            f"{ocr_read} filing(s) marked (OCR) were read from scans; quotes may contain recognition errors.",
        ]
    if unread:
        reason = "OCR found no text" if ocr_available() else "OCR not available"
        lines += ["", f"{unread} scanned attachment(s) could not be read ({reason})."]

    # Every deal filing keeps its title line; quotes are shared round-robin within the remaining budget,
    # so one long disclosure cannot crowd out later events.
    heads = []
    for f in deal:
        r = f.row
        url = (r["attachments"][0]["url"] if r["attachments"] else "").replace(IDX_FILES, "")
        mark = (
            " (scanned, not read)"
            if f.needs_ocr and not f.snippets
            else (" (OCR)" if f.ocr else "")
        )
        heads.append(f"- {r['publish_time'][:10]} [{f.category}] {r['title'][:140]}{mark} <{url}>")
    fixed = sum(len(x) + 1 for x in lines + heads) + 40
    budget = max_chars - fixed
    taken = [0] * len(deal)
    progress = True
    while progress:
        progress = False
        for i, f in enumerate(deal):
            # Deal-term filings (takeover, tender, material transaction, rights) get 3 quotes per round.
            for _ in range(
                3 if f.category in PRIORITY or PRIORITY_TITLE.search(f.row["title"]) else 1
            ):
                if taken[i] >= len(f.snippets):
                    break
                cost = len(f.snippets[taken[i]]) + 5
                if cost > budget:
                    break
                budget -= cost
                taken[i] += 1
                progress = True
    dropped = sum(len(f.snippets) - t for f, t in zip(deal, taken, strict=True))

    section = ["", "## Deal-relevant filings"]
    for head, f, t in zip(heads, deal, taken, strict=True):
        section.append(head)
        section += [f"  - {s}" for s in f.snippets[:t]]
    if dropped:
        section.append(
            f"\n({dropped} more quotes omitted for the {max_chars}-char budget; raise --max-chars.)"
        )
    lines[deal_section_at:deal_section_at] = section
    return "\n".join(lines) + "\n"
