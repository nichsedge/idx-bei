# METHODOLOGY — Quantifying Power, Bias Minimization

**Who is powerful?** Pareto 80/20 on board centrality.
- `board_seats = count(DISTINCT companies) where Person is director/commissioner`
- Top persons covering 80% of total seats = Power200 (currently 200). Minimal filter = top 20% if 80% not reached.
- Source: `companyDetailsByKodeEmiten.json` (11MB) + Neo4j `DIRECTOR_OF|COMMISSIONER_OF`. Deduped, empty names filtered.

**Ormas classification:**
- Initial seed 20 Jabar ormas (manual from Kemendagri). `classify_ormas()` rule: religious keywords, kepemudaan-preman-risk, adat.
- Toxicity/Benefit: `toxicity = conflict_events*10 + (preman in news?20:0) + (risk class?15:0)`, `benefit = social_events*5`, `net = benefit - toxicity`. `confidence = high if source_url else low`.
- No LLM judgment. Counts from news + registry only. Transparent.

**Politicians:**
- LHKPN via your `lhkpn` scraper (Playwright stealth). Wealth parsed from `Rp.` format. Link to boards via exact UPPER name match. Currently Prabowo sample 11 records → 0 board links (expected). Pipeline ready for 50.

**Bias mitigation:**
- Every edge has `source_url`, `date`, `confidence`.
- Scores show formula, not hidden model.
- We publish methodology, allow correction PR.

**Limitations:** IDX only covers listed firms; private + ormas data incomplete. We mark `confidence: low` where needed and keep static seed for Jabar before scaling.

**Tier definitions (0-100 normalized):**
- `support` (>=80): high board centrality + verified public filings; quantifies institutional backing.
- `neutral` (20-79): moderate seats / mixed sources; requires further verification.
- `punish` (<20 or toxicity-dominant): conflict events + preman risk exceed benefit; flag for scrutiny, not verdict.

## Support / Punish Tiers (normalized 0-100)
- `tier = "support"` if support_score > punish_score + 10 (clear net positive)
- `tier = "punish"` if punish_score > support_score + 10 (clear net negative)
- `tier = "neutral"` otherwise (within 10 pts)
- Confidence: high = verified board + registered source_url; low = news fallback only / 0 LHKPN hits.
