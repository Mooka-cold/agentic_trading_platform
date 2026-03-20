
import sys
import os
import json
from sqlalchemy import create_engine, text

sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from app.core.config import settings
except ImportError:
    from backend.app.core.config import settings

def inspect_reflection_content(session_id):
    print(f"Inspecting reflections for: {session_id}")
    try:
        db_url = settings.DATABASE_USER_URL
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Get Reflections
            query = text("SELECT stage, content, score, created_at FROM session_reflections WHERE session_id = :id ORDER BY created_at")
            results = conn.execute(query, {"id": session_id}).fetchall()
            
            if not results:
                print("No reflections found.")
                return

            print(f"Found {len(results)} reflections:\n")
            for i, r in enumerate(results):
                print(f"--- Reflection {i+1} ({r.stage}) ---")
                print(f"Score: {r.score}")
                print(f"Created: {r.created_at}")
                try:
                    content_json = json.loads(r.content)
                    print(json.dumps(content_json, indent=2))
                except:
                    print(f"Raw Content: {r.content}")
                print("\n")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_reflection_content('auto-BTC/USDT-1773127051')
