import asyncio
import aiohttp
import sys
import json
import re
import time
import os

CONFIG_PATH = "config.json"

if not os.path.exists(CONFIG_PATH):
    print(f"[!] Critical: Config not found at {CONFIG_PATH}")
    sys.exit(1)

with open(CONFIG_PATH, "r") as f:
    PLATFORMS = json.load(f).get("platforms", {})

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

async def extract_intel(html):
    emails = set(re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', html))
    phones = set(re.findall(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3][-.\s]?\d{4}', html))
    links = set(re.findall(r'https?://(?:www\.)?(?:t\.me|linktr\.ee|wa\.me|beacons\.ai|instagram\.com|twitter\.com)/[a-zA-Z0-9_.-]+', html))
    
    valid_emails = [e for e in emails if not any(x in e for x in ['.png', '.jpg', '.svg', 'example.com', 'sentry'])]
    valid_phones = [p for p in phones if len(p.strip()) >= 10]
    
    return {
        "emails": valid_emails,
        "phones": valid_phones,
        "external_links": list(links)
    }

async def check_target(session, name, cfg, username):
    url = cfg["url"].format(username)
    start = time.time()
    try:
        async with session.get(url, headers=HEADERS, timeout=12, allow_redirects=True) as resp:
            elapsed = round(time.time() - start, 2)
            if resp.status != 200:
                return {"platform": name, "status": "Not Found", "url": url, "time": elapsed}
            
            body = await resp.text()
            if cfg.get("error_type") == "keyword" and cfg["keyword"].lower() in body.lower():
                return {"platform": name, "status": "Not Found", "url": url, "time": elapsed}
            
            intel = await extract_intel(body)
            return {"platform": name, "status": "Found", "url": url, "time": elapsed, "intelligence": intel}
    except asyncio.TimeoutError:
        return {"platform": name, "status": "Timeout", "url": url, "time": 0}
    except Exception:
        return {"platform": name, "status": "Error", "url": url, "time": 0}

async def main():
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <username>")
        sys.exit(1)
        
    target = sys.argv[1]
    print(f"\n[*] Spectre Recon Engine v1.0")
    print(f"[*] Target: {target} | Modules: {len(PLATFORMS)}\n")
    
    start_time = time.time()
    async with aiohttp.ClientSession() as session:
        tasks = [check_target(session, name, cfg, target) for name, cfg in PLATFORMS.items()]
        results = await asyncio.gather(*tasks)
        
    print("-" * 60)
    hits = 0
    report = []
    for r in results:
        report.append(r)
        if r["status"] == "Found":
            hits += 1
            print(f"[+] {r['platform']} ({r['time']}s) -> {r['url']}")
            intel = r.get("intelligence", {})
            if intel.get("emails") or intel.get("phones") or intel.get("external_links"):
                print(f"    └── Data: {intel}")
        else:
            print(f"[-] {r['platform']}: Not Found")
            
    print("-" * 60)
    print(f"[*] Completed in {round(time.time() - start_time, 2)}s | Matches: {hits}/{len(PLATFORMS)}")
    
    outfile = f"{target}_report.json"
    with open(outfile, "w") as f:
        json.dump(report, f, indent=4)
    print(f"[*] Report saved to {outfile}\n")

if __name__ == "__main__":
    asyncio.run(main())
