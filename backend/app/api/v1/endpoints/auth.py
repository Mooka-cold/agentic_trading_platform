from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from app.db.session import get_user_db
from shared.models.user import User
from pydantic import BaseModel, EmailStr
import secrets
from eth_account import Account
from eth_account.messages import encode_defunct
import jwt
from datetime import datetime, timedelta
from app.core.config import settings
import hashlib

router = APIRouter()

class WalletLoginRequest(BaseModel):
    address: str
    message: str # SIWE Message
    signature: str

class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str

SECRET_KEY = settings.SECRET_KEY if hasattr(settings, "SECRET_KEY") else "dev_secret_key"
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return hashlib.sha256((password + SECRET_KEY).encode()).hexdigest()

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=1440) # 24h
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/register", response_model=Token)
def register(
    req: RegisterRequest,
    db: Session = Depends(get_user_db)
) -> Any:
    user = db.query(User).filter(User.email == req.email).first()
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return {"access_token": access_token, "token_type": "bearer", "user_id": str(user.id)}

@router.post("/login/email", response_model=Token)
def login_with_email(
    req: EmailLoginRequest,
    db: Session = Depends(get_user_db)
) -> Any:
    user = db.query(User).filter(User.email == req.email).first()
    if not user or user.hashed_password != hash_password(req.password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
        
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return {"access_token": access_token, "token_type": "bearer", "user_id": str(user.id)}

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
        if user.nonce not in req.message:
            raise HTTPException(status_code=400, detail="Nonce mismatch in message")
        
        message_hash = encode_defunct(text=req.message)
        recovered_address = Account.recover_message(message_hash, signature=req.signature)
        
        if recovered_address.lower() != address:
            raise HTTPException(status_code=401, detail="Invalid signature")
            
        user.nonce = secrets.token_hex(16)
        db.commit()
        
        access_token = create_access_token(data={"sub": str(user.id), "wallet": address})
        return {"access_token": access_token, "token_type": "bearer", "user_id": str(user.id)}
        
    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")
