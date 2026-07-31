import uuid
from typing import Optional
from fastapi import Header, HTTPException, Depends, Request
import jwt
from sqlalchemy.orm import Session
import uuid

from app.core.config import settings
from app.db.session import get_user_db
from shared.models.user import User

def get_runtime_user_id(
    request: Request,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_user_db)
) -> Optional[uuid.UUID]:
    """
    Get current user ID from JWT token or internal service header.
    Throws 401 if token is invalid or missing.
    """
    # Check internal bypass first
    if request.headers.get("X-Internal-Service") == "ai_engine":
        internal_user_id = request.headers.get("X-User-Id")
        if internal_user_id and internal_user_id != "default":
            try:
                return uuid.UUID(internal_user_id)
            except ValueError:
                pass
        return None
            
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        sub = payload.get("sub")
        if sub is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        user_id = uuid.UUID(sub)
        
        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
            
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(
    user_id: uuid.UUID = Depends(get_runtime_user_id),
    db: Session = Depends(get_user_db)
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
