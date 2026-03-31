from fastapi import FastAPI
from app.api.endpoints import router
from shared.core.config import settings
import uvicorn
import os

app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(router, prefix="/api/v1")

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
