import asyncio
import aiohttp
import sys
import json
import re
import time

# Platforms with custom search parameters and error handling rules
PLATFORMS = {
    "GitHub": {
        "url": "https://github.com/{}",
        "error_type": "status",
        "error_code": 404
    },
    "Instagram": {
        "url": "https://www.instagram.com/{}/",
        "error_type": "keyword",
        "keyword": "Page not found"
    },
    "Twitter/X": {
        "url": "https://twitter.com/{}",
        "error_type": "status",
        "error_code": 404
    },
    "Reddit": {
        "url": "https://www.reddit.com/user/{}",
        "error_type": "status",
        "error_code": 404
    },
    "TikTok": {
        "url": "https://www.tiktok.com/@{}",
        "error_type": "status",
        "error_code": 404
    },
    "Pinterest": {
        "url": "https://www.pinterest.com/{}/",
        "error_type": "status",
        "error_code": 404
    }
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

async def extract_intelligence(html_text):
    """Regex engine to pull emails, phone patterns, and external tracking links from raw HTML"""
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', html_text)
    phones = re.findall(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3][-.\s]?\d{4}', html_text)
    links = re.findall(r'https?://(?:www\.)?(?:t\.me|linktr\.ee|wa\.me|beacons\.ai|instagram\.com|twitter\.com)/[a-zA-Z0-9_.-]+', html_text)
    
    filtered_emails = [e for e in set(emails) if not any(x in e for x in ['.png', '.jpg', '.svg', 'example.com', 'sentry'])]
    filtered_phones = [p for p in set(phones) if len(p.strip()) >= 10]
    
    return {
        "emails": filtered_emails,
        "phones": filtered_phones,
        "external_links": list(set(links))
    }

async def scan_platform(session, name, config, username):
    url = config["url"].format(username)
    start_time = time.time()
    
    try:
        async with session.get(url, headers=HEADERS, timeout=12, allow_redirects=True) as response:
            elapsed = round(time.time() - start_time, 2)
            
            if response.status != 200:
                return {"platform": name, "status": "Not Found", "url": url, "time": elapsed}
            
            html = await response.text()
            
            if config["error_type"] == "keyword" and config["keyword"].lower() in html.lower():
                return {"platform": name, "status": "Not Found", "url": url, "time": elapsed}
            
            intel = await extract_intelligence(html)
            
            return {
                "platform": name,
                "status": "Found",
                "url": url,
                "time": elapsed,
                "intelligence": intel
            }
            
    except asyncio.TimeoutError:
        return {"platform": name, "status": "Timeout", "url": url, "time": 0}
    except Exception:
        return {"platform": name, "status": "Error", "url": url, "time": 0}

async def main():
    if len(sys.argv) < 2:
        print("\n[-] Usage: python main.py <target_username>")
        print("[-] Example: python main.py johndoe\n")
        sys.exit(1)
        
    target = sys.argv[1]
    
    print("\n" + "="*65)
    print(f"       SPECTRE RECONNAISSANCE ENGINE (v1.0)")
    print("="*65)
    print(f"[*] Target Handle : {target}")
    print(f"[*] Target Modules: {len(PLATFORMS)} Global Platforms")
    print(f"[*] Status        : Scanning asynchronously...\n")
    
    total_start = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = [scan_platform(session, name, info, target) for name, info in PLATFORMS.items()]
        results = await asyncio.gather(*tasks)
        
    print("-" * 65)
    found_hits = 0
    full_report = []
    
    for res in results:
        full_report.append(res)
        if res["status"] == "Found":
            found_hits += 1
            print(f"[+] [FOUND] {res['platform']} ({res['time']}s) -> {res['url']}")
            
            intel = res.get("intelligence", {})
            if intel.get("emails") or intel.get("phones") or intel.get("external_links"):
                print(f"    └── 💡 Extracted Intel:")
                if intel["emails"]:
                    print(f"         • Emails Found : {intel['emails']}")
                if intel["phones"]:
                    print(f"         • Phones Found : {intel['phones']}")
                if intel["external_links"]:
                    print(f"         • Bio Links    : {intel['external_links']}")
        else:
            print(f"[-] [-----] {res['platform']} : Not Found")
            
    print("-" * 65)
    total_time = round(time.time() - total_start, 2)
    print(f"[*] Scan Completed in {total_time} seconds.")
    print(f"[*] Match Success Rate: {found_hits}/{len(PLATFORMS)} platforms active.")
    
    report_file = f"{target}_recon_report.json"
    with open(report_file, "w") as f:
        json.dump(full_report, f, indent=4)
    print(f"[*] Intelligence payload dumped successfully to: {report_file}\n")

if __name__ == "__main__":
    asyncio.run(main())
