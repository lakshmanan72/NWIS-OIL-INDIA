import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Header
from pydantic import BaseModel
from ..db.config import db_config

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# Roles definition
ROLE_ADMIN = "ADMIN"
ROLE_DRILLING_ENGINEER = "DRILLING_ENGINEER"
ROLE_GEOLOGIST = "GEOLOGIST"
ROLE_VIEWER = "VIEWER"

ALL_ROLES = [ROLE_ADMIN, ROLE_DRILLING_ENGINEER, ROLE_GEOLOGIST, ROLE_VIEWER]


class TokenData(BaseModel):
    username: str
    role: str
    user_id: Optional[str] = None


class UserResponse(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool = True
    permissions: List[str]


# Default seeded users for development / demonstration (hashed passwords)
DEFAULT_USERS: Dict[str, Dict[str, Any]] = {
    "admin": {
        "username": "admin",
        "email": "admin@nwis.internal",
        "full_name": "Senior System Administrator",
        "hashed_password": pwd_context.hash("AdminPassword2026!"),
        "role": ROLE_ADMIN,
        "is_active": True,
    },
    "engineer": {
        "username": "engineer",
        "email": "engineer@nwis.internal",
        "full_name": "Senior Drilling Operations Engineer",
        "hashed_password": pwd_context.hash("EngineerPassword2026!"),
        "role": ROLE_DRILLING_ENGINEER,
        "is_active": True,
    },
    "geologist": {
        "username": "geologist",
        "email": "geologist@nwis.internal",
        "full_name": "Lead Subsurface Geologist",
        "hashed_password": pwd_context.hash("GeologistPassword2026!"),
        "role": ROLE_GEOLOGIST,
        "is_active": True,
    },
    "viewer": {
        "username": "viewer",
        "email": "viewer@nwis.internal",
        "full_name": "Field Observer / Viewer",
        "hashed_password": pwd_context.hash("ViewerPassword2026!"),
        "role": ROLE_VIEWER,
        "is_active": True,
    },
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=db_config.jwt_expire_minutes)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, db_config.jwt_secret, algorithm=db_config.jwt_algorithm)


def decode_access_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(token, db_config.jwt_secret, algorithms=[db_config.jwt_algorithm])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        user_id: Optional[str] = payload.get("user_id")
        if username is None or role is None:
            return None
        return TokenData(username=username, role=role, user_id=user_id)
    except Exception:
        return None


def get_permissions_for_role(role: str) -> List[str]:
    role_up = role.upper()
    if role_up == ROLE_ADMIN:
        return [
            "wells:read", "wells:write", "geology:read", "formations:read",
            "drilling:read", "mudlog:read", "events:read", "wcr:read", "wcr:write", "wcr:approve",
            "documents:read", "documents:upload", "documents:review", "documents:approve",
            "telemetry:read", "telemetry:write", "alerts:read", "alerts:ack", "alerts:close",
            "copilot:query", "audit:read", "users:manage", "config:manage"
        ]
    elif role_up == ROLE_DRILLING_ENGINEER:
        return [
            "wells:read", "geology:read", "formations:read", "drilling:read",
            "mudlog:read", "events:read", "wcr:read", "wcr:write", "wcr:approve",
            "documents:read", "documents:upload", "documents:review", "documents:approve",
            "telemetry:read", "telemetry:write", "alerts:read", "alerts:ack", "alerts:close",
            "copilot:query"
        ]
    elif role_up == ROLE_GEOLOGIST:
        return [
            "wells:read", "geology:read", "formations:read", "mudlog:read",
            "events:read", "wcr:read", "documents:read", "documents:upload",
            "copilot:query", "spatial:read"
        ]
    else:  # VIEWER
        return [
            "wells:read", "geology:read", "formations:read", "drilling:read",
            "mudlog:read", "events:read", "wcr:read", "documents:read",
            "telemetry:read", "alerts:read"
        ]


def get_current_user(authorization: Optional[str] = Header(None)) -> UserResponse:
    """
    Validates JWT token from Authorization header.
    If no authorization header is provided, defaults to an engineering context
    for backward compatibility with legacy prototype test suites.
    """
    if not authorization:
        if db_config.is_production:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials required in production mode.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Default development user with DRILLING_ENGINEER permissions
        dev_user = DEFAULT_USERS["engineer"]
        return UserResponse(
            username=dev_user["username"],
            email=dev_user["email"],
            full_name=dev_user["full_name"],
            role=dev_user["role"],
            is_active=True,
            permissions=get_permissions_for_role(dev_user["role"]),
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token format. Use 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    token_data = decode_access_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Lookup user
    user_info = DEFAULT_USERS.get(token_data.username.lower())
    if user_info:
        return UserResponse(
            username=user_info["username"],
            email=user_info["email"],
            full_name=user_info.get("full_name"),
            role=token_data.role,
            is_active=user_info.get("is_active", True),
            permissions=get_permissions_for_role(token_data.role),
        )

    return UserResponse(
        username=token_data.username,
        email=f"{token_data.username}@nwis.internal",
        full_name=token_data.username.capitalize(),
        role=token_data.role,
        is_active=True,
        permissions=get_permissions_for_role(token_data.role),
    )


def require_role(*allowed_roles: str):
    """Dependency enforcing role-based access control."""
    def role_checker(current_user: UserResponse = Depends(get_current_user)):
        user_role = current_user.role.upper()
        allowed = [r.upper() for r in allowed_roles]
        if user_role not in allowed and user_role != ROLE_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Role '{current_user.role}' lacks permission for this operation. Required: {allowed_roles}",
            )
        return current_user
    return role_checker
