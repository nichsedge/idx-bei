"""News fallback scraper — direct scrape when indoscraping fails. Saves with confidence."""
import json, os, re, time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from idx.core.utils import DATA_DIR

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152.0.0.0 Safari/537.36"}

def scrape_detik_fallback(limit=5):
    """Scrape detik indeks directly, return list with source_url+confidence"""
    url = "https://news.detik.com/indeks"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        articles=[]
        for a in soup.select("article a[href*='detik.com']")[:limit]:
            href=a.get("href")
            title=a.get_text(strip=True) or a.get("title","")
            if href and title and len(title)>20:
                articles.append({"title": title[:120], "url": href, "source": "detik.com", "source_url": href, "confidence": "high" if "detik.com" in href else "low", "verified": True})
        # fallback if selector fails
        if not articles:
            for a in soup.find_all("a", href=True)[:limit*3]:
                href=a["href"]
                if "detik.com" in href and len(a.get_text(strip=True))>20:
                    articles.append({"title": a.get_text(strip=True)[:120], "url": href, "source": "detik.com", "source_url": href, "confidence": "medium", "verified": False})
                    if len(articles)>=limit:
                        break
        return articles
    except Exception as e:
        return [{"error": str(e), "source_url": url, "confidence": "low", "verified": False}]

def run_and_save(limit=5):
    data = scrape_detik_fallback(limit=limit)
    out = os.path.join(DATA_DIR, "news_verified.json")
    payload = {"scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S+07:00"), "count": len(data), "articles": data, "fallback_used": True, "confidence": "high" if any(a.get("verified") for a in data) else "low"}
    with open(out, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"News fallback: {len(data)} articles -> {out}")
    for a in data[:2]:
        print(f"  - {a.get('title','')[:60]} | {a.get('confidence')}")
    return payload

if __name__=="__main__":
    run_and_save()
