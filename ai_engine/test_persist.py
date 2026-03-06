import httpx
import asyncio
import os
import time

async def test_create_session():
    url = os.getenv("BACKEND_URL", "http://backend:8000")
    session_id = f"test-manual-{int(time.time())}"
    print(f"Creating session {session_id} at {url}...")
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{url}/api/v1/workflow/session",
                json={"session_id": session_id, "symbol": "BTC/USDT"}
            )
            print(f"Create Session Status: {resp.status_code}")
            print(f"Response: {resp.text}")
            
            if resp.status_code == 200:
                print("Logging message...")
                resp_log = await client.post(
                    f"{url}/api/v1/workflow/{session_id}/log",
                    json={
                        "agent_id": "test_agent",
                        "log_type": "info",
                        "content": "Manual test log",
                        "artifact": None
                    }
                )
                print(f"Log Status: {resp_log.status_code}")
                print(f"Log Response: {resp_log.text}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_create_session())