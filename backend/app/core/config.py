from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AI Trading Platform"
    
    # Database
    TIMESCALE_URI: str = "postgresql://user:pass@timescaledb:5432/trading"
    
    # AI Engine
    AI_ENGINE_URL: str = "http://ai-engine:8000"
    
    # Trading Bot
    TRADING_BOT_URL: str = "http://trading-bot:8080"

    class Config:
        case_sensitive = True

settings = Settings()
