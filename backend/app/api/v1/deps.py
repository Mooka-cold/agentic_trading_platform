from typing import Optional
from fastapi import Header
import jwt

from app.core.config import settings


def get_runtime_user_id(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> int:
    if x_user_id is not None:
        try:
            value = int(x_user_id)
            if value > 0:
                return value
        except Exception:
            pass

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token:
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                sub = payload.get("sub")
                if sub is not None:
                    value = int(sub)
                    if value > 0:
                        return value
            except Exception:
                pass

    return 1
