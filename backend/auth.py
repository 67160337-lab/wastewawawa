import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import HTTPException
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .models import User

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str):
    return pwd_context.hash(password[:72])


def verify_password(password: str, hashed: str):
    return pwd_context.verify(password[:72], hashed)


# ---------------------------------------------------------------------------
# Signed session tokens (HMAC-SHA256, standard library only).
#
# Before: the "token" was just the username, so anyone could send
# "Authorization: Bearer <admin's username>" and become that user.
# Now the token carries the user id + expiry and is signed with SECRET_KEY,
# so it can't be forged or edited by the client.
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    print(
        "WARNING: SECRET_KEY is not set. Using a random key, so every login "
        "is invalidated on restart. Set SECRET_KEY in your environment."
    )

TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_HOURS", "168")) * 3600  # 7 days


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str) -> str:
    return _b64(hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).digest())


def create_token(user_id: int) -> str:
    body = json.dumps(
        {"uid": user_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS},
        separators=(",", ":"),
    ).encode()
    payload = _b64(body)
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str):
    """Return the user id if the token is valid and not expired, else None."""
    try:
        payload, signature = token.split(".")
        if not hmac.compare_digest(signature, _sign(payload)):
            return None
        data = json.loads(_unb64(payload))
        if data["exp"] < time.time():
            return None
        return int(data["uid"])
    except Exception:
        return None


def user_from_token(authorization: str, db: Session):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please login")

    user_id = verify_token(authorization.replace("Bearer ", "", 1))
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    # Self-heals the ADMIN_USERNAME grant on every authenticated request
    # (Render's free plan wipes the SQLite file on each deploy).
    admin_username = os.getenv("ADMIN_USERNAME")
    if admin_username and user.username == admin_username and not user.is_admin:
        user.is_admin = True
        db.commit()
        db.refresh(user)

    return user


def admin_from_token(authorization: str, db: Session):
    user = user_from_token(authorization, db)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
