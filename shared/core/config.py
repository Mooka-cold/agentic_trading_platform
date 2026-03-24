from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os

# Try to find .env file intelligently
def find_env_file():
    candidates = [
        Path(".env"),
        Path("../.env"),
        Path("../../.env"),
        Path("/app/.env"), # Docker default
        Path(os.getcwd()) / ".env"
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return ".env" # Default fallback

# Define Paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Trading Platform (Shared)"
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
    CHROMA_URL: str = "http://chromadb:8000"
    CHROMA_PERSIST_DIRECTORY: str = str(DATA_DIR / "chroma_db")

    # LLM
    LLM_PROVIDER: str = "qwen"
    LLM_MODEL: str = "qwen-plus"
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DEEPSEEK_API_KEY: str = ""
    
    # External APIs
    CRYPTOPANIC_API_KEY: str = ""
    NEWS_API_KEY: str = ""
    NEWSAPI_QUERY: str = "bitcoin OR crypto OR ethereum"
    NEWSAPI_DOMAINS: str = "coindesk.com,cointelegraph.com,bloomberg.com,reuters.com,cnbc.com"
    
    # Trading
    TRADING_MODE: str = "PAPER" # PAPER, LIVE
    LIVE_TRADING_ENABLED: bool = False

    # Service URLs (Internal Communication)
    BACKEND_URL: str = "http://backend:8000"
    AI_ENGINE_URL: str = "http://ai-engine:8000"
    CRAWLER_URL: str = "http://crawler:8000"

    # Risk Management
    RISK_TRAILING_STOP_PCT: float = 0.02
    RISK_AI_TRIGGER_PCT: float = -0.005

    # Workflow Config
    WORKFLOW_LOOP_INTERVAL: int = 540 # 9 minutes
    LLM_TIMEOUT_SECONDS: int = 60
    REVIEW_INTERVALS: list[int] = [1, 6, 24]
    CALIBRATION_SYMBOL: str = "ETH/USDT"
    CALIBRATION_WINDOW_DAYS: int = 14

    model_config = SettingsConfigDict(env_file=find_env_file(), case_sensitive=True, extra="ignore")

settings = Settings()
