import httpx
import asyncio
import sys

async def check_session():
    session_id = sys.argv[1] if len(sys.argv) > 1 else "test-manual-1772640641"
    url = f"http://localhost:8000/api/v1/workflow/session/{session_id}"
    print(f"Checking {url}...")
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            logs = data['session']['logs']
            print(f"Logs count: {len(logs)}")
            if logs:
                print(f"First Log: {logs[0]['content']}")
        else:
            print(resp.text)

if __name__ == "__main__":
    asyncio.run(check_session())