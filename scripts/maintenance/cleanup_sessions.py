from sqlalchemy import create_engine, text
from app.core.config import settings

def cleanup_bad_sessions():
    engine = create_engine(settings.DATABASE_USER_URL)
    with engine.connect() as conn:
        try:
            print("Cleaning up ALL sessions...")
            
            # 1. Delete Agent Logs
            conn.execute(text("DELETE FROM agent_logs"))
            print("Deleted all logs.")
            
            # 2. Delete Reflections
            conn.execute(text("DELETE FROM trade_reflections"))
            print("Deleted all reflections.")
            
            # 3. Delete Paper Orders
            conn.execute(text("DELETE FROM paper_orders"))
            print("Deleted all orders.")
            
            # 4. Delete Workflow Sessions
            conn.execute(text("DELETE FROM workflow_sessions"))
            print("Deleted all sessions.")
            
            conn.commit()
            print("Cleanup complete.")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
            conn.rollback()

if __name__ == "__main__":
    cleanup_bad_sessions()