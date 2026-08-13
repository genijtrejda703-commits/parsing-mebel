"""Single-password admin auth with JWT (MVP scope by design)."""
import os
import time
import jwt
from fastapi import Header, HTTPException
from dotenv import load_dotenv

load_dotenv("/app/.env")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "homeart2025")
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-secret")
JWT_TTL = 60 * 60 * 24 * 7  # 7 days


def create_token() -> str:
    payload = {"sub": "admin", "iat": int(time.time()), "exp": int(time.time()) + JWT_TTL}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_password(password: str) -> bool:
    return password == ADMIN_PASSWORD


async def require_auth(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return True
