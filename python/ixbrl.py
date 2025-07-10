from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# Load the XHTML file (replace with your actual file path)
with open("inlineXBRL/1000000.html", "r", encoding="utf-8") as file:
    soup = BeautifulSoup(file, "lxml-xml")

# Extract all iXBRL elements
ix_tags = soup.find_all(["ix:nonFraction", "ix:nonNumeric", "ix:fraction"])

# Store results
results = []

for tag in ix_tags:
    data = {
        "tag": tag.name,
        "name": tag.get("name"),
        "contextRef": tag.get("contextRef"),
        "unitRef": tag.get("unitRef"),
        "decimals": tag.get("decimals"),
        "value": tag.text.strip()
    }
    results.append(data)

# Optional: Print results
for r in results:
    print(r)

# Optional: Write to CSV
import csv

with open("ixbrl_data.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["tag", "name", "contextRef", "unitRef", "decimals", "value"])
    writer.writeheader()
    writer.writerows(results)
