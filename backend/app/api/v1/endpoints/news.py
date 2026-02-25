from fastapi import APIRouter

router = APIRouter()

@router.get("/latest")
async def get_latest_news(limit: int = 20):
    # TODO: Fetch from ChromaDB/Postgres
    return {"news": []}
