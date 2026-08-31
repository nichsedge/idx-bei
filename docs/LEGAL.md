# LEGAL — Indonesia Power Map

**Principle:** We publish *public filings*, not opinions.

- All facts from public sources: IDX/BEI (companyDetailsByKodeEmiten.json), KSEI ownership, KPK LHKPN (elhkpn.kpk.go.id), Kemendagri/Kemenkumham Ormas registry, news links.
- Every node/edge has `source_url` + `confidence` (high/medium/low) + `date`. No unsourced claim.
- We do not label "corrupt" or "toxic" as editorial. We quantify: `toxicity = conflict_events*10 + preman + ...` and show formula + raw counts. Reader decides.
- Defamation risk (UU ITE): mitigated by citing official documents and using rule-based scores. No anonymus accusation without document.
- Hosting: Vercel + Cloudflare, repo under org `bijak-beli`/`idx-bei`, not personal. For sensitive ormas mapping, publish dataset, not author identity. Use pseudonym if needed. No home address, use ProtonMail.
- If takedown request: keep raw export JSON immutable, add `disputed: true` flag, don't delete history.

**Disclaimer on /power page:** "Data from public filings. Scores are transparent formulas, not legal judgments. Verify via source links."

**Hourly automation:** `production_refresh.sh` (Power200 + LHKPN + detik news fallback + Parquet warehouse) verified 2026-08-31, cron `489c0afe3df7` daily 06:00 + `d04c87d97bfa` hourly via Hermes, all confidence flagged high/medium/low per your constraint "verify the truth, and if not confident, just mention it."
