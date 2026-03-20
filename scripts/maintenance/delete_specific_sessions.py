import os
import sys
from sqlalchemy import text

# Add backend directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from app.db.session import SessionLocalUser
from app.models.workflow import WorkflowSession, AgentLog
from app.services.paper_trading import PaperOrder, PaperPosition

def delete_sessions(session_ids):
    db = SessionLocalUser()
    try:
        print(f"🚨 STARTING SESSION DELETION for IDs: {session_ids}...")
        
        for sid in session_ids:
            print(f"Processing Session: {sid}")
            
            # 1. Delete Agent Logs
            deleted_logs = db.query(AgentLog).filter(AgentLog.session_id == sid).delete()
            print(f"  - Deleted {deleted_logs} logs.")
            
            # 2. Delete Paper Orders (linked by session_id)
            deleted_orders = db.query(PaperOrder).filter(PaperOrder.session_id == sid).delete()
            print(f"  - Deleted {deleted_orders} orders.")
            
            # 3. Delete Paper Positions (linked by session_id)
            deleted_positions = db.query(PaperPosition).filter(PaperPosition.session_id == sid).delete()
            print(f"  - Deleted {deleted_positions} positions.")

            # 4. Delete Workflow Session
            # Use raw SQL for safety if ORM mapping is tricky or ID is string
            # But ORM should work fine.
            session = db.query(WorkflowSession).filter(WorkflowSession.id == sid).first()
            if session:
                db.delete(session)
                print(f"  - Deleted Workflow Session record.")
            else:
                print(f"  - Session record not found (might have been auto-deleted or not exist).")

        db.commit()
        print("✅ DELETION COMPLETE!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error deleting sessions: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    target_sessions = [
        "auto-BTC/USDT-1772703887",
        "auto-BTC/USDT-1772704141",
        "periodic-review-1772703844"
    ]
    delete_sessions(target_sessions)
