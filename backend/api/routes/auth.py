"""Auth router — JWT login with direct asyncpg (avoids SQLAlchemy session issues)."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncpg
import jwt

router = APIRouter(tags=["auth"])

DSN = os.getenv("DATABASE_URL", "postgresql+asyncpg://realtoros:realtoros15!@127.0.0.1:5432/realtoros")
DSN = DSN.replace("+asyncpg", "")


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(body: LoginRequest):
    pw_hash = hashlib.sha256(body.password.encode()).hexdigest()
    conn = await asyncpg.connect(DSN)
    try:
        row = await conn.fetchrow(
            "SELECT id, email, full_name, phone, role_id FROM users WHERE email=$1 AND password_hash=$2 AND deleted_at IS NULL",
            body.email, pw_hash
        )
        if not row:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        payload = {
            "sub": str(row["id"]),
            "email": row["email"],
            "role": str(row["role_id"]),
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        }
        secret = os.getenv("SECRET_KEY", "dev-secret-key-not-for-production")
        token = jwt.encode(payload, secret, algorithm="HS256")
        return {
            "token": token,
            "user": {
                "id": str(row["id"]),
                "email": row["email"],
                "full_name": row["full_name"],
                "phone": row["phone"],
                "role": str(row["role_id"]),
                "avatar": None,
            },
            "expires_at": payload["exp"].isoformat(),
        }
    finally:
        await conn.close()
