from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import httpx
from app.core.config import settings
from app.db.session import get_user_db
from shared.models.system import SystemConfig
from app.schemas.system import SystemConfigCreate, SystemConfig as SystemConfigSchema

router = APIRouter()

@router.post("/reload")
async def reload_ai_engine():
    """Trigger AI Engine to reload configuration"""
    async with httpx.AsyncClient() as client:
        try:
            workflow_url = f"{settings.AI_ENGINE_URL}/workflow/reload"
            sentiment_url = f"{settings.AI_ENGINE_URL}/sentiment/reload-config"
            workflow_resp = await client.post(workflow_url)
            sentiment_resp = await client.post(sentiment_url)
            if workflow_resp.status_code != 200:
                raise HTTPException(status_code=workflow_resp.status_code, detail="AI Engine workflow reload failed")
            if sentiment_resp.status_code != 200:
                raise HTTPException(status_code=sentiment_resp.status_code, detail="AI Engine sentiment reload failed")
            return {
                "workflow": workflow_resp.json(),
                "sentiment": sentiment_resp.json()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reload AI Engine: {e}")

@router.get("/sentiment/aggregate")
async def get_sentiment_aggregate(symbol: str):
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(f"{settings.AI_ENGINE_URL}/sentiment/aggregate", params={"symbol": symbol})
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch sentiment aggregate: {e}")

@router.get("/sentiment/interpretations")
async def get_sentiment_interpretations(symbol: str, limit: int = 20, scope: str = "symbol"):
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(
                f"{settings.AI_ENGINE_URL}/sentiment/interpretations",
                params={"symbol": symbol, "limit": limit, "scope": scope},
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch sentiment interpretations: {e}")

@router.get("/sentiment/dashboard")
async def get_sentiment_dashboard(symbol: str):
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(f"{settings.AI_ENGINE_URL}/sentiment/dashboard", params={"symbol": symbol})
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch sentiment dashboard: {e}")

@router.get("/config", response_model=List[SystemConfigSchema])
def get_configs(db: Session = Depends(get_user_db)):
    configs = db.query(SystemConfig).all()
    return configs

@router.post("/config", response_model=SystemConfigSchema)
def set_config(config: SystemConfigCreate, db: Session = Depends(get_user_db)):
    db_config = db.query(SystemConfig).filter(SystemConfig.key == config.key).first()
    if db_config:
        db_config.value = config.value
        if config.description is not None:
            db_config.description = config.description
    else:
        db_config = SystemConfig(key=config.key, value=config.value, description=config.description)
        db.add(db_config)
    
    db.commit()
    db.refresh(db_config)
    return db_config

@router.get("/config/{key}", response_model=SystemConfigSchema)
def get_config_by_key(key: str, db: Session = Depends(get_user_db)):
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return config
