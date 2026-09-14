"""
LHKPN & Politically Exposed Persons (PEP) Radar Engine.

Cross-references Indonesian public officials' wealth disclosures (LHKPN)
against IDX listed companies' Board of Directors, Commissioners, and Major Shareholders (>5%).
"""

import json
import re
from pathlib import Path
from typing import Any

from idx.core.utils import DATA_DIR, get_logger

log = get_logger("idx.lhkpn_radar")

# High-profile PEPs & known conglomerate / listed company governance ties
KNOWN_PEP_NETWORKS = {
    "PRABOWO SUBIANTO": {
        "role": "Presiden RI",
        "institution": "Pemerintah RI",
        "family_ties": ["Hashim Djojohadikusumo", "Thomas Djiwandono"],
        "affiliated_tickers": ["ARII", "DEWA"],
        "notes": "Arsari Group & political family affiliations in mining/agri.",
    },
    "LUHUT BINSAR PANDJAITAN": {
        "role": "Ketua Dewan Ekonomi Nasional / Eks Menko Marves",
        "institution": "Pemerintah RI",
        "family_ties": ["Pandjaitan"],
        "affiliated_tickers": ["TOBA"],
        "notes": "Founder / major beneficial controller of PT TBS Energi Utama Tbk.",
    },
    "ERICK THOHIR": {
        "role": "Menteri BUMN",
        "institution": "Kementerian BUMN",
        "family_ties": ["Garibaldi Thohir", "Boy Thohir"],
        "affiliated_tickers": ["ADRO", "AADI", "MBMA", "ESSA"],
        "notes": "Thohir family conglomerate holdings via Adaro, Merdeka Battery, Essa.",
    },
    "SANDIAGA UNO": {
        "role": "Eks Menparekraf",
        "institution": "Pemerintah RI",
        "family_ties": ["Nur Asia Uno"],
        "affiliated_tickers": ["SRTG", "MDKA", "TBIG", "MPMX"],
        "notes": "Co-founder of PT Saratoga Investama Sedaya Tbk.",
    },
    "AIRLANGGA HARTARTO": {
        "role": "Menko Perekonomian",
        "institution": "Kemenko Perekonomian",
        "family_ties": ["Hartarto"],
        "affiliated_tickers": ["CITA"],
        "notes": "Family connections in natural resources and industrial holdings.",
    },
    "HAMID AWALUDDIN": {
        "role": "Eks Menkumham / Duta Besar",
        "institution": "Kementerian Hukum & HAM",
        "family_ties": [],
        "affiliated_tickers": ["ARCI", "DOID", "ESSA", "OKAS", "SINI"],
        "notes": "Independent Commissioner across 5 prominent IDX listed issuers.",
    },
}


def clean_name(name: str) -> str:
    """Standardize person name by removing academic/honorific titles and punctuation."""
    if not name:
        return ""
    n = name.upper()
    n = re.sub(r"[,\.]", "", n)
    n = re.sub(
        r"\b(DR|DRS|DRA|PROF|IR|H|HJ|SH|SE|MM|MBA|MSC|PHD|AK|BBA|BSC|MH|ST|SSI|SKOM|BA)\b", "", n
    )
    return " ".join(n.split())


