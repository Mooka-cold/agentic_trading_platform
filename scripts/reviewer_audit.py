
import sys
import os
import json
from sqlalchemy import create_engine, text

# Add paths to sys.path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from backend.app.core.config import settings
except ImportError:
    try:
        from app.core.config import settings
    except ImportError:
        # Fallback for direct execution
        class Settings:
            DATABASE_USER_URL = "postgresql://postgres:postgres@localhost:5432/user_db" # Guessing default from docker-compose
        settings = Settings()

def audit_reviewer(limit=10):
    # Hardcoded fallback for host execution
    db_url = "postgresql://user_admin:user_password@localhost:3205/ai_trading_users"
        
    engine = create_engine(db_url)
    
    query = text("""
        SELECT 
            s.id, s.symbol, s.action, s.start_time,
            l_rev.artifact as reviewer_artifact,
            l_strat.artifact as strategist_artifact,
            l_ana.artifact as analyst_artifact
        FROM workflow_sessions s
        LEFT JOIN agent_logs l_rev ON s.id = l_rev.session_id AND l_rev.agent_id = 'reviewer' AND l_rev.log_type = 'output'
        LEFT JOIN agent_logs l_strat ON s.id = l_strat.session_id AND l_strat.agent_id = 'strategist' AND l_strat.log_type = 'output'
        LEFT JOIN agent_logs l_ana ON s.id = l_ana.session_id AND l_ana.agent_id = 'analyst' AND l_ana.log_type = 'output'
        WHERE s.review_status = 'APPROVED'
        AND s.action NOT IN ('HOLD', 'SKIP')
        ORDER BY s.start_time DESC
        LIMIT :limit
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"limit": limit}).fetchall()
        
        print(f"Found {len(result)} approved transactions.")
        
        for row in result:
            sid, symbol, action, time, rev_art, strat_art, ana_art = row
            
            print(f"\n{'='*50}")
            print(f"SESSION: {sid}")
            print(f"TIME: {time}")
            print(f"SYMBOL: {symbol} | ACTION: {action}")
            
            # Reviewer Info
            print(f"\n[REVIEWER VERDICT]")
            if rev_art:
                print(f"Score: {rev_art.get('score')}")
                print(f"Checks: {json.dumps(rev_art.get('checks', {}), indent=2)}")
                print(f"Reason: {rev_art.get('reason')}")
            else:
                print("No Reviewer Artifact found.")

            # Strategist Info
            print(f"\n[STRATEGIST PROPOSAL]")
            if strat_art:
                print(f"Confidence: {strat_art.get('confidence')}")
                print(f"R/R: {strat_art.get('rr')}")
                print(f"Reasoning: {strat_art.get('reasoning')[:200]}...")
            else:
                print("No Strategist Artifact found.")
                
            # Analyst Info
            print(f"\n[ANALYST VIEW]")
            if ana_art:
                print(f"Bias: {ana_art.get('bias')}")
                print(f"Risk: {ana_art.get('risk')}")
            else:
                print("No Analyst Artifact found.")

if __name__ == "__main__":
    audit_reviewer()
