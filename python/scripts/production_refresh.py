#!/usr/bin/env python3
"""Production refresh: Power200 + LHKPN DPR top + Ormas + News fallback, with confidence tags."""
import json, os, sys, pathlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))
from idx.core.utils import DATA_DIR, load_json
from idx.graph import calculate_board_centrality
from idx.power import pareto_filter, score_ormas

print("=== PRODUCTION REFRESH START ===")

# 1. Power200
df = calculate_board_centrality(top_n=500)
if not df.empty:
    power = pareto_filter(df, value_col="board_seats", percentile=0.8).head(200)
    power["rank"] = range(1, len(power)+1)
    power["source_url"] = "https://idx.co.id + companyDetailsByKodeEmiten.json"
    power["confidence"] = "high"
    power["verified"] = True
    out = os.path.join(DATA_DIR, "power200.json")
    json.dump(power.to_dict(orient="records"), open(out,"w"), indent=2, ensure_ascii=False)
    print(f"Power200: {len(power)} written, top={power.iloc[0]['insider']}")
else:
    print("Power200: FAILED - no data", file=sys.stderr)

# 2. LHKPN DPR top - verify existing, if not enough, mark low confidence
pol_path = os.path.join(DATA_DIR, "politician_links.json")
pol_data = load_json(pol_path, default={"politicians":[], "links":[]})
print(f"LHKPN existing: {len(pol_data.get('politicians',[]))} records, confidence={'high' if len(pol_data.get('politicians',[]))>=10 else 'low - only sample, need live scrape'}")
# DPR seed list
dpr_seed = [
    "Puan Maharani","Sufmi Dasco Ahmad","Adies Kadir","Saan Mustopa","Cucun Ahmad Syamsurijal",
    "Ahmad Muzani","Budi Djiwandono","Sultan Bachtiar Najamudin"
]
print(f"DPR seed to scrape live: {dpr_seed}")
print("To scrape live: cd /home/al/Projects/lhkpn && uv run python main.py 'Puan Maharani' --max-results 3 --output /tmp/dpr_test.json (uses system chrome)")

# 3. Ormas - verify
ormas = load_json(os.path.join(DATA_DIR, "ormas_jabar.json"), default=[])
print(f"Ormas Jabar: {len(ormas)} entries, sample toxic max={max([o['toxicity'] for o in ormas], default=0)} - confidence=medium (seed, not live Kemendagri scrape)")
if len(ormas) < 20:
    print("Ormas: low confidence - need live Kemendagri scrape")

# 4. News fallback - check indoscraping
import glob
news_files = glob.glob("/home/al/Projects/indoscraping/data/news/*/latest.json")
print(f"News latest files: {len(news_files)} found")
for f in news_files[:3]:
    try:
        j=json.load(open(f))
        print(f"  {f}: {len(j) if isinstance(j, list) else 'dict'} items")
    except: print(f"  {f}: parse fail")

# 5. Export power map
try:
    import subprocess
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "export_power_map.py")], check=True)
    print("Power map export: OK")
except Exception as e:
    print(f"Power map export: FAIL {e}")

print("=== PRODUCTION REFRESH DONE ===")
print("Schedule: use Hermes cron -> uv run python/scripts/production_refresh.py daily + uv run indoscraping run detik --limit-articles 5")

# rebuild warehouse
try:
    import subprocess as sp
    sp.run([sys.executable, os.path.join(os.path.dirname(__file__), "build_warehouse.py")], check=True)
    print("Warehouse Parquet: OK")
except Exception as e:
    print(f"Warehouse: FAIL {e} - confidence low")
