import os
import re
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger("nwis.config")

DEFAULT_DEV_JWT_SECRET = "nwis_default_secret_key_change_in_production_2026"
DEFAULT_DEV_DB_URL = "postgresql://nwis_admin:nwis_secure_password_2026@localhost:5432/nwis"


class DatabaseConfig(BaseModel):
    environment: str = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
    data_backend: str = os.getenv("DATA_BACKEND", "csv").lower()
    database_url: Optional[str] = os.getenv("DATABASE_URL", DEFAULT_DEV_DB_URL)
    postgis_enabled: bool = os.getenv("POSTGIS_ENABLED", "true").lower() in ("true", "1", "yes")
    telemetry_storage: str = os.getenv("TELEMETRY_STORAGE", "postgres").lower()
    alert_storage: str = os.getenv("ALERT_STORAGE", "postgres").lower()
    vector_backend: str = os.getenv("VECTOR_BACKEND", "local").lower()
    jwt_secret: str = os.getenv("JWT_SECRET", DEFAULT_DEV_JWT_SECRET)
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    @property
    def is_postgres_mode(self) -> bool:
        return self.data_backend == "postgres"

    @property
    def is_csv_mode(self) -> bool:
        return self.data_backend == "csv"

    @property
    def is_production(self) -> bool:
        return self.environment in ("production", "prod", "staging")

    def validate_production_security(self) -> None:
        """
        Enforces strict cryptographic and connectivity constraints in production environments.
        Fails safely if default development secrets are detected.
        """
        if self.is_production:
            if not self.jwt_secret or self.jwt_secret == DEFAULT_DEV_JWT_SECRET:
                raise RuntimeError(
                    "FATAL SECURITY CONFIGURATION: In production mode, JWT_SECRET must be explicitly set "
                    "to an unguessable cryptographic key (minimum 32 characters). Default dev secret is prohibited."
                )
            if len(self.jwt_secret) < 32:
                raise RuntimeError(
                    "FATAL SECURITY CONFIGURATION: JWT_SECRET must be at least 32 characters in production."
                )
            if self.is_postgres_mode and (not self.database_url or self.database_url == DEFAULT_DEV_DB_URL):
                raise RuntimeError(
                    "FATAL SECURITY CONFIGURATION: In production mode with DATA_BACKEND=postgres, "
                    "DATABASE_URL must be explicitly configured with production credentials."
                )

    def get_safe_summary(self) -> Dict[str, Any]:
        """
        Returns a redacted representation of runtime configuration safe for logs and diagnostics.
        Never exposes raw passwords or token signing keys.
        """
        safe_db_url = None
        if self.database_url:
            # Mask password: postgresql://user:pass@host:port/db -> postgresql://user:*****@host:port/db
            safe_db_url = re.sub(r"://([^:]+):([^@]+)@", r"://\1:*****@", self.database_url)

        return {
            "environment": self.environment,
            "data_backend": self.data_backend,
            "database_url_masked": safe_db_url,
            "postgis_enabled": self.postgis_enabled,
            "telemetry_storage": self.telemetry_storage,
            "alert_storage": self.alert_storage,
            "vector_backend": self.vector_backend,
            "jwt_algorithm": self.jwt_algorithm,
            "jwt_expire_minutes": self.jwt_expire_minutes,
            "jwt_secret_configured": bool(self.jwt_secret and self.jwt_secret != DEFAULT_DEV_JWT_SECRET),
        }


db_config = DatabaseConfig()

# Run non-destructive startup check
try:
    db_config.validate_production_security()
except RuntimeError as err:
    logger.critical(str(err))
    if db_config.is_production:
        raise
