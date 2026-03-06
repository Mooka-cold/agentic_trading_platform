import httpx
import asyncio
import os

async def test_conn():
    url = os.getenv("BACKEND_URL", "http://backend:8000")
    print(f"Testing connection to {url}...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{url}/health")
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_conn())