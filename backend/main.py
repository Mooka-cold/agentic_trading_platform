from fastapi import FastAPI
from app.api.v1 import router as api_router
from app.core.config import settings

def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        description="AI Trading Platform Backend API",
        version="0.1.0",
    )

    application.include_router(api_router, prefix=settings.API_V1_STR)
    
    return application

app = create_application()

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "backend"}
