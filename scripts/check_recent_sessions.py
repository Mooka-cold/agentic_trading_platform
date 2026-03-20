
import sys
import os
from sqlalchemy import create_engine, text

sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from app.core.config import settings
except ImportError:
    from backend.app.core.config import settings

def check_recent_sessions(limit=50):
    try:
        db_url = settings.DATABASE_USER_URL
        engine = create_engine(db_url)
        with engine.connect() as conn:
            query = text("SELECT id, start_time FROM workflow_sessions ORDER BY start_time DESC LIMIT :limit")
            result = conn.execute(query, {"limit": limit}).fetchall()
            
            print(f"Top {limit} Recent Sessions:")
            found = False
            for i, row in enumerate(result):
                is_target = row[0] == 'auto-BTC/USDT-1773127051'
                marker = " <--- TARGET" if is_target else ""
                if is_target: found = True
                print(f"{i+1}. {row[0]} ({row[1]}){marker}")
            
            if not found:
                print("\nTarget session is NOT in the top list.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_recent_sessions(50)
