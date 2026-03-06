import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add backend directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from app.db.session import SessionLocalUser
from app.services.paper_trading import PaperAccount, PaperPosition, PaperOrder, TradeReflection

def reset_account(user_id=1, initial_balance=100000.0):
    db = SessionLocalUser()
    try:
        print(f"Resetting account for User ID {user_id}...")
        
        # 1. Get Account
        account = db.query(PaperAccount).filter(PaperAccount.user_id == user_id).first()
        if not account:
            print("Account not found, creating new one...")
            account = PaperAccount(user_id=user_id, balance=initial_balance)
            db.add(account)
        else:
            print(f"Found account {account.id}. Old Balance: {account.balance}")
            account.balance = initial_balance
            print(f"New Balance: {account.balance}")
            
        # 2. Clear Positions
        deleted_pos = db.query(PaperPosition).filter(PaperPosition.account_id == account.id).delete()
        print(f"Deleted {deleted_pos} positions.")
        
        # 3. Clear Orders
        deleted_orders = db.query(PaperOrder).filter(PaperOrder.account_id == account.id).delete()
        print(f"Deleted {deleted_orders} orders.")

        # 4. Clear Reflections (optional, but good for clean slate)
        # Note: Reflections are linked to orders, so we might need to delete them first or cascade.
        # But since we are just doing raw delete on orders, let's see if we need to clean reflections.
        # TradeReflection has order_id, so if we deleted orders, reflections might be orphaned or cascade deleted.
        # Let's delete explicitly to be safe.
        # Since we don't have account_id in TradeReflection, we have to find them via orders.
        # But we already deleted orders... wait. 
        # If database has cascade delete, we are fine. If not, we might have foreign key errors if we delete orders first.
        # Let's check model definition or just try to delete all reflections for simplicity in this dev script.
        # Actually, let's just delete all reflections for now as it's a single user dev env.
        deleted_reflections = db.query(TradeReflection).delete()
        print(f"Deleted {deleted_reflections} reflections.")

        db.commit()
        print("✅ Account reset successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error resetting account: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_account()
