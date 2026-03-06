import os
import sys
from sqlalchemy import text, select
import datetime

# Add backend directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from app.db.session import SessionLocalUser
from app.services.paper_trading import PaperOrder, TradeReflection

def inspect_session(session_id):
    db = SessionLocalUser()
    try:
        print(f"🔍 INSPECTING SESSION: {session_id}")
        
        # 1. Find Orders
        orders = db.execute(select(PaperOrder).where(PaperOrder.session_id == session_id)).scalars().all()
        
        if not orders:
            print("❌ No orders found for this session.")
        else:
            for order in orders:
                print(f"\n📦 ORDER: {order.id}")
                print(f"   - Status: {order.status}")
                print(f"   - Created At: {order.created_at}")
                print(f"   - Filled At: {order.filled_at}")
                # Check for closed_at? PaperOrder doesn't have closed_at, PaperPosition does.
                # But get_pending_reflections uses PaperOrder.created_at as proxy for "close"? 
                # Let's check logic.
                
                # Check Reflections
                reflections = db.execute(select(TradeReflection).where(TradeReflection.session_id == session_id)).scalars().all()
                print(f"   - Reflections: {[r.stage for r in reflections]}")
                
                # Calculate elapsed time
                now = datetime.datetime.now(datetime.timezone.utc)
                if order.created_at:
                    elapsed = (now - order.created_at).total_seconds() / 3600
                    print(f"   - Elapsed Hours: {elapsed:.2f}")
                    
                    # Manual Check of Pending Logic
                    # stages_config = {"T_PLUS_1H": (1, 6), ...}
                    if 1 <= elapsed < 6:
                        print("   ✅ SHOULD TRIGGER T_PLUS_1H")
                    elif elapsed >= 6:
                        print("   ⚠️ MISSED T_PLUS_1H WINDOW (Elapsed > 6h)")
                    else:
                        print("   ⏳ NOT YET TIME (< 1h)")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    inspect_session("auto-BTC/USDT-1772708608")
