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
            # Ensure AI_ENGINE_URL is set in backend env
            url = f"{settings.AI_ENGINE_URL}/workflow/reload"
            resp = await client.post(url)
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="AI Engine returned error")
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reload AI Engine: {e}")

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
