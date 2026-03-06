from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Engine"
    
    # LLM
    LLM_PROVIDER: str = "qwen"
    OPENAI_API_KEY: str
    OPENAI_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_MODEL: str = "qwen-plus"
    
    # Database (TimescaleDB)
    DATABASE_MARKET_URL: str
    DATABASE_USER_URL: str # Added for accessing News table

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Backend Service
    BACKEND_URL: str = "http://backend:8000"

    # Review Scheduler (Hours)
    REVIEW_INTERVALS: list[int] = [1, 6, 24] # Configurable intervals for T+X reviews

    # Workflow Config
    WORKFLOW_LOOP_INTERVAL: int = 900 # 15 minutes
    LLM_TIMEOUT_SECONDS: int = 60

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings()
