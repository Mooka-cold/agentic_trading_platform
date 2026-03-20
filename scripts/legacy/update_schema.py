from sqlalchemy import create_engine, text
from app.core.config import settings

def add_columns():
    engine = create_engine(settings.DATABASE_USER_URL)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE paper_orders ADD COLUMN session_id VARCHAR(50)"))
            print("Added session_id to paper_orders")
        except Exception as e:
            print(f"paper_orders error (maybe exists): {e}")

        try:
            conn.execute(text("ALTER TABLE paper_positions ADD COLUMN session_id VARCHAR(50)"))
            print("Added session_id to paper_positions")
        except Exception as e:
            print(f"paper_positions error (maybe exists): {e}")
            
        conn.commit()

if __name__ == "__main__":
    add_columns()
