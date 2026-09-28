from datetime import datetime
from typing import Protocol, List, Optional, Dict, Any, Tuple
from ..models.well import CanonicalWell, WellMarker, NearbyWellItem


class IWellRepository(Protocol):
    def get_all_wells(
        self,
        offset: int = 0,
        limit: int = 100,
        basin: Optional[str] = None,
        operator: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[int, List[CanonicalWell]]: ...

    def get_well(self, well_id: str) -> Optional[CanonicalWell]: ...
    def search_wells(self, query: str, limit: int = 50) -> List[CanonicalWell]: ...
    def get_well_location(self, well_id: str) -> Optional[Tuple[float, float]]: ...
    def create_canonical_well(self, well_data: Dict[str, Any], reviewer: str = "Engineer") -> CanonicalWell: ...
    def get_all_markers(self, force_reload: bool = False, include_new_wells: bool = True) -> List[WellMarker]: ...
    def get_total_count(self) -> int: ...


class ISpatialRepository(Protocol):
    def get_nearby_wells(self, well_id: str, radius_km: float = 25.0, limit: int = 50) -> List[NearbyWellItem]: ...
    def get_nearest_wells(self, well_id: str, k: int = 10) -> List[NearbyWellItem]: ...


class IGeologyRepository(Protocol):
    def get_geology(self, well_id: str) -> List[Dict[str, Any]]: ...


class IFormationRepository(Protocol):
    def get_formations(self, well_id: str) -> List[Dict[str, Any]]: ...
    def get_formation_at_depth(self, well_id: str, depth_md: float) -> Optional[Dict[str, Any]]: ...


class IDrillingRepository(Protocol):
    def get_drilling_parameters(self, well_id: str, limit: int = 50) -> List[Dict[str, Any]]: ...


class IMudLoggingRepository(Protocol):
    def get_mud_logging(
        self,
        well_id: str,
        depth_from: Optional[float] = None,
        depth_to: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]: ...


class IEventRepository(Protocol):
    def get_historical_events(self, well_id: str, event_type: Optional[str] = None) -> List[Dict[str, Any]]: ...


class ICompletionRepository(Protocol):
    def get_completion_wcr(self, well_id: str) -> Optional[Dict[str, Any]]: ...


class IDocumentRepository(Protocol):
    def list_documents(self, status: Optional[str] = None, well_id: Optional[str] = None) -> List[Any]: ...
    def get_document(self, doc_id: str) -> Optional[Any]: ...
    def create_document(self, doc_data: Dict[str, Any]) -> Any: ...
    def update_approval_status(self, doc_id: str, status: str, approved_by: Optional[str] = None) -> Any: ...


class IRiskRepository(Protocol):
    def get_risk_recommendations(self, well_id: str) -> List[Dict[str, Any]]: ...


class ITelemetryRepository(Protocol):
    def record_telemetry(self, record: Dict[str, Any]) -> None: ...
    def get_latest_telemetry(self, well_id: str) -> Optional[Dict[str, Any]]: ...
    def get_telemetry_range(
        self,
        well_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        depth_from: Optional[float] = None,
        depth_to: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]: ...


class IAlertRepository(Protocol):
    def create_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]: ...
    def get_alert(self, alert_id: str) -> Optional[Dict[str, Any]]: ...
    def get_active_alerts(self, well_id: Optional[str] = None, severity: Optional[str] = None) -> List[Dict[str, Any]]: ...
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str, note: str = "") -> Optional[Dict[str, Any]]: ...
    def close_alert(self, alert_id: str, closed_by: str, note: str = "") -> Optional[Dict[str, Any]]: ...


class IAuditRepository(Protocol):
    def record_audit(
        self,
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
    ) -> None: ...
    def list_audit_logs(self, well_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]: ...
