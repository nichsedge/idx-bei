"""
Acquisition, backdoor-listing and rights-issue tracker.

- Deals (acquisitions, backdoor listings, tender offers) come from ``data/deals.json``.
- Tracked capital raises (planned, ongoing and recent rights issues / placements, with terms and
  events) come from ``data/rights.json``; ``linked_deal`` points to a deal when the raise is part of one.
- Listed rights issues and private placements come from ``data/corporateActions.json`` (``idx corporate``).

IDX listing records can cover a single batch of exercised rights and the feed misses some issues,
so listed sizes understate the real issue. Full terms need prospectus extraction.
"""

import os
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from idx.core.utils import DATA_DIR, load_json

DEALS_FILE = os.path.join(DATA_DIR, "deals.json")
RIGHTS_FILE = os.path.join(DATA_DIR, "rights.json")
CORPORATE_ACTIONS_FILE = os.path.join(DATA_DIR, "corporateActions.json")
OPEN_STATUSES = {"active", "watch"}

# ---------- Rights issues & private placements ----------

RAISE_CATEGORIES = {
    "hmetd": "rights_issue",
    "tanpaHmetd": "private_placement",
    "PrivatePlacement": "private_placement",
}

FLAG_LABELS = {
    "LARGE": "Large (≥ 1× existing shares)",
    "SERIAL": "Serial issuer (≥ 2 in 36m)",
    "PP_OVER_10": "Placement > 10% of capital",
}

BATCH_WINDOW = timedelta(days=45)
SERIAL_WINDOW = timedelta(days=round(3 * 365.25))


def _listing_date(row: dict[str, Any]) -> date:
    return date.fromisoformat(str(row["TanggalPencatatan"])[:10])


def build_capital_raises(actions: dict[str, Any]) -> list[dict[str, Any]]:
    """Rights issues and private placements, newest first, with dilution and flags.

    Batches of one issue (same ticker and type, ≤ 45 days apart, share counts chaining) are merged.
    """
    rows: list[dict[str, Any]] = []
    categories = actions.get("categories", {})
    for cat, kind in RAISE_CATEGORIES.items():
        for r in categories.get(cat, {}).get("data", []):
            added = float(r.get("JumlahSaham") or 0)
            after = float(r.get("JumlahSahamSetelahTindakan") or 0)
            # Old IDX rows sometimes carry inconsistent totals (added ≥ after); skip what we can't interpret.
            if added <= 0 or after <= added:
                continue
            d = _listing_date(r)
            rows.append(
                {
                    "id": r["id"],
                    "ticker": str(r["KodeEmiten"]).strip().upper(),
                    "type": kind,
                    "listing_date": d,
                    "last_listing_date": d,
                    "tranches": 1,
                    "new_shares": added,
                    "shares_after": after,
                }
            )

    rows.sort(key=lambda x: (x["ticker"], x["type"], x["listing_date"]))
    merged: list[dict[str, Any]] = []
    for r in rows:
        prev = merged[-1] if merged else None
        if (
            prev
            and prev["ticker"] == r["ticker"]
            and prev["type"] == r["type"]
            and r["listing_date"] - prev["last_listing_date"] <= BATCH_WINDOW
            and abs((r["shares_after"] - r["new_shares"]) - prev["shares_after"])
            <= prev["shares_after"] * 0.01
        ):
            prev["new_shares"] += r["new_shares"]
            prev["shares_after"] = r["shares_after"]
            prev["last_listing_date"] = r["listing_date"]
            prev["tranches"] += 1
        else:
            merged.append(dict(r))

    by_ticker: dict[str, list[date]] = defaultdict(list)
    for r in merged:
        by_ticker[r["ticker"]].append(r["listing_date"])

    for r in merged:
        before = r["shares_after"] - r["new_shares"]
        r["shares_before"] = before
        r["dilution_pct"] = r["new_shares"] / r["shares_after"] * 100
        r["size_vs_old_pct"] = r["new_shares"] / before * 100
        r["raises_in_36m"] = sum(
            1
            for d in by_ticker[r["ticker"]]
            if d <= r["listing_date"] and r["listing_date"] - d <= SERIAL_WINDOW
        )
        flags = []
        if r["size_vs_old_pct"] >= 100:
            flags.append("LARGE")
        if r["raises_in_36m"] >= 2:
            flags.append("SERIAL")
        if r["type"] == "private_placement" and r["size_vs_old_pct"] > 10.5:
            flags.append("PP_OVER_10")
        r["flags"] = flags

    merged.sort(key=lambda x: (x["listing_date"], x["ticker"]), reverse=True)
    for r in merged:
        r["listing_date"] = r["listing_date"].isoformat()
        r["last_listing_date"] = r["last_listing_date"].isoformat()
    return merged


