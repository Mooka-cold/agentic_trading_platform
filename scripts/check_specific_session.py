
import sys
import os
from sqlalchemy import create_engine, text

# Add project root to sys.path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from app.core.config import settings
except ImportError:
    from backend.app.core.config import settings

def check_session(session_id):
    print(f"Checking session: {session_id}")
    try:
        db_url = settings.DATABASE_USER_URL
        if not db_url:
             print("DATABASE_USER_URL not found in settings")
             return

        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Check Session
            query = text("SELECT * FROM workflow_sessions WHERE id = :id")
            result = conn.execute(query, {"id": session_id}).fetchone()
            
            if result:
                print("\n--- Session Found in DB ---")
                if hasattr(result, '_mapping'):
                    for key in result._mapping.keys():
                        print(f"{key}: {result._mapping[key]}")
                else:
                    print(result)
            else:
                print("\n--- Session NOT Found in DB ---")
                
            # Check Logs count
            log_query = text("SELECT count(*) FROM agent_logs WHERE session_id = :id")
            log_count = conn.execute(log_query, {"id": session_id}).scalar()
            print(f"\nLog Count: {log_count}")

            # Check Reflections
            ref_query = text("SELECT * FROM session_reflections WHERE session_id = :id")
            reflections = conn.execute(ref_query, {"id": session_id}).fetchall()
            print(f"\nReflections Count: {len(reflections)}")
            for r in reflections:
                print(f" - Stage: {r.stage}, Score: {r.score}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_session('auto-BTC/USDT-1773127051')
