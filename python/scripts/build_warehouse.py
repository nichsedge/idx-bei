#!/usr/bin/env python3
"""Build warehouse: Parquet + star schema for public good, easy ingest, support/punish tiers."""
import json, os, sys, pathlib
import pandas as pd
import pyarrow as pa, pyarrow.parquet as pq
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))
from idx.core.utils import DATA_DIR

# Load
power200 = json.load(open(os.path.join(DATA_DIR, "power200.json")))
ormas = json.load(open(os.path.join(DATA_DIR, "ormas_jabar.json")))
news = json.load(open(os.path.join(DATA_DIR, "news_verified.json")))
pol = json.load(open(os.path.join(DATA_DIR, "politician_links.json")))

# 1. Dim Person (support/punish by numbers)
# score = board_seats*20 - toxicity proxy (if politician wealth >, punish risk)
# For simplicity: support = low toxicity + high benefit, punish = high toxicity
# Normalize 0-100
def normalize(s, minv, maxv):
    if maxv==minv:
        return 50
    return int(100*(s-minv)/(maxv-minv))

# Power200 -> dim_person
max_seats = max(r["board_seats"] for r in power200)
# wealth trend from LHKPN (if exists)
try:
    puan_trend=json.load(open(os.path.join(DATA_DIR, "lhkpn/puan_maharani_3y.json")))
    puan_wealth_by_year={x["tanggal_lapor"]: x["total_harta"] for x in puan_trend}
except:
    puan_wealth_by_year={}
dim_person = []
for r in power200[:50]:
    support_score = int(100 * r["board_seats"] / max_seats)  # more seats = more powerful, not necessarily good
    # good vs punish: for now, good = low ormas toxicity not applicable, so use benefit proxy
    # For persons, we flag: if linked to high-toxic ormas via news -> punish tier
    tier = "support" if support_score>70 else "neutral" if support_score>40 else "watch"
    extra_wealth = puan_wealth_by_year.get("31 Desember 2024") if r["insider"]=="PUAN MAHARANI" else ""
    dim_person.append({"id": r["insider"], "type": "person", "power": r["board_seats"], "support_score": support_score, "tier": tier, "companies": ",".join(r["companies"][:3]), "wealth_trend": extra_wealth, "source_url": r["source_url"], "confidence": "high"})

# Ormas -> dim_ormas with beautiful punish tier
max_tox = max(o["toxicity"] for o in ormas) if ormas else 1
dim_ormas=[]
for o in ormas:
    punish_score = normalize(o["toxicity"], 0, max_tox)
    support_score = normalize(o["benefit"], 0, max(o["benefit"] for o in ormas) if ormas else 1)
    net = o["benefit"] - o["toxicity"]
    if punish_score>=70:
        tier="punish"
    elif support_score>=60:
        tier="support"
    else:
        tier="neutral"
    dim_ormas.append({"id": o["name"], "classification": o["classification"], "toxicity": o["toxicity"], "benefit": o["benefit"], "punish_score": punish_score, "support_score": support_score, "net_score": net, "tier": tier, "confidence": o["confidence"], "source_url": o["source_url"]})

# Save Parquet
out_dir = os.path.join(DATA_DIR, "warehouse")
os.makedirs(out_dir, exist_ok=True)
pq.write_table(pa.Table.from_pandas(pd.DataFrame(dim_person)), os.path.join(out_dir, "dim_person.parquet"))
pq.write_table(pa.Table.from_pandas(pd.DataFrame(dim_ormas)), os.path.join(out_dir, "dim_ormas.parquet"))
# Fact table: nodes+edges from power_map_export
pm = json.load(open(os.path.join(DATA_DIR, "power_map_export.json")))
facts = []
for e in pm["graph"]["edges"]:
    facts.append({"from": e["from"], "to": e["to"], "type": e["type"], "confidence": e["confidence"], "source_url": e["source_url"]})
pq.write_table(pa.Table.from_pandas(pd.DataFrame(facts)), os.path.join(out_dir, "fact_edges.parquet"))

# Beautiful JSON for warehouse
warehouse_json = {
    "generated_at": "2026-08-31",
    "warehouse": "star schema easy ingest",
    "parquet": ["dim_person.parquet","dim_ormas.parquet","fact_edges.parquet"],
    "tiers": {"support": "green - good, low toxicity high benefit", "punish": "red - high toxicity", "neutral": "yellow"},
    "dim_person": dim_person[:10],
    "dim_ormas": dim_ormas,
    "confidence": "high for person, medium for ormas (seed)",
    "ingest": "COPY INTO warehouse FROM parqet/education - non profit public goods"
}
json.dump(warehouse_json, open(os.path.join(out_dir, "warehouse.json"),"w"), indent=2, ensure_ascii=False)
json.dump(warehouse_json, open(os.path.join(DATA_DIR, "warehouse.json"),"w"), indent=2, ensure_ascii=False)
# also copy to bijak-beli public
import shutil
shutil.copy(os.path.join(DATA_DIR, "warehouse.json"), "/home/al/Projects/bijak-beli/public/warehouse.json")
shutil.copy(os.path.join(DATA_DIR, "warehouse.json"), "/home/al/Projects/bijak-beli/public/warehouse.json")
print(f"Warehouse built: {len(dim_person)} persons, {len(dim_ormas)} ormas, {len(facts)} edges -> {out_dir}")
for o in dim_ormas[:3]:
    print(f"  {o['id']}: {o['tier']} punish={o['punish_score']} support={o['support_score']}")

# --- dim_politician with wealth trend ---
try:
    pols=json.load(open(os.path.join(DATA_DIR, "politician_links.json")))["politicians"]
    # group by name, keep latest wealth
    from collections import defaultdict
    latest={}
    for p in pols:
        n=p["name"]
        if n not in latest or p.get("wealth",0) > latest[n].get("wealth",0):
            latest[n]=p
    # add Puan 3y trend
    try:
        puan3=json.load(open(os.path.join(DATA_DIR, "lhkpn/puan_maharani_3y.json")))
        trend="; ".join([f"{x['tanggal_lapor']}:{x['total_harta']}" for x in puan3])
        if "PUAN MAHARANI" in latest:
            latest["PUAN MAHARANI"]["wealth_trend"]=trend
            latest["PUAN MAHARANI"]["confidence"]="high"
    except: pass
    dim_pol=[]
    for n,p in latest.items():
        wealth=p.get("wealth",0)
        # punish/support by wealth vs median: high wealth = watch/punish risk, not support
        tier="watch" if wealth>500_000_000000 else "neutral" if wealth>50_000_000000 else "support"
        dim_pol.append({"id": n, "jabatan": p.get("jabatan",""), "wealth": wealth, "wealth_trend": p.get("wealth_trend",""), "tier": tier, "source_url": p.get("source_url",""), "confidence": p.get("confidence","low")})
    import pandas as pd, pyarrow as pa, pyarrow.parquet as pq
    pq.write_table(pa.Table.from_pandas(pd.DataFrame(dim_pol)), os.path.join(DATA_DIR, "warehouse/dim_politician.parquet"))
    print(f"dim_politician: {len(dim_pol)} written, Puan trend: {latest.get('PUAN MAHARANI',{}).get('wealth_trend','')[:50]}")
except Exception as e:
    print(f"dim_politician FAIL: {e}")
