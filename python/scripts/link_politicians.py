import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))
from idx.scrapers.politician import load_politicians
from idx.graph import calculate_board_centrality
from idx.core.utils import DATA_DIR

pols = load_politicians(limit=50)
df = calculate_board_centrality(top_n=500)
board_names = set(df["insider"].astype(str).str.upper())

links=[]
for p in pols:
    name = p["name"]
    if name in board_names:
        row = df[df["insider"].str.upper()==name].iloc[0]
        links.append({"politician": name, "jabatan": p["jabatan"], "companies": row["companies"], "board_seats": int(row["board_seats"]), "wealth": p["wealth"], "source_url": p["source_url"], "confidence": 0.95})

out = os.path.join(DATA_DIR, "politician_links.json")
with open(out, "w") as f:
    json.dump({"politicians": pols, "links": links}, f, indent=2, ensure_ascii=False)
print(f"Politicians loaded: {len(pols)}")
print(f"Links to boards: {len(links)}")
if links:
    print(json.dumps(links[:2], indent=2, ensure_ascii=False))
else:
    print("No direct name matches — expected for Prabowo (not on board). Example board names:", list(board_names)[:5])
print(f"Saved -> {out}")
