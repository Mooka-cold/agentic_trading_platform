from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# User DB Engine
engine_user = create_engine(settings.DATABASE_USER_URL, pool_pre_ping=True)
SessionLocalUser = sessionmaker(autocommit=False, autoflush=False, bind=engine_user)

# Market DB Engine
engine_market = create_engine(settings.DATABASE_MARKET_URL, pool_pre_ping=True)
SessionLocalMarket = sessionmaker(autocommit=False, autoflush=False, bind=engine_market)

def get_market_engine():
    return engine_market

def get_user_db() -> Session:
    db = SessionLocalUser()
    try:
        yield db
    finally:
        db.close()

def get_market_db() -> Session:
    db = SessionLocalMarket()
    try:
        yield db
    finally:
        db.close()
