import logging
from typing import Optional
from ..db.config import db_config
from ..db.session import check_database_connection
from .interfaces import (
    IWellRepository,
    ISpatialRepository,
    IGeologyRepository,
    IFormationRepository,
    IDrillingRepository,
    IMudLoggingRepository,
    IEventRepository,
    ICompletionRepository,
    IRiskRepository,
    ITelemetryRepository,
    IAlertRepository,
    IAuditRepository,
)
from .csv_repository import (
    CsvWellRepository,
    CsvSpatialRepository,
    CsvGeologyRepository,
    CsvFormationRepository,
    CsvDrillingRepository,
    CsvMudLoggingRepository,
    CsvEventRepository,
    CsvCompletionRepository,
    CsvRiskRepository,
    CsvTelemetryRepository,
    CsvAlertRepository,
    CsvAuditRepository,
)
from .postgres_repository import (
    PostgresWellRepository,
    PostgresSpatialRepository,
    PostgresGeologyRepository,
    PostgresFormationRepository,
    PostgresDrillingRepository,
    PostgresMudLoggingRepository,
    PostgresEventRepository,
    PostgresCompletionRepository,
    PostgresRiskRepository,
    PostgresTelemetryRepository,
    PostgresAlertRepository,
    PostgresAuditRepository,
)

logger = logging.getLogger("nwis.repo.factory")

# Singletons cache
_well_repo: Optional[IWellRepository] = None
_spatial_repo: Optional[ISpatialRepository] = None
_geology_repo: Optional[IGeologyRepository] = None
_formation_repo: Optional[IFormationRepository] = None
_drilling_repo: Optional[IDrillingRepository] = None
_mud_repo: Optional[IMudLoggingRepository] = None
_event_repo: Optional[IEventRepository] = None
_completion_repo: Optional[ICompletionRepository] = None
_risk_repo: Optional[IRiskRepository] = None
_telemetry_repo: Optional[ITelemetryRepository] = None
_alert_repo: Optional[IAlertRepository] = None
_audit_repo: Optional[IAuditRepository] = None


def is_postgres_available() -> bool:
    if not db_config.is_postgres_mode:
        return False
    health = check_database_connection()
    return bool(health.get("connected"))


def get_well_repository() -> IWellRepository:
    global _well_repo
    if _well_repo is None:
        if is_postgres_available():
            logger.info("Initializing PostgresWellRepository")
            _well_repo = PostgresWellRepository()
        else:
            logger.info("Initializing CsvWellRepository (Default/Fallback)")
            _well_repo = CsvWellRepository()
    return _well_repo


def get_spatial_repository() -> ISpatialRepository:
    global _spatial_repo
    if _spatial_repo is None:
        well_repo = get_well_repository()
        if is_postgres_available():
            logger.info("Initializing PostgresSpatialRepository (PostGIS)")
            _spatial_repo = PostgresSpatialRepository(well_repo=well_repo)
        else:
            logger.info("Initializing CsvSpatialRepository (Precomputed/Haversine)")
            _spatial_repo = CsvSpatialRepository(well_repo=well_repo)
    return _spatial_repo


def get_geology_repository() -> IGeologyRepository:
    global _geology_repo
    if _geology_repo is None:
        if is_postgres_available():
            _geology_repo = PostgresGeologyRepository()
        else:
            _geology_repo = CsvGeologyRepository()
    return _geology_repo


def get_formation_repository() -> IFormationRepository:
    global _formation_repo
    if _formation_repo is None:
        if is_postgres_available():
            _formation_repo = PostgresFormationRepository()
        else:
            _formation_repo = CsvFormationRepository()
    return _formation_repo


def get_drilling_repository() -> IDrillingRepository:
    global _drilling_repo
    if _drilling_repo is None:
        if is_postgres_available():
            _drilling_repo = PostgresDrillingRepository()
        else:
            _drilling_repo = CsvDrillingRepository()
    return _drilling_repo


def get_mud_logging_repository() -> IMudLoggingRepository:
    global _mud_repo
    if _mud_repo is None:
        if is_postgres_available():
            _mud_repo = PostgresMudLoggingRepository()
        else:
            _mud_repo = CsvMudLoggingRepository()
    return _mud_repo


def get_event_repository() -> IEventRepository:
    global _event_repo
    if _event_repo is None:
        if is_postgres_available():
            _event_repo = PostgresEventRepository()
        else:
            _event_repo = CsvEventRepository()
    return _event_repo


def get_completion_repository() -> ICompletionRepository:
    global _completion_repo
    if _completion_repo is None:
        if is_postgres_available():
            _completion_repo = PostgresCompletionRepository()
        else:
            _completion_repo = CsvCompletionRepository()
    return _completion_repo


def get_risk_repository() -> IRiskRepository:
    global _risk_repo
    if _risk_repo is None:
        if is_postgres_available():
            _risk_repo = PostgresRiskRepository()
        else:
            _risk_repo = CsvRiskRepository()
    return _risk_repo


def get_telemetry_repository() -> ITelemetryRepository:
    global _telemetry_repo
    if _telemetry_repo is None:
        if is_postgres_available() and db_config.telemetry_storage == "postgres":
            _telemetry_repo = PostgresTelemetryRepository()
        else:
            _telemetry_repo = CsvTelemetryRepository()
    return _telemetry_repo


def get_alert_repository() -> IAlertRepository:
    global _alert_repo
    if _alert_repo is None:
        if is_postgres_available() and db_config.alert_storage == "postgres":
            _alert_repo = PostgresAlertRepository()
        else:
            _alert_repo = CsvAlertRepository()
    return _alert_repo


def get_audit_repository() -> IAuditRepository:
    global _audit_repo
    if _audit_repo is None:
        if is_postgres_available():
            _audit_repo = PostgresAuditRepository()
        else:
            _audit_repo = CsvAuditRepository()
    return _audit_repo