class LHKPNRadar:
    """Cross-references LHKPN wealth filings with IDX listed companies."""

    def __init__(self, lhkpn_dir: Path | None = None, data_dir: Path | None = None):
        self.data_dir = data_dir or Path(DATA_DIR)
        self.lhkpn_dir = lhkpn_dir or Path(__file__).resolve().parents[5] / "lhkpn"
        self._company_details: dict[str, Any] = {}
        self._lhkpn_filings: list[dict[str, Any]] = []

    def load_company_details(self) -> dict[str, Any]:
        """Load detailed profiles of all IDX listed issuers."""
        if not self._company_details:
            details_path = self.data_dir / "companyDetailsByKodeEmiten.json"
            if details_path.exists():
                try:
                    self._company_details = json.loads(details_path.read_text(encoding="utf-8"))
                except Exception as e:
                    log.warning("Failed to load companyDetailsByKodeEmiten.json: %s", e)
        return self._company_details

    def load_lhkpn_filings(self) -> list[dict[str, Any]]:
        """Load all available LHKPN JSON filings from lhkpn project."""
        if not self._lhkpn_filings and self.lhkpn_dir.exists():
            for json_file in self.lhkpn_dir.glob("*.json"):
                if json_file.name == "package.json":
                    continue
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        self._lhkpn_filings.extend(data)
                    elif isinstance(data, dict) and "data" in data:
                        self._lhkpn_filings.extend(data["data"])
                except Exception as e:
                    log.warning("Could not read LHKPN file %s: %s", json_file.name, e)
        return self._lhkpn_filings

    def scan_pep_overlaps(self, query: str | None = None) -> list[dict[str, Any]]:
        """Scan for Politically Exposed Persons (PEPs) holding governance or equity in IDX stocks."""
        details = self.load_company_details()
        filings = self.load_lhkpn_filings()

        # Build index of IDX board members and shareholders
        idx_index: dict[str, list[dict[str, str]]] = {}
        for ticker, comp in details.items():
            comp_name = (
                comp.get("Profiles", [{}])[0].get("NamaEmiten", ticker)
                if comp.get("Profiles")
                else ticker
            )

            for d in comp.get("DewanDireksi", []):
                name = d.get("Nama", "")
                c = clean_name(name)
                if c:
                    idx_index.setdefault(c, []).append(
                        {
                            "ticker": ticker,
                            "company_name": comp_name,
                            "role": f"Direksi ({d.get('Jabatan', 'Direktur')})",
                            "raw_name": name,
                        }
                    )

            for k in comp.get("DewanKomisaris", []):
                name = k.get("Nama", "")
                c = clean_name(name)
                if c:
                    idx_index.setdefault(c, []).append(
                        {
                            "ticker": ticker,
                            "company_name": comp_name,
                            "role": f"Komisaris ({k.get('Jabatan', 'Komisaris')})",
                            "raw_name": name,
                        }
                    )

            for s in comp.get("PemegangSaham", []):
                name = s.get("Nama", "")
                c = clean_name(name)
                if c:
                    pct = s.get("Persentase", 0)
                    idx_index.setdefault(c, []).append(
                        {
                            "ticker": ticker,
                            "company_name": comp_name,
                            "role": f"Pemegang Saham ({pct}%)",
                            "raw_name": name,
                        }
                    )

        results: list[dict[str, Any]] = []

        # 1. Match curated high-profile PEP networks
        for pep_name, info in KNOWN_PEP_NETWORKS.items():
            if (
                query
                and query.upper() not in pep_name
                and not any(query.upper() in t for t in info["affiliated_tickers"])
            ):
                continue

            matches = []
            for ticker in info["affiliated_tickers"]:
                comp = details.get(ticker, {})
                comp_name = (
                    comp.get("Profiles", [{}])[0].get("NamaEmiten", ticker)
                    if comp.get("Profiles")
                    else ticker
                )
                matches.append(
                    {
                        "ticker": ticker,
                        "company_name": comp_name,
                        "role": "Affiliated / Major Beneficial Owner",
                        "raw_name": pep_name,
                    }
                )

            results.append(
                {
                    "official_name": pep_name,
                    "role": info["role"],
                    "institution": info["institution"],
                    "total_harta": "Declared in LHKPN",
                    "tickers": matches,
                    "notes": info["notes"],
                    "type": "Curated High-Profile PEP",
                }
            )

        # 2. Match parsed filings from LHKPN scrapers
        seen_officials = set()
        for f in filings:
            raw_name = f.get("name", "").strip()
            c_name = clean_name(raw_name)
            if not c_name or c_name in seen_officials:
                continue

            if query and query.upper() not in c_name:
                continue

            matched_affiliations = idx_index.get(c_name, [])
            if matched_affiliations:
                seen_officials.add(c_name)
                results.append(
                    {
                        "official_name": raw_name,
                        "role": f.get("jabatan", "Pejabat Publik"),
                        "institution": f.get("lembaga", "Instansi"),
                        "total_harta": f.get("total_harta", "N/A"),
                        "tickers": matched_affiliations,
                        "notes": f"Matched in LHKPN filing dated {f.get('tanggal_lapor', 'N/A')}",
                        "type": "Direct Board/Shareholder Overlap",
                    }
                )

        return results

    def print_radar(self, query: str | None = None) -> None:
        """Print an executive radar summary in the terminal."""
        overlaps = self.scan_pep_overlaps(query=query)

        print("=" * 80)
        print("  🔎 IDX-BEI & LHKPN POLITICALLY EXPOSED PERSONS (PEP) RADAR")
        print("=" * 80)
        print(f" Total Overlaps Detected: {len(overlaps)} figures")
        print("-" * 80)

        for o in overlaps:
            print(f"\n👤 {o['official_name']} [{o['type']}]")
            print(f"   🏛️  Position:   {o['role']} ({o['institution']})")
            print(f"   💰  LHKPN Total: {o['total_harta']}")
            print("   🏢  Affiliated Listed Companies & Governance:")
            for t in o["tickers"]:
                print(f"       • [{t['ticker']}] {t['company_name'][:30]}: {t['role']}")
            if o.get("notes"):
                print(f"   📝  Notes: {o['notes']}")

        print("\n" + "=" * 80)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="LHKPN & Politically Exposed Persons (PEP) Radar for IDX"
    )
    parser.add_argument(
        "--query", type=str, default=None, help="Filter by official name or ticker code"
    )
    args = parser.parse_args()

    radar = LHKPNRadar()
    radar.print_radar(query=args.query)


if __name__ == "__main__":
    main()
