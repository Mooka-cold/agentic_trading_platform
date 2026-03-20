
import sys
import os
from sqlalchemy import create_engine, text

sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from app.core.config import settings
except ImportError:
    from backend.app.core.config import settings

def upgrade_paper_account():
    print("Upgrading paper_accounts table...")
    try:
        db_url = settings.DATABASE_USER_URL
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # 1. Add Daily Start Balance
            conn.execute(text("ALTER TABLE paper_accounts ADD COLUMN IF NOT EXISTS daily_start_balance NUMERIC(20, 8) DEFAULT 100000.0;"))
            print("Added daily_start_balance.")
            
            # 2. Add High Watermark (Max Equity Seen)
            conn.execute(text("ALTER TABLE paper_accounts ADD COLUMN IF NOT EXISTS high_watermark NUMERIC(20, 8) DEFAULT 100000.0;"))
            print("Added high_watermark.")

            # 3. Add Lock Status (Circuit Breaker)
            conn.execute(text("ALTER TABLE paper_accounts ADD COLUMN IF NOT EXISTS is_locked BOOLEAN DEFAULT FALSE;"))
            print("Added is_locked.")
            
            # 4. Add Lock Reason
            conn.execute(text("ALTER TABLE paper_accounts ADD COLUMN IF NOT EXISTS lock_reason VARCHAR(255);"))
            print("Added lock_reason.")
            
            conn.commit()
            print("Upgrade Complete.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    upgrade_paper_account()
