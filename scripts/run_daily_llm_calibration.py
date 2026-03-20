import asyncio
import json
import os

import httpx


async def main():
    backend_url = os.getenv("BACKEND_URL", "http://localhost:3201")
    symbol = os.getenv("CALIBRATION_SYMBOL", "ETH/USDT")
    window_days = int(os.getenv("CALIBRATION_WINDOW_DAYS", "14"))
    url = f"{backend_url}/api/v1/calibration/run"
    params = {"symbol": symbol, "window_days": window_days}
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(url, params=params)
        response.raise_for_status()
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
