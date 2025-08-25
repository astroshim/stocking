import asyncio
import argparse
import websockets


async def main(host: str, port: int, path: str, stock_id: str, count: int, user_id: str):
    # uri = f"ws://{host}:{port}{path}?stock_id={stock_id}&user_id={user_id}"
    uri = f"wss://{host}{path}?stock_id={stock_id}&user_id={user_id}"
    print(f"Connecting to: {uri}")
    async with websockets.connect(uri) as websocket:
        print(f"Connected to: {uri}")
        received = 0
        while count <= 0 or received < count:
            msg = await websocket.recv()
            print(msg)
            received += 1


# 국내: uv run tests/ws_client.py --stock-id 035900 --count 5
# 해외: uv run tests/ws_client.py --stock-id RBAQAAPL --count 5

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple WS test client for stock price stream")
    parser.add_argument("--host", default="localhost", help="server host (default: localhost)")
    parser.add_argument("--port", type=int, default=5100, help="server port (default: 5100)")
    parser.add_argument("--path", default="/api/v1/trading/ws", help="WS path (default: /api/v1/trading/ws)")
    parser.add_argument("--stock-id", default="035250", help="stock id query value (default: 035250)")
    parser.add_argument("--count", type=int, default=10, help="number of messages to print (<=0 for infinite)")
    parser.add_argument("--user-id", default="shim", help="user id query value (default: 1)")
    args = parser.parse_args()

    asyncio.run(main(args.host, args.port, args.path, args.stock_id, args.count, args.user_id))
