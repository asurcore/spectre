import asyncio
import json
import os
import random
import re
import time
import aiohttp
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

CONFIG_FILE = "config.json"

if not os.path.exists(CONFIG_FILE):
    # Fallback default config if file is missing
    default_config = {
        "settings": {"timeout": 10, "user_agent": "Mozilla/5.0", "proxy_list": []},
        "platforms": {
            "Instagram": {"url": "https://www.instagram.com/{}/", "error_type": "status_code", "error_code": 404, "headers": {}},
            "GitHub": {"url": "https://github.com/{}", "error_type": "status_code", "error_code": 404, "headers": {}},
            "Reddit": {"url": "https://www.reddit.com/user/{}", "error_type": "status_code", "error_code": 404, "headers": {}},
            "Pinterest": {"url": "https://www.pinterest.com/{}/", "error_type": "status_code", "error_code": 404, "headers": {}}
        }
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(default_config, f, indent=4)

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

def extract_intel(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    found = {}
    for key, pattern in PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            found[key] = list(set(matches))
    return found

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
            if response.status == 200:
                html = await response.text()
                intel = extract_intel(html)
                return {"platform": name, "status": "Found", "time": elapsed, "url": url, "intel": intel}
            else:
                return {"platform": name, "status": "Not Found", "time": elapsed}
    except Exception:
        return {"platform": name, "status": "Error", "time": round(time.time() - start_time, 2)}

# FastAPI App Initialization
app = FastAPI(title="Spectre OSINT Suite", version="1.2.0")

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Spectre // OSINT Dashboard</title>
        <style>
            body { font-family: monospace; background: #0f172a; color: #38bdf8; padding: 40px; }
            .container { max-width: 650px; margin: auto; background: #1e293b; padding: 30px; border-radius: 8px; border: 1px solid #334155; }
            input { width: 68%; padding: 10px; background: #0f172a; border: 1px solid #475569; color: white; border-radius: 4px; font-family: monospace; }
            button { padding: 10px 20px; background: #0284c7; color: white; border: none; border-radius: 4px; cursor: pointer; font-family: monospace; }
            button:hover { background: #0369a1; }
            pre { background: #0f172a; padding: 15px; border-radius: 4px; overflow-x: auto; color: #f8fafc; font-size: 13px; max-height: 400px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>👻 Spectre // OSINT Dashboard</h2>
            <p>Enter target username:</p>
            <input type="text" id="username" placeholder="username...">
            <button onclick="runScan()">Run Scan</button>
            <h3>Execution Output:</h3>
            <pre id="output">Waiting for target...</pre>
        </div>
        <script>
            async function runScan() {
                const user = document.getElementById('username').value;
                if(!user) return alert('Enter a username first!');
                document.getElementById('output').innerText = "Scanning " + user + " across targets...";
                const res = await fetch('/api/scan/' + user);
                const data = await res.json();
                document.getElementById('output').innerText = JSON.stringify(data, null, 2);
            }
        </script>
    </body>
    </html>
    """

@app.get("/api/scan/{username}")
async def api_scan(username: str):
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_platform(session, name, data, username) for name, data in PLATFORMS.items()]
        responses = await asyncio.gather(*tasks)
        return {"target": username, "results": list(responses)}
