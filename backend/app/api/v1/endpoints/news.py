from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_user_db
from app.services.news_service import news_service

router = APIRouter()

@router.post("/fetch")
async def fetch_news(symbol: str = "BTC", background_tasks: BackgroundTasks = None, db: Session = Depends(get_user_db)):
    """
    Trigger news fetch from external API.
    """
    count = await news_service.fetch_and_store_news(db, symbol)
    return {"status": "success", "added_count": count}

@router.get("")
def get_news(limit: int = 10, db: Session = Depends(get_user_db)):
    """
    Get latest news from DB.
    """
    from shared.models.news import News
    news = db.query(News).order_by(News.published_at.desc()).limit(limit).all()
    return news
