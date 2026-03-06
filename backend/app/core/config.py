from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Trading Platform"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # Security
    SECRET_KEY: str = "CHANGE_THIS_TO_A_SECURE_RANDOM_STRING"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

    # Database
    DATABASE_USER_URL: str
    DATABASE_MARKET_URL: str
    
    # Redis
    REDIS_URL: str
    
    # Vector DB
    CHROMA_URL: str = "http://chromadb:8000" # Default or Optional

    # LLM
    OPENAI_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    
    # External APIs
    CRYPTOPANIC_API_KEY: str = ""
    NEWS_API_KEY: str = ""
    NEWSAPI_QUERY: str = ""
    NEWSAPI_DOMAINS: str = ""
    
    # Trading
    TRADING_MODE: str = "PAPER" # PAPER, LIVE

    # External Services
    AI_ENGINE_URL: str = "http://ai-engine:8000"

    # Risk Management
    RISK_TRAILING_STOP_PCT: float = 0.02
    RISK_AI_TRIGGER_PCT: float = -0.005

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings()
