from fastapi import FastAPI, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Deque
from collections import defaultdict, deque



app = FastAPI()
# Keep active WebSocket connections
active_clients: List[WebSocket] = []

# --- Enable CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Allow all origins, restrict if needed
    allow_credentials=True,
    allow_methods=["*"],       # Allow all HTTP methods
    allow_headers=["*"],       # Allow all headers
)

# In-memory storage: list of (endereco, temperatura, timestamp)
storage: Dict[str, Deque] = defaultdict(deque)

# enderecos = {
#     "sensor_1": "Sensor baixo",
#     "sensor_2": "Sensor cima"
# }


async def broadcast_snapshot(obj):
    """Send the latest snapshot to all connected clients."""
    disconnected = []
    for ws in active_clients:
        try:
            await ws.send_json(obj)
        except Exception:
            disconnected.append(ws)
    # Remove broken connections
    for ws in disconnected:
        active_clients.remove(ws)

@app.get("/log")
async def log(endereco: str = Query(...), temperatura: float = Query(...)):
    """Receive and log endereco, temperatura, and timestamp."""
    now = datetime.now(timezone.utc)
    # endereco = enderecos[endereco]
    storage[endereco].append((now, temperatura))
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    if storage[endereco][0][0] < cutoff:
        storage[endereco].popleft()
    
    
    await broadcast_snapshot({
        "endereco": endereco, "temperatura": temperatura, "data": now.isoformat()
    })
    return {"status": "ok", "endereco": endereco, "temperatura": temperatura, "time": now.isoformat()}



@app.get("/dados")
def dados():
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    result = []

    for endereco, entries in storage.items():
        # Keep only last 10 minutes
        recent_entries = [(t, temp) for t, temp in entries if t >= cutoff]
        storage[endereco] = recent_entries  # cleanup

        if recent_entries:
            result.append({
                "endereco": endereco,
                "temperatura": [temp for t, temp in recent_entries],
                "data": [t.isoformat() for t, temp in recent_entries]
            })

    return result





@app.get('/')
def index():
    file = open('./frontend/index.html', 'r')
    return HTMLResponse(content=file.read(), status_code=200)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_clients.append(websocket)

    try:
        while True:
            # keep connection alive (no incoming messages expected)
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        if websocket in active_clients:
            active_clients.remove(websocket)