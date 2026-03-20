from sqlalchemy import create_engine, text
from shared.core.config import settings

engine = create_engine(settings.DATABASE_USER_URL)
with engine.connect() as conn:
    conn.execute(text("DROP TABLE IF EXISTS onchain_metrics CASCADE"))
    conn.commit()
    print("Dropped onchain_metrics")
