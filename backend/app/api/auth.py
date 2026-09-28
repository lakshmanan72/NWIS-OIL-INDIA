from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from ..security.auth import (
    DEFAULT_USERS,
    verify_password,
    create_access_token,
    get_current_user,
    require_role,
    ROLE_ADMIN,
    UserResponse,
    get_permissions_for_role,
)
from ..security.audit import log_audit_event

router = APIRouter(prefix="/api/auth", tags=["Authentication & RBAC"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request):
    uname = payload.username.strip().lower()
    user_data = DEFAULT_USERS.get(uname)
    client_ip = request.client.host if request.client else None

    if not user_data or not verify_password(payload.password, user_data.get("hashed_password", "")):
        log_audit_event(
            username=payload.username.strip() or "anonymous",
            role="UNKNOWN",
            action="LOGIN_FAILED",
            resource_type="AUTH",
            reason="Invalid username or password",
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user_data.get("is_active", True):
        log_audit_event(
            username=user_data["username"],
            role=user_data["role"],
            action="LOGIN_BLOCKED",
            resource_type="AUTH",
            reason="Account deactivated",
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    # Issue token with role claim
    token = create_access_token(
        data={
            "sub": user_data["username"],
            "role": user_data["role"],
            "user_id": user_data["username"],
        }
    )

    log_audit_event(
        username=user_data["username"],
        role=user_data["role"],
        action="LOGIN_SUCCESS",
        resource_type="AUTH",
        reason="User authenticated successfully",
        ip_address=client_ip,
    )

    user_resp = UserResponse(
        username=user_data["username"],
        email=user_data["email"],
        full_name=user_data.get("full_name"),
        role=user_data["role"],
        is_active=True,
        permissions=get_permissions_for_role(user_data["role"]),
    )

    return LoginResponse(access_token=token, token_type="bearer", user=user_resp)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: UserResponse = Depends(get_current_user)):
    return current_user


@router.get("/users", response_model=List[UserResponse])
def list_system_users(admin_user: UserResponse = Depends(require_role(ROLE_ADMIN))):
    return [
        UserResponse(
            username=u["username"],
            email=u["email"],
            full_name=u.get("full_name"),
            role=u["role"],
            is_active=u.get("is_active", True),
            permissions=get_permissions_for_role(u["role"]),
        )
        for u in DEFAULT_USERS.values()
    ]
