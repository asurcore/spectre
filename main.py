cat << 'EOF' > main.py
import asyncio
import json
import os
import random
import re
import sys
import time
import aiohttp
from bs4 import BeautifulSoup

CONFIG_FILE = "config.json"

if not os.path.exists(CONFIG_FILE):
    print(f"[!] Error: {CONFIG_FILE} not found.")
    sys.exit(1)

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

settings = config.get("settings", {})
PLATFORMS = config.get("platforms", {})
PROXIES = settings.get("proxy_list", [])

PATTERNS = {
    "email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    "phone": r"\+?[0-9][0-9()\-\s]{7,15}[0-9]"
}

def get_random_proxy():
    return random.choice(PROXIES) if PROXIES else None

async def check_platform(session, name, data, username):
    url = data["url"].format(username)
    timeout = settings.get("timeout", 10)
    
    headers = {"User-Agent": settings.get("user_agent", "Mozilla/5.0")}
    if "headers" in data and data["headers"]:
        headers.update(data["headers"])

    proxy = get_random_proxy()
    start_time = time.time()

    try:
        async with session.get(url, headers=headers, proxy=proxy, timeout=timeout, allow_redirects=True) as response:
            elapsed = round(time.time() - start_time, 2)
            
            if data["error_type"] == "status_code":
                if response.status == 200:
                    html = await response.text()
                    intel = extract_intel(html)
                    return {"platform": name, "status": "Found", "time": elapsed, "url": url, "intel": intel}
                else:
                    return {"platform": name, "status": "Not Found", "time": elapsed}
    except Exception:
        return {"platform": name, "status": "Error", "time": round(time.time() - start_time, 2)}

def extract_intel(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    
    found = {}
    for key, pattern in PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            found[key] = list(set(matches))
    return found

async def scan(username):
    print(f"\n[*] Scanning target: {username}")
    print("-" * 60)
    
    results = []
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_platform(session, name, data, username) for name, data in PLATFORMS.items()]
        responses = await asyncio.gather(*tasks)
        
        for res in responses:
            if res["status"] == "Found":
                print(f"[+] {res['platform']} ({res['time']}s) -> {res['url']}")
                if res.get("intel"):
                    print(f"    └── Extracted Info: {res['intel']}")
            else:
                print(f"[-] {res['platform']}: Not Found")
            results.append(res)
    
    print("-" * 60)
    report_name = f"{username}_report.json"
    with open(report_name, "w") as f:
        json.dump(results, f, indent=4)
    print(f"[*] Report saved to {report_name}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <username>")
        sys.exit(1)
    
    target = sys.argv[1]
    asyncio.run(scan(target))
EOF
