#!/usr/bin/env python3
"""
Monitor Server - Central hub for real-time test monitoring.
Receives screenshot streams from test jobs and broadcasts to dashboard.
"""

import asyncio
import base64
import json
import os
import time
from pathlib import Path
from typing import Dict, Set

try:
    import uvicorn
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
except ImportError:
    print("Installing dependencies...")
    import subprocess
    subprocess.run(["pip", "install", "fastapi", "uvicorn[standard]"], check=True)
    import uvicorn
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Test Lab Monitor")

# Store connected dashboard clients
dashboard_clients: Set[WebSocket] = set()

# Store device states
device_states: Dict[str, dict] = {}

# Store latest screenshots (base64)
latest_screenshots: Dict[str, str] = {}

DASHBOARD_HTML = Path(__file__).parent / "dashboard.html"


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    if DASHBOARD_HTML.exists():
        return DASHBOARD_HTML.read_text(encoding="utf-8")
    return "<h1>Dashboard not found</h1>"


@app.post("/api/device/register")
async def register_device(request: Request):
    data = await request.json()
    device_id = data.get("device_id", "unknown")
    device_states[device_id] = {
        "device_id": device_id,
        "api_level": data.get("api_level", "?"),
        "device_name": data.get("device_name", "Unknown"),
        "screen_size": data.get("screen_size", "?"),
        "status": "registered",
        "last_update": time.time(),
        "step": 0,
        "screens_found": 0
    }
    await broadcast_dashboard_update()
    return {"status": "ok", "device_id": device_id}


@app.post("/api/screenshot")
async def receive_screenshot_generic(request: Request):
    data = await request.json()
    image_b64 = data.get("image", "")
    step = data.get("step", 0)
    device_id = data.get("device_id", f"device_{int(time.time())}")
    if device_id not in device_states:
        device_states[device_id] = {
            "device_id": device_id,
            "api_level": "?",
            "device_name": device_id,
            "screen_size": "?",
            "status": "streaming",
            "last_update": time.time(),
            "step": step,
            "screens_found": 0
        }
    device_states[device_id]["last_update"] = time.time()
    device_states[device_id]["step"] = step
    device_states[device_id]["status"] = "streaming"
    latest_screenshots[device_id] = image_b64
    await broadcast_screenshot(device_id, image_b64, step, 0)
    return {"status": "ok"}


@app.post("/api/device/{device_id}/screenshot")
async def receive_screenshot(device_id: str, request: Request):
    data = await request.json()
    image_b64 = data.get("image", "")
    step = data.get("step", 0)
    screens_found = data.get("screens_found", 0)

    if device_id not in device_states:
        device_states[device_id] = {
            "device_id": device_id,
            "api_level": "?",
            "device_name": "Unknown",
            "screen_size": "?",
            "status": "streaming",
            "last_update": time.time(),
            "step": step,
            "screens_found": screens_found
        }

    device_states[device_id]["last_update"] = time.time()
    device_states[device_id]["step"] = step
    device_states[device_id]["screens_found"] = screens_found
    device_states[device_id]["status"] = "streaming"

    # Store screenshot
    latest_screenshots[device_id] = image_b64

    # Broadcast to dashboard clients
    await broadcast_screenshot(device_id, image_b64, step, screens_found)

    return {"status": "ok"}


@app.post("/api/device/{device_id}/status")
async def update_status(device_id: str, request: Request):
    data = await request.json()
    if device_id not in device_states:
        device_states[device_id] = {"device_id": device_id}

    device_states[device_id].update({
        "status": data.get("status", "unknown"),
        "last_update": time.time(),
        "step": data.get("step", 0),
        "screens_found": data.get("screens_found", 0)
    })

    await broadcast_dashboard_update()
    return {"status": "ok"}


@app.get("/api/devices")
async def list_devices():
    return {"devices": list(device_states.values())}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    dashboard_clients.add(websocket)
    try:
        # Send current state
        await websocket.send_json({
            "type": "init",
            "devices": list(device_states.values()),
            "screenshots": {k: v for k, v in latest_screenshots.items()}
        })
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Handle ping/pong
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        dashboard_clients.discard(websocket)
    except:
        dashboard_clients.discard(websocket)


@app.websocket("/ws/device")
async def device_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            try:
                pos = 0
                dev_len = int.from_bytes(data[pos:pos+2], "big"); pos += 2
                device_id = data[pos:pos+dev_len].decode(); pos += dev_len
                step_len = int.from_bytes(data[pos:pos+2], "big"); pos += 2
                step = data[pos:pos+step_len].decode(); pos += step_len
                jpeg_data = data[pos:]
                b64 = base64.b64encode(jpeg_data).decode()
                if device_id not in device_states:
                    device_states[device_id] = {
                        "device_id": device_id, "api_level": "?",
                        "device_name": device_id, "screen_size": "?",
                        "status": "streaming", "last_update": time.time(),
                        "step": int(step), "screens_found": 0
                    }
                device_states[device_id]["last_update"] = time.time()
                device_states[device_id]["step"] = int(step)
                device_states[device_id]["status"] = "streaming"
                latest_screenshots[device_id] = b64
                await broadcast_screenshot(device_id, b64, int(step), 0)
            except Exception as e:
                print(f"  [ws] Parse error: {e}")
    except WebSocketDisconnect:
        pass
    except:
        pass


async def broadcast_screenshot(device_id: str, image_b64: str, step: int, screens_found: int):
    message = json.dumps({
        "type": "screenshot",
        "device_id": device_id,
        "image": image_b64,
        "step": step,
        "screens_found": screens_found,
        "timestamp": time.time()
    })
    disconnected = set()
    for client in dashboard_clients:
        try:
            await client.send_text(message)
        except:
            disconnected.add(client)
    dashboard_clients.difference_update(disconnected)


async def broadcast_dashboard_update():
    message = json.dumps({
        "type": "devices_update",
        "devices": list(device_states.values())
    })
    disconnected = set()
    for client in dashboard_clients:
        try:
            await client.send_text(message)
        except:
            disconnected.add(client)
    dashboard_clients.difference_update(disconnected)


if __name__ == "__main__":
    port = int(os.environ.get("MONITOR_PORT", "8765"))
    print(f"Monitor server starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
