from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SystemConfigBase(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

class SystemConfigCreate(SystemConfigBase):
    pass

class SystemConfigUpdate(SystemConfigBase):
    pass

class SystemConfig(SystemConfigBase):
    updated_at: datetime

    class Config:
        from_attributes = True
