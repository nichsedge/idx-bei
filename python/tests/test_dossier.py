"""
Offline tests for the filing digest (idx.pipelines.dossier). Texts are short excerpts shaped like real IDX filings.
"""

import idx.pipelines.dossier as dossier
from idx.pipelines.announcements import AnnouncementStore
from idx.pipelines.dossier import (
    Filing,
    _window,
    build_dossier,
    classify,
    key_sentences,
    mark_superseded,
    parse_ownership,
    restrict_newspaper,
    summarise_ownership,
)

COVER = (
    "Nomor Surat Nama Perusahaan Kode Emiten Lampiran Perihal 017/PSP/2026 PT Contoh Abadi Tbk ABCD 1 Perihal "
    "Go To English Page Dengan ini kami untuk dan atas nama perusahaan menyampaikan Laporan Informasi atau Fakta "
    "Material sebagai berikut: Nama Emiten atau Perusahaan Publik PT Contoh Abadi Tbk Bidang Usaha hotel "
    "Telepon : (021) 8790 5100 Tanggal Kejadian 22 April 2026 Jenis Informasi atau Fakta Material Negosiasi "
    "Uraian Informasi atau Fakta Material Calon Pengendali Baru berencana untuk membeli sebanyak 1.075.000.000 "
    "saham milik Para Penjual yang merupakan sekitar 86% dari seluruh saham Perseroan. "
    "Go To Indonesian Page The prospective controller plans to buy 1,075,000,000 shares of the Company."
)

OWNERSHIP_FORM = (
    "Nama (sesuai SID) : PUTRASAKTI MANDIRI Anggota Direksi/Dewan Komisaris : Tidak Jumlah Saham Sebelum "
    "Transaksi : 475.500.000,00 Unit Hak Suara Sebelum Transaksi : 38,039% Jumlah Saham Setelah Transaksi : "
    "448.000.000,00 Unit Hak Suara Setelah Transaksi : 35,839% Harga (Rp) Tanggal Transaksi Tujuan Transaksi "
    "Penjualan Ya Langsung - - - 10.493.200,00 Saham Biasa 522,00 22-Jul-2026 Restrukturisasi Kepemilikan Saham "
    "Penjualan Ya Langsung - - - 306.800,00 Saham Biasa 515,00 23-Jul-2026 Restrukturisasi Kepemilikan Saham "
    "Saya bertanggung jawab penuh Go To English Page Name ..."
)


def _row(i, date, title, urls=("u",)):
    return {
        "id": f"id{i}",
        "ticker": "ABCD",
        "title": title,
        "publish_time": f"{date}T10:00:00",
        "fetched_at": f"{date}T11:00:00+07:00",
        "attachments": [{"url": f"{u}{i}"} for u in urls],
        "raw": {},
    }


def test_classify():
    assert classify("Penyampaian Bukti Iklan Keterbukaan Informasi") is None
    assert classify("Laporan Bulanan Registrasi Pemegang Efek") is None
    assert classify("Keterbukaan Informasi Tentang Penawaran Tender Wajib") == "tender_offer"
    assert classify("Penambahan Modal Tanpa HMETD Hasil Pelaksanaan") == "private_placement"
    assert classify("Penyampaian Prospektus Ringkas Sehubungan Dengan PMHMETD I") == "rights_issue"
    assert classify("Pengumuman negosiasi rencana Pengambilalihan") == "takeover"
    assert classify("Rencana Transaksi Material Dengan Persetujuan RUPS") == "material_transaction"
    assert classify("LAPORAN KEPEMILIKAN ATAU SETIAP PERUBAHAN KEPEMILIKAN SAHAM") == "ownership"
    assert classify("Penjelasan atas Permintaan Penjelasan Bursa") == "exchange"
    assert classify("Pencatatan Saham") == "listing"
    assert classify("Hotel Baru Resmi Beroperasi") == "other"


def test_mark_superseded_only_by_corrections():
    a = Filing(_row(1, "2026-05-13", "Persetujuan Transaksi Material"), "material_transaction")
    b = Filing(
        _row(2, "2026-05-13", "Persetujuan Transaksi Material (KOREKSI)"), "material_transaction"
    )
    c = Filing(
        _row(3, "2026-05-22", "Persetujuan Transaksi Material (KOREKSI)"), "material_transaction"
    )
    own1 = Filing(_row(4, "2026-08-04", "LAPORAN KEPEMILIKAN"), "ownership")
    own2 = Filing(_row(5, "2026-08-05", "LAPORAN KEPEMILIKAN"), "ownership")
    mark_superseded([a, b, c, own1, own2])
    assert (a.superseded, b.superseded, c.superseded) == (True, True, False)
    assert c.originals == [b] and b.originals == [a]
    assert dossier._all_originals(c) == [b, a]
    assert not own1.superseded and not own2.superseded  # same title, not a correction


