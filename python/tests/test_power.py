import pandas as pd
from idx.power import create_ormas_node, link_politician_to_company, pareto_filter, score_ormas, classify_ormas

def test_ormas_node_creation():
    node = create_ormas_node("FPI", chairman="Rizieq Shihab", classification="religious")
    assert node["label"] == "Ormas"
    assert node["classification"] == "religious"

def test_politician_link():
    link = link_politician_to_company("Prabowo Subianto", "GOTO", role="shareholder")
    assert link["relationship"] == "AFFILIATED_WITH"
    assert link["to"] == "GOTO"

def test_pareto_filter():
    df = pd.DataFrame({"insider": ["A","B","C","D","E"], "board_seats": [10,8,2,1,1]})
    top = pareto_filter(df)
    assert len(top) <= 3
    assert top.iloc[0]["insider"] == "A"

def test_classify():
    assert classify_ormas("Laskar Pembela Islam") == "religious"
    assert classify_ormas("Pemuda Pancasila") == "kepemudaan-preman-risk"

def test_score_ormas():
    s = score_ormas({"conflict_events": 2, "news_context": "preman memalak", "classification": "kepemudaan-preman-risk", "source_url": "https://x"})
    assert s["toxicity"] >= 35
