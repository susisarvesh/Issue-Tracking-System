from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from database import engine, Base
from routers import tickets, customers, agents, products
from ws_manager import manager   # ✅ updated import

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Issue Ticketing Platform API")

# ---------------- ENABLE CORS ----------------
origins = [
    "http://localhost:5173",  # Vite default React dev server
    "http://127.0.0.1:5173",  # Sometimes it uses 127.0.0.1
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # or ["*"] to allow all (useful for dev)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(tickets.router)
app.include_router(customers.router)
app.include_router(agents.router)
app.include_router(products.router)


@app.get("/")
def root():
    return {"message": "Ticketing API running 🚀"}


# ---------------- WEBSOCKET ENDPOINT ----------------
@app.websocket("/ws/agents/{agent_id}")
async def websocket_endpoint(websocket: WebSocket, agent_id: int):
    await manager.connect(agent_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(agent_id)
