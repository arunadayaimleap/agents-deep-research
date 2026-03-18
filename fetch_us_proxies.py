#!/usr/bin/env python3
"""
Fetch US proxy list from free-proxy-list.net and save to us_proxies.json.
Source: https://free-proxy-list.net/en/us-proxy.html
"""
import json
import re
import sys
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Install: pip install requests beautifulsoup4")
    sys.exit(1)

URL = "https://free-proxy-list.net/en/us-proxy.html"
OUTPUT = Path(__file__).resolve().parent / "us_proxies.json"


def fetch_proxies():
    print(f"Fetching {URL}...")
    r = requests.get(URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    proxies = []
    # Table has IP and Port in first two columns
    table = soup.find("table", class_="table")
    if table:
        for row in table.find_all("tr")[1:]:  # skip header
            cells = row.find_all("td")
            if len(cells) >= 2:
                ip = cells[0].get_text(strip=True)
                port = cells[1].get_text(strip=True)
                if ip and port and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
                    proxies.append({
                        "ip": ip,
                        "port": int(port) if port.isdigit() else port,
                        "url": f"http://{ip}:{port}",
                    })

    if not proxies:
        # Fallback: try to find raw list in textarea or script
        for elem in soup.find_all(["textarea", "script", "pre"]):
            text = elem.get_text()
            for m in re.finditer(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)", text):
                ip, port = m.groups()
                proxies.append({"ip": ip, "port": int(port), "url": f"http://{ip}:{port}"})

    return list({p["url"]: p for p in proxies}.values())  # dedupe


def main():
    proxies = fetch_proxies()
    print(f"Found {len(proxies)} US proxies")

    data = {"source": URL, "count": len(proxies), "proxies": proxies}
    OUTPUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Saved to {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
