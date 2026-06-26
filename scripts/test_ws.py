import asyncio
import websockets


async def check_ws():
    async with websockets.connect("ws://localhost:8000/ws") as websocket:
        msg = await websocket.recv()
        print("Received:", msg)


if __name__ == "__main__":
    asyncio.run(check_ws())
