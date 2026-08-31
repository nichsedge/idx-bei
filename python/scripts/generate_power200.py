#!/usr/bin/env python3
"""Generate Power200 Pareto list from existing Neo4j/local centrality."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))
from idx.graph import calculate_board_centrality
from idx.power import pareto_filter
from idx.core.utils import DATA_DIR

out = os.path.join(DATA_DIR, "power200.json")

df = calculate_board_centrality(top_n=500)
if df.empty:
    print("No centrality data — is companyDetailsByKodeEmiten.json present?")
    sys.exit(1)

# Pareto filter
power = pareto_filter(df, value_col="board_seats", percentile=0.8)
# Cap to 200 for export
power = power.head(200).reset_index(drop=True)
power["rank"] = power.index + 1
power["source_url"] = "https://idx.co.id + companyDetailsByKodeEmiten.json"
power["confidence"] = "high"

# Add market cap controlled if available (placeholder)
records = power.to_dict(orient="records")
# Ensure JSON serializable
for r in records:
    if isinstance(r.get("companies"), list):
        r["companies"] = r["companies"]
    else:
        r["companies"] = list(r["companies"]) if r.get("companies") else []

with open(out, "w") as f:
    json.dump(records, f, indent=2, ensure_ascii=False)

print(f"Generated Power200: {len(records)} entries -> {out}")
print(f"Top 5: {[r['insider'] for r in records[:5]]}")
