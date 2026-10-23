"""
Offline tests for the market-wide title screen (idx.pipelines.screen). Titles are real IDX filing titles.
"""

import json

import idx.pipelines.screen as screen
from idx.pipelines.announcements import AnnouncementStore
from idx.pipelines.screen import build_screen, screen_rows, tag


def _row(i, ticker, date, title, jenis="STOCK"):
    return {
        "id": f"id{i}",
        "ticker": ticker,
        "title": title,
        "publish_time": f"{date}T09:00:00",
        "jenis": jenis,
        "attachments": [],
    }


def test_tag_signals_and_false_positives():
    assert tag("Keterbukaan Informasi Tentang Penawaran Tender Wajib") == ["TO"]
    assert set(tag("Keterbukaan Informasi Tentang Pengambilalihan")) == {"CC", "TK"}
    assert "CC" in tag(
        "Perubahan dalam pengendalian baik langsung maupun tidak langsung terhadap Emiten"
    )
    assert "NG" in tag(
        "Pengumuman negosiasi sebagaimana dimaksud dalam Peraturan No. 9/POJK.04/2018"
    )
    assert "SPA" in tag("Penandatanganan Perjanjian Jual Beli Saham Bersyarat")
    assert "BC" in tag("Rencana Transaksi Perubahan Kegiatan Usaha")
    assert tag("Penambahan Modal Tanpa HMETD Hasil Pelaksanaan Penambahan Modal Tanpa HMETD") == [
        "PP"
    ]
    assert tag(
        "Keterbukaan Informasi terkait Aksi Korporasi - Rencana Penambahan Modal dengan HMETD"
    ) == ["RI"]
    # Known false positives
    assert "NG" not in tag(
        "Pencabutan Penghentian Sementara Perdagangan Efek Hanya di Pasar Negosiasi PT X Tbk"
    )
    assert "CC" not in tag(
        "PT Ecocare Indo Pasifik Tbk, penyedia jasa hygiene, sanitasi, dan pengendalian hama"
    )
    assert "CC" not in tag(
        "Transaksi pengalihan saham oleh pemegang saham pengendali yang tidak menyebabkan perubahan pengendalian"
    )
    assert tag("Penyampaian Prospektus") == []  # bonds / IPOs, not a rights issue
    assert tag("Penyampaian Bukti Iklan Keterbukaan Informasi Tentang Penawaran Tender Wajib") == []
    assert tag("Laporan Bulanan Registrasi Pemegang Efek") == []


def test_screen_rows_scores_distinct_signals():
    rows = [
        _row(1, "AAAA", "2026-04-24", "Negosiasi rencana Pengambilalihan PT Aaaa Tbk"),
        _row(
            2,
            "AAAA",
            "2026-08-20",
            "Informasi atau fakta material sehubungan dengan perubahan pengendalian terhadap Perseroan",
        ),
        _row(3, "AAAA", "2026-10-02", "Keterbukaan Informasi Tentang Penawaran Tender Wajib"),
        _row(
            4,
            "AAAA",
            "2026-10-03",
            "Keterbukaan Informasi Tentang Penawaran Tender Wajib (KOREKSI)",
        ),  # same signal again
        _row(5, "AAAA", "2026-10-20", "Penjelasan atas Permintaan Penjelasan Bursa"),
        _row(6, "BBBB", "2026-09-14", "Keterbukaan Informasi terkait Aksi Korporasi - HMETD"),
        _row(7, "BBBB", "2026-09-20", "Penjelasan atas Volatilitas Transaksi"),
        _row(
            8, "CCCC", "2026-05-01", "Penjelasan atas Volatilitas Transaksi"
        ),  # support only → not a candidate
        _row(
            9, "DDDD", "2024-12-31", "Keterbukaan Informasi Tentang Penawaran Tender Wajib"
        ),  # before window
        _row(
            10,
            "EEEE",
            "2026-01-05",
            "Keterbukaan Informasi Tentang Penawaran Tender Wajib",
            jenis="BOND",
        ),
    ] + [
        _row(
            100 + i,
            "BBBB",
            "2026-08-01",
            "LAPORAN KEPEMILIKAN ATAU SETIAP PERUBAHAN KEPEMILIKAN SAHAM",
        )
        for i in range(5)
    ]

    cands = screen_rows(rows, "2025-01-01")
    a, b = cands["AAAA"], cands["BBBB"]
    # NG 3 + CC 4 + TO 4 + TK 2 (from "Pengambilalihan") + IQ 1
    assert a.score("ma") == 3 + 4 + 4 + 2 + 1
    assert a.score("capital") == 0
    assert a.stage() == "tender offer"
    assert (a.first, a.last, a.filings) == ("2026-04-24", "2026-10-20", 5)
    # RI 2 + VOL 1 + OWN (5 ownership reports) 1
    assert b.score("capital") == 2 + 1 + 1 and b.score("ma") == 0
    assert b.ownership_reports == 5
    assert "CCCC" in cands and cands["CCCC"].score("ma") == cands["CCCC"].score("capital") == 0
    assert "DDDD" not in cands and "EEEE" not in cands


def test_build_screen_renders_ranked_lists(tmp_path, monkeypatch):
    store = AnnouncementStore(str(tmp_path / "ann"))
    for r in [
        _row(1, "LOWW", "2026-03-01", "Rencana Transaksi Perubahan Kegiatan Usaha"),
        _row(2, "HIGH", "2026-04-24", "Negosiasi rencana Pengambilalihan PT High Tbk"),
        _row(3, "HIGH", "2026-10-02", "Keterbukaan Informasi Tentang Penawaran Tender Wajib"),
        _row(4, "RITE", "2026-09-14", "Rencana Penambahan Modal dengan HMETD"),
        _row(5, "TIE1", "2026-01-10", "Rencana Transaksi Perubahan Kegiatan Usaha"),
    ]:
        store.add(r)
    monkeypatch.setattr(screen, "SCREEN_DIR", str(tmp_path / "screens"))

    md = build_screen(
        date_from="2026-01-01", date_to="2026-10-23", top=10, fetch=False, store=store
    )

    ma = md.split("## M&A")[1].split("## Capital")[0]
    assert (
        ma.index("| HIGH |") < ma.index("| LOWW |") < ma.index("| TIE1 |")
    )  # score, then most recent
    assert (
        "tender offer" in ma
        and "2026-10-02 Keterbukaan Informasi Tentang Penawaran Tender Wajib" in ma
    )
    cap = md.split("## Capital")[1]
    assert "| RITE |" in cap and "| HIGH |" not in cap
    assert "5 filings scanned" in md
    data = json.loads(
        (tmp_path / "screens" / "screen_2026-01-01_2026-10-23.json").read_text(encoding="utf-8")
    )
    assert (
        data["candidates"][0]["ticker"] == "HIGH"
        and data["candidates"][0]["stage"] == "tender offer"
    )
