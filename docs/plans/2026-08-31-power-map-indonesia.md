# Indonesia Power Map — Weeks not Months Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build LittleSis-for-Indonesia: quantified power graph connecting IDX corporations → Politicians → Ormas, with Pareto-filtered top 200 power list, cluster ormas, and link everything via Neo4j + bijak-beli frontend. Ship weekly, not monthly.

**Architecture:** Extend existing `idx-bei` Neo4j graph (952 tickers, 12k insiders) as core truth engine. Add `Politician` and `Ormas` nodes + relationships. Keep `bijak-beli` as consumer-facing read layer that pulls from idx-bei via generated JSON/API, not direct Neo4j write. All edges carry `source_url`, `confidence` to handle bias/legal. Pseudonymous hosting, no PII opinions.

**Tech Stack:** Python 3.13 uv, Neo4j 5, Next.js 16, Drizzle ORM sqlite/libsql, DuckDB Parquet, curl_cffi scraper, Docker Compose

---

## Week 0 — Foundations (Day 1-2)

### Task 1: Extend Neo4j schema for Power Map

**Objective:** Add Politician/Ormas node types without breaking existing Company/Insider graph

**Files:**
- Modify: `python/src/idx/graph.py:1-30`
- Modify: `python/neo4j_ingest.py:1-50`
- Create: `python/src/idx/power.py`

**Step 1: Write failing test**

```python
# python/tests/test_power.py
def test_ormas_node_creation():
    from idx.power import create_ormas_node
    node = create_ormas_node("FPI", chairman="Rizieq Shihab", classification="religious")
    assert node["label"] == "Ormas"
    assert node["classification"] == "religious"

def test_politician_link():
    from idx.power import link_politician_to_company
    link = link_politician_to_company("Prabowo Subianto", "GOTO", role="shareholder")
    assert link["relationship"] == "AFFILIATED_WITH"
```

**Step 2: Run test to verify failure**

Run: `uv run pytest python/tests/test_power.py -v`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```python
# python/src/idx/power.py
def create_ormas_node(name, chairman, classification, source_url=""):
    return {"label": "Ormas", "name": name, "chairman": chairman, "classification": classification, "source_url": source_url}

def link_politician_to_company(politician, ticker, role=""):
    return {"from": politician, "to": ticker, "relationship": "AFFILIATED_WITH", "role": role}

def pareto_filter(df, value_col="board_seats", percentile=0.8):
    """Return top 20% rows that account for 80% of value"""
    import pandas as pd
    df = df.sort_values(value_col, ascending=False)
    cumsum = df[value_col].cumsum() / df[value_col].sum()
    cutoff = cumsum[cumsum <= percentile].index
    return df.loc[cutoff] if len(cutoff)>0 else df.head(max(1, len(df)//5))
```

**Step 4: Run test to verify pass**

Run: `uv run pytest python/tests/test_power.py -v`
Expected: PASS 2/2

**Step 5: Commit**

```bash
git add python/src/idx/power.py python/tests/test_power.py
git commit -m "feat: add power map Ormas/Politician node schema"
```

---

### Task 2: Generate Power200 from existing IDX data (Pareto)

**Objective:** Produce Pareto-filtered top 200 powerful insiders using existing centrality data, no new scraping

**Files:**
- Modify: `python/src/idx/graph.py:calculate_board_centrality`
- Create: `python/scripts/generate_power200.py`
- Create: `data/power200.json`

**Step 1: Write failing test**

```python
def test_power200_generation():
    from idx.power import pareto_filter
    import pandas as pd
    df = pd.DataFrame({"insider": ["A","B","C","D","E"], "board_seats": [10,8,2,1,1]})
    top = pareto_filter(df)
    assert len(top) <= 2  # top 20% ~1, but 80% value rule
    assert top.iloc[0]["insider"] == "A"
```

**Step 2-4: Implement + verify**

Run: `uv run python scripts/generate_power200.py` → should create `data/power200.json` with fields: `rank`, `insider`, `board_seats`, `companies`, `total_market_cap_controlled`, `source`

**Step 5: Commit**

```bash
git add python/scripts/generate_power200.py data/power200.json
git commit -m "feat: generate Power200 Pareto list from IDX centrality"
```

---

### Task 3: Wire bijak-beli → idx-bei bridge (brand → ticker mapping)

**Objective:** Create brand-to-ticker map so bijak-beli can enrich ownership from idx-bei

**Files:**
- Create: `bijak-beli/src/data/idx-mapping.json`
- Create: `bijak-beli/scripts/sync-idx-ownership.ts`

**Content `idx-mapping.json`:**

```json
{
  "indomie": {"ticker": "INDF", "source": "idx-bei"},
  "sarimi": {"ticker": "INDF"},
  "mie-sedaap": {"ticker": null, "note": "Wings private"},
  "mayora": {"ticker": "MYOR"},
  "gojek": {"ticker": "GOTO"},
  "kopi-kenangan": {"ticker": null},
  "wardah": {"ticker": null, "parent": "Paragon private"}
}
```

