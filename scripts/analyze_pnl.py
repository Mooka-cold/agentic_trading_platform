
import sys
import os
from sqlalchemy import create_engine, text
import json

# Add project root to sys.path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from app.core.config import settings
except ImportError:
    # Fallback if running from scripts/ directly
    from backend.app.core.config import settings

def analyze_pnl(limit=20):
    try:
        db_url = settings.DATABASE_USER_URL
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # Query closed trades (orders with PnL)
            query = text("""
                SELECT 
                    o.id, 
                    o.symbol, 
                    o.side, 
                    o.type, 
                    o.intent, 
                    o.price, 
                    o.quantity, 
                    o.pnl, 
                    o.session_id, 
                    o.created_at
                FROM paper_orders o
                WHERE o.pnl IS NOT NULL
                ORDER BY o.created_at DESC
                LIMIT :limit
            """)
            
            result = conn.execute(query, {"limit": limit}).fetchall()
            
            if not result:
                print("No closed trades with PnL found.")
                return

            print("\nRecent Closed Trades (PnL Analysis):")
            print(f"{'Symbol':<10} {'Intent':<15} {'Price':<10} {'Qty':<10} {'PnL':<10} {'Session ID':<30} {'Time'}")
            print("-" * 100)
            
            losing_sessions = []
            
            for row in result:
                symbol = row[1]
                intent = row[4]
                price = row[5]
                quantity = row[6]
                pnl = float(row[7])
                session_id = row[8]
                time_str = row[9].strftime("%Y-%m-%d %H:%M")
                
                print(f"{symbol:<10} {intent:<15} {price:<10.2f} {quantity:<10.4f} {pnl:<10.2f} {session_id:<30} {time_str}")
                
                if pnl < 0:
                    losing_sessions.append({
                        "session_id": session_id,
                        "symbol": symbol,
                        "pnl": pnl,
                        "intent": intent
                    })

            # Deep Dive into Losing Sessions
            if losing_sessions:
                print("\n🔍 Analyzing Losing Trades...")
                for item in losing_sessions:
                    session_id = item['session_id']
                    print(f"\n{'='*50}")
                    print(f"[Session: {session_id}] Loss: {item['pnl']:.2f} USDT")
                    
                    if "guardian" in session_id:
                        print("  ⚠️ Triggered by Guardian (Stop Loss / Take Profit)")
                        # Find the opening session
                        find_opening_session(conn, item['symbol'], item['intent'])
                    else:
                        analyze_session_logs(conn, session_id)

    except Exception as e:
        print(f"Error: {e}")

def find_opening_session(conn, symbol, close_intent):
    # Try to find the closed position
    # If intent is CLOSE_LONG, we look for side=LONG
    side = 'LONG' if 'CLOSE_LONG' in close_intent else 'SHORT'
    
    query = text("""
        SELECT session_id, entry_price, size, opened_at, closed_at 
        FROM paper_positions 
        WHERE symbol = :symbol 
        AND side = :side 
        AND status = 'CLOSED'
        ORDER BY closed_at DESC 
        LIMIT 1
    """)
    
    row = conn.execute(query, {"symbol": symbol, "side": side}).fetchone()
    if row:
        print(f"  ➡️ Original Opening Session: {row[0]}")
        print(f"     Opened: {row[3]} | Entry: {row[1]} | Size: {row[2]}")
        analyze_session_logs(conn, row[0])
    else:
        print("  (Could not find original opening position)")

def analyze_session_logs(conn, session_id):
    # Query logs for this session to find the reasoning
    query = text("""
        SELECT agent_id, log_type, content, created_at
        FROM agent_logs 
        WHERE session_id = :session_id 
        ORDER BY created_at ASC
    """)
    
    logs = conn.execute(query, {"session_id": session_id}).fetchall()
    
    if not logs:
        print("  (No logs found for this session)")
        return

    print("  📝 Session Logs:")
    for log in logs:
        agent = log[0]
        log_type = log[1]
        content = log[2]
        
        # Skip system heartbeat/irrelevant logs if needed
        if log_type == 'system': continue

        # Try to parse JSON content if possible
        try:
            if isinstance(content, str) and content.strip().startswith('{'):
                 data = json.loads(content)
                 if agent == 'strategist' and log_type == 'output':
                     action = data.get('action', 'UNKNOWN')
                     reason = data.get('reasoning', 'No reasoning')
                     print(f"    - [{agent.upper()}] Action: {action}")
                     print(f"      Reason: {reason[:300]}...")
                 elif agent == 'reviewer' and log_type == 'output':
                     score = data.get('score', 'N/A')
                     status = data.get('status', 'UNKNOWN')
                     checks = data.get('checks', {})
                     print(f"    - [{agent.upper()}] Status: {status} (Score: {score})")
                     print(f"      Checks: {json.dumps(checks)}")
                 elif agent == 'reflector':
                     print(f"    - [{agent.upper()}] {content[:300]}...")
                 else:
                     # Print thought or other structured data
                     if log_type == 'thought':
                         print(f"    - [{agent.upper()}] Thought: {content[:200]}...")
            else:
                # If plain text
                if len(content) > 200:
                     content = content[:200] + "..."
                print(f"    - [{agent.upper()}] {content}")
        except:
            print(f"    - [{agent.upper()}] {content[:100]}...")

if __name__ == "__main__":
    analyze_pnl(20)