def test_key_sentences_filters_and_ranks():
    extra = (
        "PERSEROAN BERTANGGUNG JAWAB ATAS KEBENARAN SELURUH INFORMASI SEBESAR 100%. "
        "Mengoreksi surat kami nomor 029 tanggal 13 Mei 2026 perihal rencana transaksi. "
        "Nilai Transaksi Pengalihan Aset dan Usaha adalah sebesar Rp113.500.000.000 kepada pihak afiliasi. "
        "Rapat diadakan di hotel pada tanggal 22 Juni 2026 dan dihadiri pemegang saham. "
    )
    # Indonesian body sits between "Go To English Page" and "Go To Indonesian Page" (the English half).
    text = COVER.replace("Go To Indonesian Page", extra + "Go To Indonesian Page")
    seen: set[str] = set()
    got = key_sentences(text, ["PT Contoh Abadi Tbk"], seen, limit=2)
    assert len(got) == 2
    assert any("Rp113.500.000.000" in s for s in got)  # strong term + figure wins
    assert any("1.075.000.000" in s for s in got)
    assert all("Telepon" not in s and "Go To" not in s for s in got)  # boilerplate stripped
    assert all("prospective controller" not in s for s in got)  # English half dropped
    assert all("BERTANGGUNG" not in s and "Mengoreksi" not in s for s in got)
    assert got.index(next(s for s in got if "1.075" in s)) == 0  # document order
    # The same facts quoted again elsewhere are near-duplicates.
    assert key_sentences(text, [], seen, limit=2) == []


def test_restrict_newspaper_keeps_only_the_notice():
    page = (
        "NASIONAL 3 Jumat, 21 November 2025 Edisi: 12895 | Thn. 53 Kejaksaan menahan lima orang terkait akuisisi "
        "PT Lain senilai Rp1,25 triliun. Pengumuman. PT Contoh Abadi Tbk (Perseroan) menerima rencana "
        "pengambilalihan sebanyak 1.075.000.000 saham oleh calon pengendali baru."
    )
    kept = restrict_newspaper(page, ["PT Contoh Abadi Tbk"])
    assert "Kejaksaan" not in kept and "1.075.000.000" in kept
    assert restrict_newspaper("Surat biasa tanpa koran.", ["X"]) == "Surat biasa tanpa koran."
    assert restrict_newspaper(page, ["PT Tidak Ada Tbk"]) == ""


def test_window_centres_on_term_with_figure():
    long = (
        "Pendahuluan " * 40
        + "Nilai Transaksi adalah sebesar Rp113.500.000.000 untuk aset. "
        + "Penutup " * 40
    )
    w = _window(long)
    assert "Rp113.500.000.000" in w and len(w) <= dossier.MAX_SENTENCE_CHARS + 2


def test_parse_and_summarise_ownership():
    rep = parse_ownership(OWNERSHIP_FORM)
    assert rep["holder"] == "PUTRASAKTI MANDIRI"
    assert (rep["before_pct"], rep["after_pct"]) == (38.039, 35.839)
    assert [(t["side"], t["shares"], t["price"], t["date"]) for t in rep["trades"]] == [
        ("Penjualan", 10_493_200, 522, "22-Jul-2026"),
        ("Penjualan", 306_800, 515, "23-Jul-2026"),
    ]
    later = {
        **rep,
        "before_pct": 35.839,
        "after_pct": 31.99,
        "trades": [{**rep["trades"][0], "price": 409}],
    }
    [row] = summarise_ownership([("2026-07-29T00:00:00", rep), ("2026-09-29T00:00:00", later)])
    assert (row["from_pct"], row["to_pct"], row["reports"]) == (38.039, 31.99, 2)
    assert (row["price_min"], row["price_max"], row["bought"]) == (409, 522, 0)
    assert parse_ownership("not a KSEI form") is None


def test_build_dossier_end_to_end(tmp_path, monkeypatch):
    store = AnnouncementStore(str(tmp_path / "ann"))
    rows = [
        _row(1, "2026-04-24", "Perkembangan Negosiasi Rencana Pengambilalihan PT Contoh Abadi Tbk"),
        _row(2, "2026-05-13", "Penyampaian Informasi rencana Transaksi material"),
        _row(3, "2026-05-22", "Penyampaian Informasi rencana Transaksi material (KOREKSI)"),
        _row(4, "2026-07-29", "LAPORAN KEPEMILIKAN ATAU SETIAP PERUBAHAN KEPEMILIKAN SAHAM"),
        _row(5, "2026-08-10", "Laporan Bulanan Registrasi Pemegang Efek"),
        _row(6, "2026-09-30", "Pemberitahuan Rencana Rapat Umum Pemegang Saham Luar Biasa"),
        {
            **_row(7, "2026-09-30", "Pemberitahuan Rencana Rapat Umum Pemegang Saham Luar Biasa"),
            "attachments": [{"url": "u6"}],
        },
        _row(8, "2026-06-25", "Perubahan Pengurus"),
    ]
    for r in rows:
        store.add(r)
    texts = {
        "u1": COVER,
        "u2": "Nilai Transaksi Pengalihan Aset dan Usaha adalah sebesar Rp113.500.000.000 kepada PT Afiliasi.",
        "u3": None,  # correction is a scanned page → quote the original
        "u4": OWNERSHIP_FORM,
        "u6": None,
    }
    monkeypatch.setattr(dossier, "pdf_text", lambda store, client, url: texts.get(url))
    monkeypatch.setattr(dossier, "DOSSIER_DIR", str(tmp_path / "dossiers"))

    md = build_dossier("abcd", date_from="2026-01-01", fetch=False, client=object(), store=store)

    assert md.startswith("# ABCD dossier — PT Contoh Abadi Tbk")
    assert "8 total, 2 noise/duplicate, 1 superseded" in md
    assert "| PUTRASAKTI MANDIRI |" in md and "38.04% → 35.84%" in md
    assert md.index("## Ownership") < md.index("## Deal-relevant filings")
    assert "(original 2026-05-13) Nilai Transaksi" in md and "Rp113.500.000.000" in md
    assert "Rapat Umum Pemegang Saham Luar Biasa (scanned, not read)" in md
    assert md.count("Pemberitahuan Rencana Rapat Umum") == 1  # same document filed twice
    assert "[board] Perubahan Pengurus" in md  # titles only
    assert "Laporan Bulanan" not in md
    assert len(list((tmp_path / "dossiers").iterdir())) == 1


