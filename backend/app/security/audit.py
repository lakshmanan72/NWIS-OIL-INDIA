import logging
from typing import Optional, Dict, Any
from ..repositories.factory import get_audit_repository

logger = logging.getLogger("nwis.security.audit")


def log_audit_event(
    username: str,
    role: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    well_id: Optional[str] = None,
    depth_md: Optional[float] = None,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> None:
    """
    Appends an immutable audit record to the persistent audit log.
    Never throws exceptions that could disrupt user operations.
    """
    try:
        repo = get_audit_repository()
        repo.record_audit(
            username=username,
            role=role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            well_id=well_id,
            depth_md=depth_md,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            ip_address=ip_address,
            request_id=request_id,
            user_id=user_id,
        )
        logger.info(f"AUDIT: [{username}:{role}] {action} on {resource_type}:{resource_id} (well: {well_id})")
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
