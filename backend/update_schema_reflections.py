from sqlalchemy import create_engine, text
from app.core.config import settings

def update_schema():
    engine = create_engine(settings.DATABASE_USER_URL)
    with engine.connect() as conn:
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS trade_reflections (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    order_id UUID NOT NULL REFERENCES paper_orders(id),
                    stage VARCHAR(20) NOT NULL,
                    market_context TEXT,
                    price_change_pct NUMERIC(10, 4),
                    score NUMERIC(5, 2),
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            print("Created trade_reflections table")
        except Exception as e:
            print(f"Error creating table: {e}")
            
        conn.commit()

if __name__ == "__main__":
    update_schema()