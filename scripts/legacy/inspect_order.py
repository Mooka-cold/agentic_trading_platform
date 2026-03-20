import os
import sys
from sqlalchemy import text, select
import datetime

# Add backend directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from app.db.session import SessionLocalUser
from app.services.paper_trading import PaperOrder, SessionReflection, PaperPosition

db = SessionLocalUser()

# List recent orders
orders = db.query(PaperOrder).order_by(PaperOrder.created_at.desc()).limit(5).all()
print("Recent Orders:")
for o in orders:
    print(f"ID: {o.id}, Symbol: {o.symbol}, Side: {o.side}, Status: {o.status}, Session: {o.session_id}")

# List recent reflections
reflections = db.query(SessionReflection).order_by(SessionReflection.created_at.desc()).limit(5).all()
print("\nRecent Reflections:")
for r in reflections:
    print(f"ID: {r.id}, Session: {r.session_id}, Stage: {r.stage}, Score: {r.score}")
