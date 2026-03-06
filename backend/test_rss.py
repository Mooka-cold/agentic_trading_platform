import urllib.request

URL = "https://cryptopanic.com/news/rss/"

def test_rss():
    req = urllib.request.Request(
        URL, 
        headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'}
    )
    try:
        with urllib.request.urlopen(req) as response:
            print(f"Status: {response.status}")
            print(response.read().decode()[:200])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_rss()