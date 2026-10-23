"""
Market-wide screen of stored IDX announcements for potential M&A / backdoor-listing and capital-raising events.

Works on filing titles only (no PDFs), so it can scan every company cheaply:

1. optionally bring the store up to date (incremental collection of the full feed);
2. tag each filing title with signals (negotiation, change of control, tender offer, rights issue, ...);
3. per ticker, score the *distinct* signals (a correction or a newspaper-ad copy of a filing never counts twice);
4. rank tickers in two lists — M&A / backdoor candidates and capital raising — and write markdown + JSON.

Candidates are leads, not findings: run ``idx dossier TICKER`` on the ones worth a closer look.
"""

import json
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date

from idx.core.utils import DATA_DIR, get_logger
from idx.pipelines.announcements import AnnouncementStore, collect

log = get_logger("idx.pipelines.screen")

SCREEN_DIR = os.path.join(DATA_DIR, "screens")


@dataclass(frozen=True)
class Signal:
    key: str
    label: str
    group: str  # "ma" | "capital" | "support"
    weight: int
    pattern: re.Pattern
    exclude: re.Pattern | None = None  # title matches pattern but is a known false positive


def _s(key, label, group, weight, pattern, exclude=None):
    return Signal(
        key, label, group, weight, re.compile(pattern, re.I), exclude and re.compile(exclude, re.I)
    )


# Checked in order; a title can carry several signals. Patterns were tuned on 120K filings (2025–2026).
SIGNALS: list[Signal] = [
    _s("TO", "tender offer", "ma", 4, r"tender\s*offer|penawaran tender"),
    _s(
        "CC",
        "change of control",
        "ma",
        4,
        r"perubahan (dalam |atas )?pengendali|pengendali baru|keterbukaan informasi tentang pengambil\s?alihan",
        exclude=r"tidak (menyebabkan|mengakibatkan) (terjadinya )?perubahan",
    ),
    _s(
        "NG",
        "takeover negotiation",
        "ma",
        3,
        r"negosiasi|calon pengendali|rencana pengambil\s?alihan",
        exclude=r"pasar negosiasi",
    ),
    _s(
        "SPA",
        "share purchase / transfer agreement",
        "ma",
        3,
        r"perjanjian (jual[- ]beli|pengalihan) saham|\bc?spa\b",
    ),
    _s("TK", "takeover / acquisition", "ma", 2, r"pengambil\s?alihan|akuisisi"),
    _s(
        "BC",
        "business change / name change",
        "ma",
        3,
        r"(perubahan|penambahan) kegiatan usaha|perubahan nama",
    ),
    _s(
        "INB",
        "inbreng (asset injection)",
        "ma",
        3,
        r"inbreng|penyetoran (modal )?dalam bentuk lain selain uang",
    ),
    # Most material-transaction filings are routine loans and contracts; business change (BC) is the strong signal.
    _s("MT", "material transaction", "ma", 1, r"transaksi material"),
    _s("MRG", "merger / consolidation / JV", "ma", 2, r"penggabungan usaha|peleburan|\bmerger\b"),
    _s(
        "GP",
        "go private / voluntary delisting",
        "ma",
        3,
        r"go private|perusahaan tertutup|penghapusan pencatatan saham secara sukarela|voluntary delisting",
    ),
    _s(
        "PP",
        "private placement (PMTHMETD)",
        "capital",
        2,
        r"tanpa\s+(memberikan\s+)?h(ak\s+memesan|metd)|pmthmetd|private placement",
    ),
    # Plain "Penyampaian Prospektus" is mostly bonds and IPOs, so only rights-issue wording counts.
    # "Tanpa HMETD" titles also match here; tag() keeps only PP for them.
    _s(
        "RI",
        "rights issue (PMHMETD)",
        "capital",
        2,
        r"hak memesan efek terlebih dahulu|\bp?mhmetd\b|\bhmetd\b|rights issue",
    ),
    _s("AFF", "affiliated transaction", "support", 1, r"transaksi afiliasi|benturan kepentingan"),
    _s(
        "EGM",
        "extraordinary / independent GMS",
        "support",
        1,
        r"luar biasa|rups\s*independen|pemegang saham independen",
    ),
    _s("IQ", "IDX inquiry reply", "support", 1, r"permintaan penjelasan"),
    _s(
        "VOL",
        "volatility / unusual market activity",
        "support",
        1,
        r"volatilitas|unusual market activity|\buma\b",
    ),
    _s("SUS", "trading suspension", "support", 1, r"penghentian sementara|suspensi"),
]
SIGNAL_BY_KEY = {s.key: s for s in SIGNALS}
OWNERSHIP = re.compile(r"(?i)laporan kepemilikan")
OWNERSHIP_HEAVY = 5  # this many 5% reports in the window counts as a support signal ("OWN")
# Copies of a filing (newspaper-ad proofs) and routine reports never carry a signal of their own.
SKIP = re.compile(r"(?i)bukti iklan|laporan bulanan registrasi|laporan keuangan|laporan tahunan")
STAGE_ORDER = ["NG", "SPA", "CC", "TO", "BC", "INB", "MRG", "GP"]  # later = further along


