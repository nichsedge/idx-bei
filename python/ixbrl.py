from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import os

output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

# Process all HTML files in the inlineXBRL directory
for filename in os.listdir("inlineXBRL"):
    if filename.endswith(".html"):
        file_path = os.path.join("inlineXBRL", filename)
        with open(file_path, "r", encoding="utf-8") as file:
            soup = BeautifulSoup(file, "lxml-xml")

        # Extract the title
        title_tag = soup.find("p", class_="titleLeft")
        title = title_tag.text.strip() if title_tag else "N/A"

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

        # Optional: Print results (for debugging each file)
        # for r in results:
        #     print(r)

        # Write to JSON
        import json

        # Sanitize title for filename
        sanitized_title = "".join([c for c in title if c.isalnum() or c in (' ', '.', '_')]).strip()
        sanitized_title = sanitized_title.replace(' ', '_')
        if not sanitized_title:
            sanitized_title = os.path.splitext(filename)[0] # Use original filename if title is empty

        json_filename = f"{sanitized_title}.json"
        with open(os.path.join(output_dir, json_filename), "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4)