**Sync script logic:**

```typescript
// scripts/sync-idx-ownership.ts
import power200 from "../../idx-bei/data/power200.json"
import { brands } from "../src/data/brands"
// for each brand with ticker, fetch from idx-bei/data/companyDetailsByKodeEmiten.json
// update ultimateOwner, put source_url = idx-bei
```

**Steps:** Write test → run → implement → `bun run sync:ownership` should update `src/data/brands.ts` ultimateOwner fields with real UBO chain

**Commit:** `feat: add idx-bei ownership sync to bijak-beli`

---

## Week 1 — Politicians Bridge

### Task 4: Scrape LHKPN + DPR public data

**Objective:** Ingest 50 politicians linked to IDX boards

**Files:**
- Create: `python/src/idx/scrapers/politician.py`
- Create: `python/tests/test_politician.py`
- Create: `data/politicians.json`

**Scrapers:**
- `https://elhkpn.kpk.go.id` — wealth reports (search by name, parse)
- `https://dpr.go.id/anggota` — DPR member list + commission
- Use existing `curl_cffi` client from `idx.core.client`

**Step 1: Failing test**

```python
def test_parse_lhkpn():
    from idx.scrapers.politician import parse_lhkpn_row
    row = {"nama": "PRABOWO SUBIANTO", "jabatan": "Presiden", "harta": "2.000.000.000"}
    p = parse_lhkpn_row(row)
    assert p["name"] == "PRABOWO SUBIANTO"
    assert p["wealth"] == 2000000000
```

**Step 2-4: Implement scraper with mock, then live test with 5 names**

**Step 5: Verify**

Run: `uv run python -m idx.scrapers.politician --sample 5` → creates `data/politicians.json` with 5 entries + source_url

**Commit:** `feat: add politician scraper LHKPN+DPR`

---

### Task 5: Link Politicians to Companies via board name match

**Objective:** Create edges Politician -[:HOLDS_POSITION]-> Company when names match across datasets

**Files:**
- Modify: `python/src/idx/power.py` — add `link_politicians_to_boards()`
- Modify: `python/neo4j_ingest.py` — ingest politician nodes

**Logic:**

```python
def link_politicians_to_boards(politicians, board_centrality_df):
    # exact name match uppercased, then fuzzy (rapidfuzz)
    # create edge with confidence 0.9 exact, 0.6 fuzzy, source = both datasets
```

**Test:** 2 politicians match 2 board members, verify edge count

**Verify:** `uv run idx graph --centrality` now includes politician flag

**Commit:** `feat: link politicians to corporate boards`

---

## Week 2 — Ormas Data Warehouse

### Task 6: Scrape Kemendagri/Kemenkumham Ormas registry

**Objective:** Build ormas warehouse for Jawa Barat pilot (20 ormas), not all Indonesia

**Files:**
- Create: `python/src/idx/scrapers/ormas.py`
- Create: `data/ormas_jabar.json`
- Create: `python/tests/test_ormas.py`

**Sources:**
- `https://ormas.kemendagri.go.id` — search, paginate
- Fallback: scrape Google News `+ormas +Jawa Barat` for activity signals

**Fields:** `name`, `chairman`, `address`, `skt_number`, `classification`, `member_count_estimate`, `source_url`, `conflict_events` (from news count)

**Test:**

```python
def test_ormas_classify():
    from idx.scrapers.ormas import classify_ormas
    assert classify_ormas("Laskar Pembela Islam") == "religious"
    assert classify_ormas("Pemuda Pancasila") == "kepemudaan-preman-risk"
```

**Verify:** `uv run python -m idx.scrapers.ormas --province JABAR --limit 20` → `data/ormas_jabar.json` 20 rows

**Commit:** `feat: add ormas scraper Jabar pilot`

---

### Task 7: Classify & score ormas toxicity via rule-based scoring

**Objective:** Quantify toxicity without ML, minimize bias

**Files:**
- Create: `python/src/idx/ormas_scoring.py`

**Scoring (no LLM opinions, just counts):**

```python
def score_ormas(ormas):
    score = 0
    score += ormas["conflict_events"] * 10  # news hits
    score += 20 if "preman" in ormas["news_context"] else 0
    score += 15 if ormas["classification"] == "kepemudaan-preman-risk" else 0
    # Benefit: member_count, social activity (bakti sosial mentions)
    benefit = ormas.get("social_events", 0) * 5
    return {"toxicity": score, "benefit": benefit, "confidence": "medium" if source_url else "low"}
```

**Test:** 3 ormas with known profiles, verify ordering

**Commit:** `feat: add ormas toxicity scoring`

---

### Task 8: Extend Neo4j ingest to full power graph

**Objective:** Ingest all 3 layers into one graph