def tag(title: str) -> list[str]:
    """Signal keys found in a filing title."""
    if SKIP.search(title):
        return []
    keys = [
        s.key
        for s in SIGNALS
        if s.pattern.search(title) and not (s.exclude and s.exclude.search(title))
    ]
    if (
        "PP" in keys and "RI" in keys
    ):  # "Penambahan Modal Tanpa HMETD" is a placement, not a rights issue
        keys.remove("RI")
    return keys


@dataclass
class Candidate:
    ticker: str
    signals: set[str] = field(default_factory=set)
    first: str = ""
    last: str = ""
    filings: int = 0  # filings with at least one signal
    ownership_reports: int = 0
    key_titles: list[tuple[str, str, str]] = field(
        default_factory=list
    )  # (date, signal keys, title)

    def score(self, group: str) -> int:
        """Weight of distinct signals in `group`, plus support signals when the group has any."""
        own = sum(SIGNAL_BY_KEY[k].weight for k in self.signals if SIGNAL_BY_KEY[k].group == group)
        if not own:
            return 0
        support = sum(
            SIGNAL_BY_KEY[k].weight for k in self.signals if SIGNAL_BY_KEY[k].group == "support"
        )
        return own + support + (1 if self.ownership_reports >= OWNERSHIP_HEAVY else 0)

    def stage(self) -> str:
        reached = [k for k in STAGE_ORDER if k in self.signals]
        return SIGNAL_BY_KEY[reached[-1]].label if reached else ""


def screen_rows(rows, date_from: str, date_to: str | None = None) -> dict[str, Candidate]:
    """Aggregate signals per ticker for STOCK filings published in [date_from, date_to]."""
    out: dict[str, Candidate] = {}
    for r in rows:
        published = (r.get("publish_time") or "")[:10]
        ticker = r.get("ticker")
        if not ticker or published < date_from or (date_to and published > date_to):
            continue
        if r.get("jenis") not in (None, "STOCK"):
            continue
        title = r.get("title") or ""
        if OWNERSHIP.search(title):
            out.setdefault(ticker, Candidate(ticker)).ownership_reports += 1
            continue
        keys = tag(title)
        if not keys:
            continue
        c = out.setdefault(ticker, Candidate(ticker))
        c.signals.update(keys)
        c.filings += 1
        c.first = min(c.first or published, published)
        c.last = max(c.last, published)
        c.key_titles.append((published, "+".join(keys), title.strip()))
    return {t: c for t, c in out.items() if c.signals}


def _rank(cands: dict[str, Candidate], group: str) -> list[Candidate]:
    """Highest score first; ties broken by most recent activity."""
    picked = [c for c in cands.values() if c.score(group) > 0]
    picked.sort(key=lambda c: c.last, reverse=True)
    picked.sort(
        key=lambda c: c.score(group), reverse=True
    )  # stable: keeps newest-first within a score
    return picked


