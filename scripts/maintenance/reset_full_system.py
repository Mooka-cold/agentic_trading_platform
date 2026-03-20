import os
import sys
from sqlalchemy import text

# Add backend directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from app.db.session import SessionLocalUser
from app.services.paper_trading import PaperAccount, PaperPosition, PaperOrder, SessionReflection
from app.models.workflow import WorkflowSession, AgentLog
from app.models.signal import Signal

def full_system_reset(user_id=1, initial_balance=100000.0):
    db = SessionLocalUser()
    try:
        print(f"🚨 STARTING FULL SYSTEM RESET for User ID {user_id}...")
        
        # 1. Clear Trade Reflections (Child of Sessions)
        deleted_reflections = db.query(SessionReflection).delete()
        print(f"🗑️  Deleted {deleted_reflections} trade reflections.")
        
        # 2. Clear Paper Orders (Child of Accounts)
        deleted_orders = db.query(PaperOrder).delete()
        print(f"🗑️  Deleted {deleted_orders} paper orders.")
        
        # 3. Clear Paper Positions (Child of Accounts)
        deleted_positions = db.query(PaperPosition).delete()
        print(f"🗑️  Deleted {deleted_positions} paper positions.")
        
        # 4. Clear Agent Logs (Child of Workflow Sessions)
        deleted_logs = db.query(AgentLog).delete()
        print(f"🗑️  Deleted {deleted_logs} agent logs.")
        
        # 5. Clear Workflow Sessions
        deleted_sessions = db.query(WorkflowSession).delete()
        print(f"🗑️  Deleted {deleted_sessions} workflow sessions.")

        # 6. Clear Signals
        deleted_signals = db.query(Signal).delete()
        print(f"🗑️  Deleted {deleted_signals} signals.")

        # 7. Reset Account Balance
        account = db.query(PaperAccount).filter(PaperAccount.user_id == user_id).first()
        if not account:
            print("🆕 Account not found, creating new one...")
            account = PaperAccount(user_id=user_id, balance=initial_balance)
            db.add(account)
        else:
            print(f"💰 Found account {account.id}. Resetting balance from {account.balance} to {initial_balance}")
            account.balance = initial_balance
            
        db.commit()
        print("✅ SYSTEM RESET COMPLETE! All records wiped and balance restored.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error resetting system: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    full_system_reset()
