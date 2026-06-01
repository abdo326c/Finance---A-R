from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from pydantic import BaseModel
from jose import JWTError, jwt

from models import get_db, SystemUser
import bcrypt
import os

def hash_pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_pw(plain: str, hashed: str) -> bool:
    try:
        if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
            return bcrypt.checkpw(plain.encode(), hashed.encode())
        else:
            import hashlib
            return hashlib.sha256(plain.encode()).hexdigest() == hashed
    except Exception:
        return False

# Configuration for JWT
SECRET_KEY = os.getenv("JWT_SECRET", "your-very-secret-key-please-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days for testing

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

class Token(BaseModel):
    access_token: str
    token_type: str
    user_role: str
    username: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception
    
    user = db.query(SystemUser).filter(SystemUser.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(SystemUser).filter(
        func.lower(SystemUser.username) == form_data.username.lower().strip(),
        SystemUser.is_active == True
    ).first()
    
    if not user or not verify_pw(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Upgrade password hash if it's legacy
    if not user.password_hash.startswith(("$2b$", "$2a$")):
        user.password_hash = hash_pw(form_data.password)
        db.commit()

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "user_role": user.role, "username": user.username}

@router.get("/me")
async def read_users_me(current_user: SystemUser = Depends(get_current_user)):
    return {"username": current_user.username, "role": current_user.role}

class ChangePasswordRequest(BaseModel):
    username: str
    current_password: str
    new_password: str

@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, db: Session = Depends(get_db)):
    user = db.query(SystemUser).filter(
        func.lower(SystemUser.username) == req.username.lower().strip()
    ).first()
    
    if not user or not verify_pw(req.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect username or current password")
    if len(req.new_password) < 4:
        raise HTTPException(status_code=400, detail="New password too short")
        
    user.password_hash = hash_pw(req.new_password)
    db.commit()
    return {"message": "Password updated successfully"}