def _best_title(c: Candidate, group: str) -> str:
    """Latest title carrying the heaviest signal of the group."""

    def weight(keys: str) -> int:
        return max(
            (SIGNAL_BY_KEY[k].weight for k in keys.split("+") if SIGNAL_BY_KEY[k].group == group),
            default=0,
        )

    d, keys, title = max(c.key_titles, key=lambda t: (weight(t[1]), t[0]))
    return f"{d} {title[:90]}"


def render(
    cands: dict[str, Candidate], date_from: str, date_to: str, total_rows: int, top: int
) -> str:
    lines = [
        f"# IDX screen {date_from}..{date_to}",
        f"{total_rows} filings scanned (titles only); {len(cands)} tickers with at least one signal.",
        "Score = distinct signal weights (+1 per support signal: "
        + ", ".join(f"{s.key} {s.label}" for s in SIGNALS if s.group == "support")
        + f"; OWN = ≥{OWNERSHIP_HEAVY} 5% reports). Leads only: confirm with `idx dossier TICKER`.",
        "Codes: " + ", ".join(f"{s.key} {s.label}" for s in SIGNALS if s.group != "support") + ".",
    ]
    for group, heading in (("ma", "M&A / backdoor candidates"), ("capital", "Capital raising")):
        ranked = _rank(cands, group)
        lines += [
            "",
            f"## {heading} ({len(ranked)} tickers, top {min(top, len(ranked))})",
            "| # | ticker | score | signals | stage | first..last | n | key filing |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for i, c in enumerate(ranked[:top], 1):
            sig = " ".join(
                sorted(
                    c.signals,
                    key=lambda k: (SIGNAL_BY_KEY[k].group != group, -SIGNAL_BY_KEY[k].weight, k),
                )
            )
            if c.ownership_reports >= OWNERSHIP_HEAVY:
                sig += f" OWN×{c.ownership_reports}"
            stage = c.stage() if group == "ma" else ""
            lines.append(
                f"| {i} | {c.ticker} | {c.score(group)} | {sig} | {stage} | {c.first}..{c.last} | {c.filings} | {_best_title(c, group)} |"
            )
    return "\n".join(lines) + "\n"


def build_screen(
    date_from="2025-01-01", date_to=None, top=40, fetch=True, client=None, store=None
) -> str:
    store = store or AnnouncementStore()
    if fetch:
        collect(
            keywords="", download=False, client=client, store=store
        )  # incremental: full feed to today
    date_to = date_to or date.today().isoformat()
    total = 0

    def rows():
        nonlocal total
        for month_rows in store.iter_months():
            for r in month_rows:
                total += 1
                yield r

    cands = screen_rows(rows(), date_from, date_to)
    md = render(cands, date_from, date_to, total, top)

    os.makedirs(SCREEN_DIR, exist_ok=True)
    stem = os.path.join(SCREEN_DIR, f"screen_{date_from}_{date_to}")
    with open(stem + ".md", "w", encoding="utf-8") as f:
        f.write(md)
    with open(stem + ".json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "date_from": date_from,
                "date_to": date_to,
                "filings_scanned": total,
                "signals": {
                    s.key: {"label": s.label, "group": s.group, "weight": s.weight} for s in SIGNALS
                },
                "candidates": [
                    {
                        **{
                            k: v for k, v in asdict(c).items() if k not in ("signals", "key_titles")
                        },
                        "signals": sorted(c.signals),
                        "score_ma": c.score("ma"),
                        "score_capital": c.score("capital"),
                        "stage": c.stage(),
                        "key_titles": sorted(c.key_titles, reverse=True)[:20],
                    }
                    for c in sorted(
                        cands.values(), key=lambda c: -max(c.score("ma"), c.score("capital"))
                    )
                ],
            },
            f,
            ensure_ascii=False,
            indent=1,
        )
    log.info("Screen %s..%s: %d candidates → %s.md/.json", date_from, date_to, len(cands), stem)
    return md


def signal_counts(cands: dict[str, Candidate]) -> Counter:
    """How many tickers carry each signal (for quick sanity checks)."""
    return Counter(k for c in cands.values() for k in c.signals)