**Files:**
- Modify: `python/neo4j_ingest.py` — add ormas + politician ingestion after company/insider
- Modify: `docker-compose/neo4j.yml` — no change, just re-run

**Verify:**

```bash
docker compose up -d
uv run python/neo4j_ingest.py
# then in Neo4j Browser:
# MATCH (p:Politician)-[:AFFILIATED_WITH]->(c:Company) RETURN count(*)
# MATCH (o:Ormas)-[:LEADS]-(leader) RETURN o.name, leader.name LIMIT 5
```

**Commit:** `feat: ingest full power graph Company-Politician-Ormas`

---

## Week 3 — Connect & Publish Safely

### Task 9: Generate Power Map API / JSON for bijak-beli

**Objective:** Expose unified graph as static JSON so bijak-beli can render without direct Neo4j access

**Files:**
- Create: `python/scripts/export_power_map.py` → `data/power_map_export.json`
- Create: `bijak-beli/src/lib/power.ts` — types for power map

**Export shape:**

```json
{
  "nodes": [{"id": "Anthoni Salim", "type": "Person", "power_score": 98, "companies": ["INDF","ICBP"]}],
  "edges": [{"from": "Anthoni Salim", "to": "INDF", "type": "ULTIMATE_OWNER", "source_url": "idx.co.id", "confidence": 0.95}],
  "power200": [...],
  "ormas": [...]
}
```

**Verify:** `uv run python scripts/export_power_map.py` && `ls -lh data/power_map_export.json`

**Commit:** `feat: export power map for bijak-beli`

---

### Task 10: bijak-beli Power Map page (Littlesis view)

**Objective:** Frontend page to visualize connections, not drama articles

**Files:**
- Create: `bijak-beli/src/app/power/page.tsx`
- Create: `bijak-beli/src/components/PowerGraph.tsx` (use existing chart.js or d3)
- Modify: `bijak-beli/src/app/layout.tsx` — add /power nav

**Features:**
- Table: Power200 ranked, filter by Pareto tier
- Graph: force-directed showing Person ↔ Company ↔ Ormas (limit 50 nodes for perf)
- Every row shows source_url, confidence, no editorial

**Test:** `bun run build` passes, `bun run dev` renders /power with mock data

**Commit:** `feat: add power map page to bijak-beli`

---

### Task 11: Legal & OPSEC hardening

**Objective:** Minimize bias and legal risk before public

**Files:**
- Create: `docs/LEGAL.md`
- Create: `docs/METHODOLOGY.md`
- Modify: `bijak-beli/src/lib/scoring.ts` — add confidence display

**Content:**
- LEGAL.md: "All data from public sources: IDX, KSEI, KPK LHKPN, Kemendagri. Every fact has source_url. No defamation — we publish filings, not accusations. Host on Vercel + Cloudflare, repo under org not personal, use pseudonym if needed."
- METHODOLOGY.md: Pareto definition, classification rules, confidence levels, bias notes
- Add disclaimer footer on /power page

**Verify:** `cat docs/LEGAL.md` && `cat docs/METHODOLOGY.md`

**Commit:** `docs: add legal and methodology for power map`

---

### Task 12: Deploy & broadcast (stealth)

**Objective:** Ship without buzz

**Files:**
- Modify: `.github/workflows/tests.yml` — add power map export test
- Run: `vercel deploy` for bijak-beli

**Steps:**
- Don't press release. Post 1 thread on X: "Power200 Indonesia by numbers — IDX data, Pareto, sources here: link" Tag 5 data journalists, not buzzer.
- Measure: 100 visits = success. If toxic ormas complains, you have source_url proof.

**Commit:** `chore: deploy power map v0`

---

## Verification Checklist

- [ ] `uv run idx graph --centrality | head -20` returns Power200
- [ ] `uv run python scripts/generate_power200.py` creates data/power200.json
- [ ] `docker compose up -d && uv run python/neo4j_ingest.py` ingests 3 node types without error
- [ ] `bun run sync:ownership` enriches bijak-beli brands with real UBO
- [ ] `bun run build` passes for bijak-beli with /power page
- [ ] Every edge in power_map_export.json has source_url + confidence
- [ ] docs/LEGAL.md + METHODOLOGY.md exist

## Risks & Mitigations

- **Incomplete politician data:** Start with 50, not 500. Confidence low = show it.
- **Ormas data messy:** Jabar pilot 20 only, manual verify 3.
- **Legal UU ITE:** Never write "toxic" without number. Use scores + source.
- **Personal safety:** Org repo, not nichsedge personal; Vercel deploy, no home address; optional Tor for inquiry.

## Next Agent Instructions

Delegate Task 1-3 to Agent A (idx-bei core), Task 4-5 to Agent B (politician), Task 6-8 to Agent C (ormas), Task 9-12 to Agent D (frontend+legal). Each agent: TDD, 1 task = 1 commit, push to branch `feat/power-map`.

