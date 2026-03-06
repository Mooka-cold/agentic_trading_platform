import httpx
import asyncio
import os
import json

# Replace with your actual key if not in env, or rely on env
API_KEY = "FAKE_KEY_12345"

URLS_TO_TEST = [
    f"https://cryptopanic.com/api/v1/posts/?auth_token={API_KEY}&public=true",
]

async def investigate_cryptopanic():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    }
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for url in URLS_TO_TEST:
            print(f"\nTesting: {url.replace(API_KEY, '***')}")
            try:
                resp = await client.get(url, headers=headers)
                print(f"Status: {resp.status_code}")
                if resp.status_code == 200:
                    print("SUCCESS!")
                    data = resp.json()
                    results = data.get("results", [])
                    print(f"Results: {len(results)}")
                    
                    if results:
                        first_item = results[0]
                        print("\n--- First Item Structure ---")
                        print(json.dumps(first_item, indent=2))
                    break
                else:
                    print(f"Response: {resp.text[:100]}...")
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(investigate_cryptopanic())