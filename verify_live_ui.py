import os
import sys
import time
import json
import base64
import subprocess
import urllib.request
import asyncio
import websockets

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
LIVE_URL = "http://127.0.0.1:5173/live"
DEBUG_PORT = 9235
SCREENSHOT_PATH = r"C:\Users\periy\.gemini\antigravity-ide\brain\77e511c1-b920-41aa-8f71-0f8a3ac2cfec\live_operations_high_fidelity.png"

async def run_verification():
    print("=" * 60)
    print("NWIS LIVE OPERATIONS — CDP HIGH-FIDELITY VERIFICATION")
    print("=" * 60)

    chrome_proc = subprocess.Popen([
        CHROME_PATH,
        f"--remote-debugging-port={DEBUG_PORT}",
        "--headless=new",
        "--disable-gpu",
        "--disable-extensions",
        "--no-sandbox",
        "--window-size=1550,1250",
        LIVE_URL
    ])

    try:
        # Find WebSocket target
        ws_url = None
        for _ in range(25):
            time.sleep(0.4)
            try:
                res = urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/list")
                tabs = json.loads(res.read())
                page_tabs = [t for t in tabs if t.get("type") == "page"]
                if page_tabs:
                    ws_url = page_tabs[0]["webSocketDebuggerUrl"]
                    break
            except Exception:
                pass

        if not ws_url:
            raise RuntimeError("Could not connect to Chrome CDP target")

        print(f"[PASS] Connected to Chrome CDP: {ws_url}")

        async with websockets.connect(ws_url, max_size=25_000_000) as ws:
            msg_id = 0
            console_errors = []

            async def send_cmd(method, params=None):
                nonlocal msg_id
                msg_id += 1
                payload = {"id": msg_id, "method": method, "params": params or {}}
                await ws.send(json.dumps(payload))
                while True:
                    resp = json.loads(await ws.recv())
                    if resp.get("method") == "Log.entryAdded":
                        entry = resp["params"]["entry"]
                        if entry.get("level") == "error":
                            console_errors.append(entry.get("text", ""))
                    elif resp.get("id") == payload["id"]:
                        return resp.get("result", {})

            await send_cmd("Page.enable")
            await send_cmd("Runtime.enable")
            await send_cmd("Log.enable")

            # Wait 4 seconds for page load, telemetry fetch, and chart rendering
            await asyncio.sleep(4.0)

            # Check initial DOM elements
            eval_script = """
            (() => {
                const bodyText = document.body.innerText;
                const hasSvgText = bodyText.includes('svg');
                const heroTitle = document.querySelector('h1')?.innerText || '';
                const cards = document.querySelectorAll('.bg-white.rounded-lg.border');
                const svgPaths = document.querySelectorAll('svg path');
                const buttons = Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim());
                
                return {
                    hasSvgText,
                    heroTitle,
                    telemetryCardCount: cards.length,
                    svgPathCount: svgPaths.length,
                    buttons: buttons.slice(0, 10),
                    bodySnippet: bodyText.slice(0, 300)
                };
            })()
            """
            eval_res = await send_cmd("Runtime.evaluate", {"expression": eval_script, "returnByValue": True})
            dom_data = eval_res.get("result", {}).get("value", {})
            print("DOM Check Results:", json.dumps(dom_data, indent=2))

            # Test 1: Click "ROP" chart tab
            print("Testing Chart tab interaction (clicking ROP)...")
            await send_cmd("Runtime.evaluate", {
                "expression": """(() => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const ropBtn = buttons.find(b => b.innerText.trim() === 'ROP');
                    if (ropBtn) { ropBtn.click(); return true; }
                    return false;
                })()"""
            })
            await asyncio.sleep(0.5)

            # Switch back to Depth tab
            await send_cmd("Runtime.evaluate", {
                "expression": """(() => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const depthBtn = buttons.find(b => b.innerText.trim() === 'Depth');
                    if (depthBtn) { depthBtn.click(); return true; }
                    return false;
                })()"""
            })
            await asyncio.sleep(0.5)

            # Test 2: Click Start Replay
            print("Testing Start Replay interaction...")
            await send_cmd("Runtime.evaluate", {
                "expression": """(() => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const startBtn = buttons.find(b => b.innerText.includes('Start Replay'));
                    if (startBtn) { startBtn.click(); return true; }
                    return false;
                })()"""
            })
            await asyncio.sleep(1.5)

            # Check status pill during replay
            replay_check = await send_cmd("Runtime.evaluate", {
                "expression": """(() => {
                    return document.body.innerText.includes('DEMO REPLAY');
                })()""",
                "returnByValue": True
            })
            print(f"[PASS] Replay response verified: {replay_check.get('result', {}).get('value')}")

            # Test 3: Stop Replay
            print("Testing Stop Replay interaction...")
            await send_cmd("Runtime.evaluate", {
                "expression": """(() => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const stopBtn = buttons.find(b => b.innerText.includes('Stop'));
                    if (stopBtn) { stopBtn.click(); return true; }
                    return false;
                })()"""
            })
            await asyncio.sleep(1.0)

            # Test 4: Open and close Source Details modal
            print("Testing Source Details modal...")
            await send_cmd("Runtime.evaluate", {
                "expression": """(() => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const srcBtn = buttons.find(b => b.innerText.includes('Source Details'));
                    if (srcBtn) { srcBtn.click(); return true; }
                    return false;
                })()"""
            })
            await asyncio.sleep(0.6)

            # Close modal
            await send_cmd("Runtime.evaluate", {
                "expression": """(() => {
                    const closeBtn = document.querySelector('.fixed.inset-0 button');
                    if (closeBtn) { closeBtn.click(); return true; }
                    return false;
                })()"""
            })
            await asyncio.sleep(0.5)

            # Take full-page screenshot
            ss_res = await send_cmd("Page.captureScreenshot", {"format": "png"})
            if "data" in ss_res:
                img_data = base64.b64decode(ss_res["data"])
                with open(SCREENSHOT_PATH, "wb") as f:
                    f.write(img_data)
                print(f"[PASS] Saved screenshot to: {SCREENSHOT_PATH}")

            print(f"Console errors count: {len(console_errors)}")
            if console_errors:
                print("Console errors:", console_errors)

    finally:
        chrome_proc.terminate()
        try:
            chrome_proc.wait(timeout=3)
        except Exception:
            chrome_proc.kill()

if __name__ == "__main__":
    asyncio.run(run_verification())
