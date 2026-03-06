import sys
import os

# Add backend directory to path so we can import 'app'
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, '..') # backend/
sys.path.append(backend_dir)

from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from app.db.session import SessionLocalUser
from app.services.paper_trading import PaperAccount, PaperPosition
from decimal import Decimal
import datetime

def update_account():
    db: Session = SessionLocalUser()
    try:
        user_id = 1
        
        # 1. Get or Create Account
        stmt = select(PaperAccount).where(PaperAccount.user_id == user_id)
        account = db.execute(stmt).scalar_one_or_none()
        
        if not account:
            account = PaperAccount(user_id=user_id, balance=0.0)
            db.add(account)
            db.commit()
            db.refresh(account)
            print(f"Created new account {account.id}")
        else:
            account.balance = 0.0
            print(f"Updated account balance to 0 for {account.id}")
            
        # 2. Clear existing positions
        # Note: Delete statement needs to be executed properly
        stmt = delete(PaperPosition).where(PaperPosition.account_id == account.id)
        db.execute(stmt) # result.rowcount might not be available depending on driver
        print(f"Cleared existing positions")
        
        # 3. Add BTC Position (100k USD worth)
        # Using a fixed recent price for simulation start
        btc_price = Decimal("66000.00") 
        initial_capital = Decimal("100000.00")
        btc_qty = initial_capital / btc_price
        
        # Round to 6 decimal places
        btc_qty = round(btc_qty, 6)
        
        pos = PaperPosition(
            account_id=account.id,
            symbol="BTC/USDT",
            side="LONG",
            entry_price=btc_price,
            size=btc_qty,
            status="OPEN",
            opened_at=datetime.datetime.now()
        )
        db.add(pos)
        
        # 4. Commit
        db.commit()
        print(f"Added position: {btc_qty} BTC @ {btc_price} (Total Value: ${initial_capital})")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    update_account()
