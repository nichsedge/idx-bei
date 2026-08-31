"""
Indonesia Power Map — core power graph utilities.
Extends idx-bei Neo4j graph with Politician + Ormas nodes.
"""
import pandas as pd


def create_ormas_node(name: str, chairman: str = "", classification: str = "unknown", source_url: str = "", **extra):
    return {
        "label": "Ormas",
        "name": name.strip(),
        "chairman": chairman.strip(),
        "classification": classification,
        "source_url": source_url,
        **extra,
    }


def create_politician_node(name: str, jabatan: str = "", lembaga: str = "", source_url: str = "", **extra):
    return {
        "label": "Politician",
        "name": name.strip().upper(),
        "jabatan": jabatan,
        "lembaga": lembaga,
        "source_url": source_url,
        **extra,
    }


def link_politician_to_company(politician: str, ticker: str, role: str = "AFFILIATED_WITH"):
    return {
        "from": politician.strip().upper(),
        "to": ticker.strip().upper(),
        "relationship": "AFFILIATED_WITH",
        "role": role,
    }


def pareto_filter(df: pd.DataFrame, value_col: str = "board_seats", percentile: float = 0.8) -> pd.DataFrame:
    """Pareto filter: return minimal rows covering `percentile` of total value.
    Falls back to top 20% if percentile not reached.
    """
    if df.empty or value_col not in df.columns:
        return df
    df = df.sort_values(value_col, ascending=False).reset_index(drop=True)
    total = df[value_col].sum()
    if total == 0:
        return df.head(max(1, len(df) // 5))
    cumsum = df[value_col].cumsum() / total
    # rows until cumsum <= percentile, at least 1
    mask = cumsum <= percentile
    if mask.any():
        # include first row that exceeds percentile too
        last_idx = mask[mask].index.max() + 1
        if last_idx < len(df):
            last_idx += 1
        return df.iloc[:last_idx]
    return df.head(max(1, len(df) // 5))


def score_ormas(ormas: dict) -> dict:
    """Rule-based ormas toxicity/benefit scoring — no LLM, just counts."""
    conflict = int(ormas.get("conflict_events", 0))
    social = int(ormas.get("social_events", 0))
    classification = ormas.get("classification", "unknown")
    news_context = (ormas.get("news_context") or "").lower()

    toxicity = conflict * 10
    if "preman" in news_context:
        toxicity += 20
    if classification == "kepemudaan-preman-risk":
        toxicity += 15
    if classification == "religious":
        toxicity += 5  # slight prior, religion label often used as cover

    benefit = social * 5 + min(15, int(ormas.get("news_verified_hits",0)//2))  # news hits = social relevance proxy, capped
    confidence = "high" if ormas.get("source_url") else "low"
    if not ormas.get("source_url") and conflict == 0:
        confidence = "low"

    return {"toxicity": toxicity, "benefit": benefit, "net_score": benefit - toxicity, "confidence": confidence}


def classify_ormas(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ["fpi", "hti", "laskar", "front pembela", "mujahid"]):
        return "religious"
    if any(k in n for k in ["pemuda pancasila", "pp ", "grib", "banser"]):
        return "kepemudaan-preman-risk"
    if any(k in n for k in ["adat", "paguyuban"]):
        return "adat"
    if any(k in n for k in ["pemuda", "kar Karang taruna", "knpi"]):
        return "kepemudaan"
    return "unknown"
