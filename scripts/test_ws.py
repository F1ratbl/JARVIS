import asyncio
import websockets
import json

async def test():
    async with websockets.connect("ws://localhost:8000/ws") as websocket:
        msg = await websocket.recv()
        print("Received:", msg)

asyncio.run(test())
