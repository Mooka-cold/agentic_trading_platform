from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from app.db.session import get_user_db
from shared.models.user import User
from pydantic import BaseModel
import secrets
from eth_account import Account
from eth_account.messages import encode_defunct
import jwt
from datetime import datetime, timedelta
from app.core.config import settings

router = APIRouter()

class WalletLoginRequest(BaseModel):
    address: str
    message: str # SIWE Message
    signature: str

class Token(BaseModel):
    access_token: str
    token_type: str

SECRET_KEY = settings.SECRET_KEY if hasattr(settings, "SECRET_KEY") else "dev_secret_key"
ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=1440) # 24h
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.get("/nonce")
def get_nonce(
    address: str = Query(..., description="Wallet Address"),
    db: Session = Depends(get_user_db)
) -> Any:
    """
    Generate a random nonce for SIWE login.
    """
    address = address.lower()
    user = db.query(User).filter(User.wallet_address == address).first()
    
    # Generate secure random nonce
    nonce = secrets.token_hex(16)
    
    if not user:
        # Create user if not exists (lazy creation)
        # Or we can just return nonce and create user on login
        # Let's create user placeholder now
        user = User(wallet_address=address, nonce=nonce)
        db.add(user)
    else:
        user.nonce = nonce
    
    db.commit()
    return {"nonce": nonce}

@router.post("/login", response_model=Token)
def login_with_wallet(
    req: WalletLoginRequest,
    db: Session = Depends(get_user_db)
) -> Any:
    """
    Verify SIWE signature and return JWT.
    """
    address = req.address.lower()
    user = db.query(User).filter(User.wallet_address == address).first()
    
    if not user or not user.nonce:
        raise HTTPException(status_code=400, detail="Invalid address or nonce not generated")
    
    try:
        # Verify Signature
        # 1. Check if nonce is in the message
        if user.nonce not in req.message:
            raise HTTPException(status_code=400, detail="Nonce mismatch in message")
        
        # 2. Recover address from signature
        message_hash = encode_defunct(text=req.message)
        recovered_address = Account.recover_message(message_hash, signature=req.signature)
        
        if recovered_address.lower() != address:
            raise HTTPException(status_code=401, detail="Invalid signature")
            
        # 3. Success -> Generate Token
        # Refresh nonce to prevent replay
        user.nonce = secrets.token_hex(16)
        db.commit()
        
        access_token = create_access_token(data={"sub": str(user.id), "wallet": address})
        return {"access_token": access_token, "token_type": "bearer"}
        
    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")
