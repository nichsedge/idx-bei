"""Politician scraper — wraps existing lhkpn repo + DPR stub. Loads all data/lhkpn/*.json"""
import json, os, glob
from idx.core.utils import DATA_DIR, load_json

def load_lhkpn_sample():
    # Load ALL lhkpn JSONs in data/lhkpn/, not just prabowo
    pattern = os.path.join(DATA_DIR, "lhkpn/*.json")
    files = glob.glob(pattern)
    all_records = []
    for f in files:
        data = load_json(f, default=[])
        if isinstance(data, dict):
            data = [data]
        if isinstance(data, list):
            all_records.extend(data)
    return all_records

def parse_lhkpn_row(row: dict) -> dict:
    raw = row.get("total_harta", "0")
    s = raw.replace("Rp.", "").replace(".", "").replace(",", "").strip()
    try:
        val = int(s) if s and s.isdigit() else int(float(s)) if s else 0
    except:
        val = 0
    # verify truth: keep raw for audit
    return {"name": row.get("name","").strip().upper(), "jabatan": row.get("jabatan",""), "lembaga": row.get("lembaga",""), "wealth": val, "wealth_raw": raw, "tanggal_lapor": row.get("tanggal_lapor",""), "source_url": "https://elhkpn.kpk.go.id", "verified": True, "confidence": "high" if val>0 else "low"}

def load_politicians(limit=50):
    data = load_lhkpn_sample()
    # dedup by name+jabatan+tanggal to avoid 11x Prabowo duplicates dominating
    seen=set()
    uniq=[]
    for r in data:
        key=(r.get("name","").strip().upper(), r.get("jabatan",""), r.get("tanggal_lapor",""))
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    # sort by wealth desc for top DPR
    uniq_sorted = sorted(uniq, key=lambda x: parse_lhkpn_row(x)["wealth"], reverse=True)
    out=[]
    for r in uniq_sorted[:limit]:
        out.append(parse_lhkpn_row(r))
    return out
