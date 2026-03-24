from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1 import router as api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine_user
from shared.db.base import Base as UserBase
from shared.core.symbols import get_schedule_symbols_from_env
# Import models to register them
from shared.models import workflow

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("📦 Creating Database Tables...")
    Base.metadata.create_all(bind=engine_user)
    UserBase.metadata.create_all(bind=engine_user)
    
    # Start Price Streamer (WebSocket)
    from app.services.price_streamer import price_streamer

    symbols = get_schedule_symbols_from_env()
    print(f"📡 Starting PriceStreamer for: {symbols}")
    await price_streamer.start(symbols)
    
    yield
    
    # Stop Price Streamer
    await price_streamer.stop()

def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        description="AI Trading Platform Backend API",
        version="0.1.0",
        lifespan=lifespan
    )

    # Set all CORS enabled origins
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, set to specific domains
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router, prefix=settings.API_V1_STR)
    
    return application

app = create_application()

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "backend"}
