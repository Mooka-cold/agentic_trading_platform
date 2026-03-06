import urllib.request
import os
import json

API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "7371d720fb1a8bd56b84a06ecef86e90da462110")
URL = f"https://cryptopanic.com/api/v1/posts/?auth_token={API_KEY}&public=true"

def test_urllib():
    print(f"Fetching {URL.replace(API_KEY, '***')} with urllib...")
    req = urllib.request.Request(
        URL, 
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    try:
        with urllib.request.urlopen(req) as response:
            print(f"Status: {response.status}")
            data = json.loads(response.read().decode())
            print(f"Results: {len(data.get('results', []))}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        print(e.read().decode()[:200])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_urllib()