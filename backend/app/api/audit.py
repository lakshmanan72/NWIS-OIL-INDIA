from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from ..security.auth import get_current_user, require_role, ROLE_ADMIN, ROLE_DRILLING_ENGINEER, UserResponse
from ..repositories.factory import get_audit_repository

router = APIRouter(prefix="/api/audit", tags=["Security Audit Trail"])


@router.get("", response_model=Dict[str, Any])
def get_audit_trail(
    well_id: Optional[str] = Query(None, description="Filter audit logs by Well ID"),
    limit: int = Query(100, ge=1, le=500),
    current_user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER))
):
    repo = get_audit_repository()
    logs = repo.list_audit_logs(well_id=well_id, limit=limit)
    return {
        "status": "success",
        "count": len(logs),
        "requested_by": current_user.username,
        "logs": logs,
    }
