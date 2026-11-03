import asyncio
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from main import PLATFORMS, aiohttp, check_platform

app = FastAPI(title="Spectre OSINT Suite", version="1.1.0")

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
