import asyncio
import websockets
import json
from datetime import datetime

async def test_okx_stream():
    # OKX Business WebSocket URL (for candles)
    uri = "wss://ws.okx.com:8443/ws/v5/business"
    
    print(f"🔌 Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected! Subscribing to candle1m...")
            
            # Subscribe Request
            subscribe_msg = {
                "op": "subscribe",
                "args": [
                    {
                        "channel": "candle1m",
                        "instId": "BTC-USDT-SWAP"
                    }
                ]
            }
            await websocket.send(json.dumps(subscribe_msg))
            
            # Read loop
            count = 0
            while count < 5:
                message = await websocket.recv()
                data = json.loads(message)
                
                # Check for subscription confirmation
                if "event" in data and data["event"] == "subscribe":
                    print(f"✅ Subscription Confirmed: {data}")
                    continue
                
                # Filter for candle data
                if "data" in data:
                    candle = data['data'][0]
                    # Format: [ts, open, high, low, close, vol, volCcy, volCcyQuote, confirm]
                    ts_ms = int(candle[0])
                    ts_str = datetime.fromtimestamp(ts_ms/1000).strftime('%H:%M:%S')
                    
                    price = candle[4]
                    high = candle[2]
                    low = candle[3]
                    confirm = candle[8]
                    
                    print(f"\n[{ts_str}] Event: candle1m")
                    print(f"   Symbol: {data['arg']['instId']}")
                    print(f"   Price: {price} (High: {high}, Low: {low})")
                    print(f"   IsClosed: {confirm == '1'}")
                    
                    count += 1
                else:
                    print(f"Info: {message}")
                
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_okx_stream())
