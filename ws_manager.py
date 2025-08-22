from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        # Map agent_id -> WebSocket
        self.active_connections: dict[int, WebSocket] = {}

    async def connect(self, agent_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[agent_id] = websocket

    def disconnect(self, agent_id: int):
        if agent_id in self.active_connections:
            del self.active_connections[agent_id]

    async def send_to_agent(self, agent_id: int, message: dict):
        websocket = self.active_connections.get(agent_id)
        if websocket:
            await websocket.send_json(message)

    async def broadcast(self, message: dict):
        for ws in self.active_connections.values():
            await ws.send_json(message)


# Global manager instance
manager = ConnectionManager()
