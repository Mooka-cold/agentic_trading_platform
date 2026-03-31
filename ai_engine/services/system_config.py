import json
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text

from core.config import settings


class SystemConfigService:
    def __init__(self):
        self.engine = create_engine(settings.DATABASE_USER_URL)

    def get_value(self, key: str) -> Optional[str]:
        query = text("SELECT value FROM system_configs WHERE key = :key LIMIT 1")
        try:
            with self.engine.connect() as conn:
                row = conn.execute(query, {"key": key}).first()
            if not row:
                return None
            return row[0]
        except Exception:
            return None

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        raw = self.get_value(key)
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            return None
        except Exception:
            return None


system_config_service = SystemConfigService()
