#!/usr/bin/env python3
"""Export unified power map for bijak-beli frontend."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))
from idx.core.utils import DATA_DIR

power200 = json.load(open(os.path.join(DATA_DIR, "power200.json")))
ormas = json.load(open(os.path.join(DATA_DIR, "ormas_jabar.json")))
pol_links = json.load(open(os.path.join(DATA_DIR, "politician_links.json")))

# Build nodes/edges
nodes=[]
edges=[]
for r in power200[:50]:  # top 50 for graph perf
    nodes.append({"id": r["insider"], "type": "Person", "power": r["board_seats"], "companies": r["companies"], "source_url": r["source_url"], "confidence": "high"})
    for c in r["companies"]:
        edges.append({"from": r["insider"], "to": c, "type": "BOARD_SEAT", "source_url": "idx.co.id", "confidence": 0.95})

for o in ormas:
    nodes.append({"id": o["name"], "type": "Ormas", "toxicity": o["toxicity"], "benefit": o["benefit"], "classification": o["classification"], "source_url": o["source_url"], "confidence": o["confidence"]})

for p in pol_links.get("politicians",[])[:10]:
    nodes.append({"id": p["name"], "type": "Politician", "jabatan": p["jabatan"], "wealth": p["wealth"], "source_url": p["source_url"], "confidence": "high"})

# Add brand mapping from idx-mapping
import pathlib
mapping_path = pathlib.Path(__file__).parent.parent.parent.parent / "bijak-beli/src/data/idx-mapping.json"
if mapping_path.exists():
    mapping = json.loads(mapping_path.read_text())
    for bid, meta in mapping.items():
        if meta.get("ticker"):
            nodes.append({"id": bid, "type": "Brand", "ticker": meta["ticker"]})
            edges.append({"from": bid, "to": meta["ticker"], "type": "BRAND_OF", "source_url": "idx-bei mapping", "confidence": 0.9})

out = {"generated_at": "2026-08-31", "power200": power200, "ormas": ormas, "politicians": pol_links, "graph": {"nodes": nodes, "edges": edges}}

dst1 = os.path.join(DATA_DIR, "power_map_export.json")
dst2 = str(pathlib.Path(__file__).parent.parent.parent.parent / "bijak-beli/public/power_map_export.json")
json.dump(out, open(dst1,"w"), indent=2, ensure_ascii=False)
json.dump(out, open(dst2,"w"), indent=2, ensure_ascii=False)
print(f"Exported {len(nodes)} nodes {len(edges)} edges -> {dst1} + {dst2}")
print(f"Sample node: {nodes[0]}")
