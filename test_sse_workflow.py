
import json
import sseclient
import requests
import threading
import time

BASE_URL = "http://localhost:8000" # Inside container port is 8000
SESSION_ID = "test-session-manual-1"

def listen_sse():
    print(f"Connecting to SSE: {BASE_URL}/stream/logs/{SESSION_ID}")
    try:
        # Use requests for blocking SSE listener (easier for script)
        response = requests.get(f"{BASE_URL}/stream/logs/{SESSION_ID}", stream=True)
        client = sseclient.SSEClient(response)
        for event in client.events():
            print(f"SSE EVENT: {event.data}")
    except Exception as e:
        print(f"SSE Error: {e}")

def trigger_workflow():
    print("Waiting 2s before triggering workflow...")
    import time
    time.sleep(2)
    print(f"Triggering Workflow: {SESSION_ID}")
    try:
        res = requests.post(f"{BASE_URL}/workflow/run", json={
            "symbol": "BTC/USDT",
            "session_id": SESSION_ID
        })
        print(f"Trigger Response: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Trigger Error: {e}")

if __name__ == "__main__":
    # Start SSE listener in a thread
    t = threading.Thread(target=listen_sse)
    t.start()

    # Trigger workflow
    trigger_workflow()

    # Join
    t.join()
