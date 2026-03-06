import asyncio
import websockets
import json
from datetime import datetime

async def test_binance_stream():
    # Try Stream URL (Spot) - often more stable for public data if futures is blocked
    uri = "wss://stream.binance.com:9443/ws/btcusdt@kline_1m"
    
    print(f"🔌 Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected! Waiting for messages...")
            
            # Read 5 messages then exit
            for i in range(5):
                message = await websocket.recv()
                data = json.loads(message)
                
                k = data['k']
                ts = datetime.fromtimestamp(data['E']/1000).strftime('%H:%M:%S')
                
                print(f"\n[{ts}] Event: {data['e']}")
                print(f"   Symbol: {data['s']}")
                print(f"   Price: {k['c']} (High: {k['h']}, Low: {k['l']})")
                print(f"   Volume: {k['v']}")
                print(f"   IsClosed: {k['x']}")
                
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_binance_stream())