def test_budget_keeps_every_filing_title(tmp_path, monkeypatch):
    store = AnnouncementStore(str(tmp_path / "ann"))
    long_doc = " ".join(
        f"Nilai Transaksi tahap {i} adalah sebesar Rp{i}00.000.000.000 kepada pembeli."
        for i in range(1, 40)
    )
    for i in range(1, 6):
        store.add(_row(i, f"2026-0{i}-10", f"Rencana Transaksi Material tahap {i}"))
    monkeypatch.setattr(
        dossier, "pdf_text", lambda store, client, url: long_doc.replace("tahap", f"dok{url}")
    )
    monkeypatch.setattr(dossier, "DOSSIER_DIR", str(tmp_path / "d"))
    md = build_dossier(
        "ABCD", date_from="2026-01-01", max_chars=2500, fetch=False, client=object(), store=store
    )
    assert all(f"Rencana Transaksi Material tahap {i}" in md for i in range(1, 6))
    assert "more quotes omitted" in md
    assert len(md) <= 2600


# ---------- OCR ----------


def _scanned_pdf(path, lines):
    """An image-only PDF (no text layer), like a scanned IDX letter."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1700, 600), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=44)
    for i, line in enumerate(lines):
        draw.text((60, 60 + i * 90), line, fill="black", font=font)
    img.save(path, "PDF", resolution=200)
    with open(path, "rb") as f:
        return f.read()


def test_pdf_text_falls_back_to_ocr_and_caches(tmp_path, monkeypatch):
    store = AnnouncementStore(str(tmp_path / "ann"))
    content = _scanned_pdf(tmp_path / "scan.pdf", ["Surat"])
    store.save_attachment("u-scan", content, "application/pdf", "2026-10-23T00:00:00+07:00")
    calls = []

    def fake_ocr(path, max_pages=dossier.OCR_MAX_PAGES):
        calls.append(path)
        return "Calon Pengendali Baru membeli 1.075.000.000 saham atau 86% dari modal Perseroan."

    monkeypatch.setattr(dossier, "OCR_URLS", set())
    monkeypatch.setattr(dossier, "ocr_available", lambda: True)
    monkeypatch.setattr(dossier, "_ocr_pdf", fake_ocr)

    assert "1.075.000.000" in dossier.pdf_text(store, None, "u-scan")
    assert "1.075.000.000" in dossier.pdf_text(store, None, "u-scan")
    assert len(calls) == 1  # second read comes from the .ocr.txt cache
    assert "u-scan" in dossier.OCR_URLS

    monkeypatch.setattr(dossier, "ocr_available", lambda: False)
    store.save_attachment("u-scan2", content + b" ", "application/pdf", "2026-10-23T00:00:00+07:00")
    assert dossier.pdf_text(store, None, "u-scan2") is None


def test_dossier_marks_ocr_filings(tmp_path, monkeypatch):
    store = AnnouncementStore(str(tmp_path / "ann"))
    store.add(_row(1, "2026-04-24", "Negosiasi rencana Pengambilalihan PT Contoh Abadi Tbk"))
    monkeypatch.setattr(dossier, "OCR_URLS", {"u1"})
    monkeypatch.setattr(dossier, "pdf_text", lambda store, client, url: COVER)
    monkeypatch.setattr(dossier, "DOSSIER_DIR", str(tmp_path / "d"))
    md = build_dossier("ABCD", date_from="2026-01-01", fetch=False, client=object(), store=store)
    assert "Pengambilalihan PT Contoh Abadi Tbk (OCR)" in md
    assert "may contain recognition errors" in md


def test_real_ocr_reads_scanned_pdf(tmp_path):
    import pytest

    if not dossier.ocr_available():
        pytest.skip("tesseract not installed")
    path = tmp_path / "scan.pdf"
    _scanned_pdf(
        path,
        ["Pengambilalihan sebanyak 1.075.000.000 saham", "atau 86% dengan harga Rp75 per saham"],
    )
    text = dossier._ocr_pdf(str(path))
    assert "1.075.000.000" in text and "86%" in text and "Rp75" in text
