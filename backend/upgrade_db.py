from sqlalchemy import create_engine, text
from app.core.config import settings

def upgrade_db():
    engine = create_engine(settings.DATABASE_USER_URL)
    with engine.connect() as conn:
        try:
            print("Adding columns to workflow_sessions...")
            # Add 'action' column
            conn.execute(text("ALTER TABLE workflow_sessions ADD COLUMN IF NOT EXISTS action VARCHAR;"))
            # Add 'review_status' column
            conn.execute(text("ALTER TABLE workflow_sessions ADD COLUMN IF NOT EXISTS review_status VARCHAR;"))
            
            conn.commit()
            print("Upgrade complete.")
            
        except Exception as e:
            print(f"Error during upgrade: {e}")
            conn.rollback()

if __name__ == "__main__":
    upgrade_db()