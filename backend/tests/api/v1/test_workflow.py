import sys
import os
# Add backend directory to sys.path so we can import 'main'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from fastapi.testclient import TestClient
from app.models.workflow import WorkflowSession, AgentLog
from app.db.base import Base
from app.db.session import engine_user
from main import app

client = TestClient(app)

def test_workflow_lifecycle():
    # 1. Create Session
    session_id = "test-session-unit-1"
    test_symbol = "TEST-BTC"
    print(f"Creating session: {session_id}")
    res = client.post("/api/v1/workflow/session", json={"session_id": session_id, "symbol": test_symbol})
    
    assert res.status_code == 200
    assert res.json()["status"] in ["created", "exists"]
    
    # 2. Add Log
    print("Adding log...")
    res = client.post(f"/api/v1/workflow/{session_id}/log", json={
        "agent_id": "analyst",
        "log_type": "process",
        "content": "Unit Testing...",
        "artifact": {"test": True}
    })
    assert res.status_code == 200
    
    # 3. Get Latest
    print("Fetching latest workflow...")
    res = client.get(f"/api/v1/workflow/latest?symbol={test_symbol}")
    assert res.status_code == 200
    data = res.json()
    
    assert data["session"] is not None
    print(f"Latest Session ID: {data['session']['id']}")
    
    # Check logs
    logs = data["session"]["logs"]
    found = False
    for log in logs:
        if log["content"] == "Unit Testing...":
            found = True
            break
    
    if found:
        print("✅ Log found! Workflow API Test Passed!")
    else:
        print("❌ Log NOT found! Test Failed.")
        # Print logs for debug
        print(logs)
    
    assert found

if __name__ == "__main__":
    test_workflow_lifecycle()