def ticker_corporate_actions(actions: dict[str, Any], ticker: str) -> list[dict[str, Any]]:
    """Every corporate action listing for one ticker, newest first."""
    ticker = ticker.strip().upper()
    out = [
        {
            "category": cat,
            "listing_date": str(r["TanggalPencatatan"])[:10],
            "shares": r.get("JumlahSaham"),
            "shares_after": r.get("JumlahSahamSetelahTindakan"),
        }
        for cat, block in actions.get("categories", {}).items()
        for r in block.get("data", [])
        if str(r.get("KodeEmiten", "")).strip().upper() == ticker
    ]
    return sorted(out, key=lambda x: x["listing_date"], reverse=True)


def load_corporate_actions() -> dict[str, Any]:
    return load_json(CORPORATE_ACTIONS_FILE, default={})


# ---------- Deals & backdoor score (plan §3.3) ----------

BACKDOOR_WEIGHTS: dict[str, tuple[int, str]] = {
    "control_change": (20, "Change of controller confirmed"),
    "different_sector": (15, "Acquirer from a different sector"),
    "shell_like_target": (15, "Small / shell-like target"),
    "business_change_plan": (20, "Plan to change business activity / name"),
    "large_capital_injection": (15, "Large rights issue / inbreng / material transaction"),
    "jumbo_ng_trades": (10, "Jumbo negotiated-market trades"),
    "price_spike": (5, "Price spike before announcement"),
}


def backdoor_score(signals: dict[str, bool] | None) -> dict[str, Any]:
    signals = signals or {}
    items: list[dict[str, Any]] = [
        {"key": k, "label": label, "weight": w, "fired": bool(signals.get(k))}
        for k, (w, label) in BACKDOOR_WEIGHTS.items()
    ]
    score = sum(w for k, (w, _) in BACKDOOR_WEIGHTS.items() if signals.get(k))
    label = (
        "Likely backdoor" if score >= 60 else "Possible" if score >= 35 else "Ordinary acquisition"
    )
    return {"score": score, "label": label, "signals": items}


def enrich_deal(deal: dict[str, Any]) -> dict[str, Any]:
    events = deal.get("events", [])
    tender = next((e for e in events if e.get("tender_price")), None)
    pre = deal.get("pre_announcement_price")
    dates = [e.get("event_date", "") for e in events] + [deal.get("announced_at") or ""]
    return {
        **deal,
        "backdoor": backdoor_score(deal.get("signals")),
        "tender_premium_pct": (tender["tender_price"] / pre - 1) * 100 if tender and pre else None,
        "last_event_date": max(dates),
        "pending_review": sum(1 for e in events if e.get("review_status") == "pending"),
    }


def list_deals(deals_file: dict[str, Any]) -> dict[str, Any]:
    deals = [enrich_deal(d) for d in deals_file.get("deals", [])]
    deals.sort(key=lambda d: d["last_event_date"], reverse=True)
    return {"updated_at": deals_file.get("updated_at"), "deals": deals}


def load_deals() -> dict[str, Any]:
    return load_json(DEALS_FILE, default={"updated_at": None, "deals": []})


# ---------- Tracked capital raises (rights.json) ----------


def enrich_raise(item: dict[str, Any]) -> dict[str, Any]:
    """Adds rights per old share, the theoretical ex-rights price and review counters."""
    t = item.get("terms") or {}
    old, new, px, cum = (
        t.get(k) for k in ("ratio_old", "ratio_new", "exercise_price", "cum_price")
    )
    events = item.get("events", [])
    dates = [e.get("event_date", "") for e in events] + [item.get("announced_at") or ""]
    return {
        **item,
        "new_per_old": new / old if old and new else None,
        "terp": (old * cum + new * px) / (old + new) if old and new and px and cum else None,
        "last_event_date": max(dates),
        "pending_review": sum(1 for e in events if e.get("review_status") == "pending"),
    }


def list_rights(rights_file: dict[str, Any]) -> dict[str, Any]:
    items = [enrich_raise(r) for r in rights_file.get("rights", [])]
    items.sort(key=lambda r: r["last_event_date"], reverse=True)
    return {"updated_at": rights_file.get("updated_at"), "rights": items}


def load_rights() -> dict[str, Any]:
    return load_json(RIGHTS_FILE, default={"updated_at": None, "rights": []})


def tracked_tickers(deals_file: dict[str, Any], rights_file: dict[str, Any]) -> list[str]:
    """Tickers of open deals and open (active / watch) capital raises."""
    return sorted(
        {
            d["target_ticker"]
            for d in deals_file.get("deals", [])
            if d.get("status") in OPEN_STATUSES
        }
        | {r["ticker"] for r in rights_file.get("rights", []) if r.get("status") in OPEN_STATUSES}
    )
