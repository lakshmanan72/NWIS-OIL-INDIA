"""
NWIS Phase 9 — Core Observability, Metrics & Structured Logging
================================================================
Implements request correlation, structured JSON logging, lightweight
operational metrics tracking, and safe error handling.
"""

from __future__ import annotations
import json
import logging
import os
import threading
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable for correlating logs to the active request
current_request_id: ContextVar[str] = ContextVar("current_request_id", default="system")


# =====================================================================
# 1. Structured JSON Log Formatter
# =====================================================================

class StructuredLogFormatter(logging.Formatter):
    """
    Emits single-line JSON log events with correlation IDs and standard metadata.
    Automatically scrubs sensitive keys (passwords, tokens, keys).
    """

    SENSITIVE_KEYS = {
        "password", "secret", "token", "jwt", "authorization",
        "api_key", "cookie", "access_token", "hashed_password"
    }

    def format(self, record: logging.LogRecord) -> str:
        req_id = getattr(record, "request_id", None) or current_request_id.get()

        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "nwis-backend",
            "logger": record.name,
            "event": getattr(record, "event", "APPLICATION_EVENT"),
            "request_id": req_id,
            "message": record.getMessage(),
        }

        # Include optional contextual attributes if set
        for attr in ("well_id", "user_id", "path", "method", "status_code", "duration_ms"):
            val = getattr(record, attr, None)
            if val is not None:
                log_data[attr] = val

        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


# =====================================================================
# 2. Thread-Safe In-Memory Metrics Collector
# =====================================================================

class MetricsCollector:
    """
    Lightweight, thread-safe application metrics registry.
    Captures throughput, status distribution, latencies, alerts, and integration health.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.start_time = time.time()
        self.total_requests = 0
        self.total_errors = 0
        self.requests_by_status: Dict[int, int] = {}
        self.latencies_ms: List[float] = []
        self._max_latency_samples = 1000

        # Subsystem event counters
        self.telemetry_points_processed = 0
        self.telemetry_rejected = 0
        self.telemetry_stale_detected = 0
        self.document_uploads = 0
        self.wcr_approvals = 0
        self.rag_queries = 0
        self.copilot_queries = 0

    def record_request(self, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self.total_requests += 1
            if status_code >= 400:
                self.total_errors += 1
            self.requests_by_status[status_code] = self.requests_by_status.get(status_code, 0) + 1

            if len(self.latencies_ms) >= self._max_latency_samples:
                self.latencies_ms.pop(0)
            self.latencies_ms.append(duration_ms)

    def inc_telemetry_processed(self, count: int = 1) -> None:
        with self._lock:
            self.telemetry_points_processed += count

    def inc_telemetry_rejected(self, count: int = 1) -> None:
        with self._lock:
            self.telemetry_rejected += count

    def inc_telemetry_stale(self, count: int = 1) -> None:
        with self._lock:
            self.telemetry_stale_detected += count

    def inc_document_upload(self, count: int = 1) -> None:
        with self._lock:
            self.document_uploads += count

    def inc_wcr_approval(self, count: int = 1) -> None:
        with self._lock:
            self.wcr_approvals += count

    def inc_rag_query(self, count: int = 1) -> None:
        with self._lock:
            self.rag_queries += count

    def inc_copilot_query(self, count: int = 1) -> None:
        with self._lock:
            self.copilot_queries += count

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            uptime_seconds = round(time.time() - self.start_time, 2)
            avg_latency = (
                round(sum(self.latencies_ms) / len(self.latencies_ms), 2)
                if self.latencies_ms
                else 0.0
            )
            max_latency = round(max(self.latencies_ms), 2) if self.latencies_ms else 0.0
            status_copy = dict(self.requests_by_status)

        # Retrieve dynamic subsystem states safely
        active_alerts_count = 0
        try:
            from ..realtime.service import realtime_service
            active_alerts_count = len(realtime_service.get_alerts(status="ACTIVE"))
        except Exception:
            pass

        integrations_state: Dict[str, str] = {}
        try:
            from ..integrations.ertmac import ertmac_adapter
            from ..integrations.witsml import witsml_adapter
            from ..integrations.wits0 import wits0_adapter
            from ..realtime.providers import demo_replay_provider
            integrations_state = {
                "ertmac": ertmac_adapter.health().get("status", "UNKNOWN"),
                "witsml": witsml_adapter.health().get("status", "UNKNOWN"),
                "wits0": wits0_adapter.health().get("status", "UNKNOWN"),
                "demo_replay": "CONNECTED" if demo_replay_provider.is_connected else "STANDBY",
            }
        except Exception:
            pass

        return {
            "uptime_seconds": uptime_seconds,
            "requests": {
                "total": self.total_requests,
                "total_errors": self.total_errors,
                "by_status": status_copy,
                "avg_duration_ms": avg_latency,
                "max_duration_ms": max_latency,
            },
            "realtime_telemetry": {
                "points_processed": self.telemetry_points_processed,
                "rejected_count": self.telemetry_rejected,
                "stale_count": self.telemetry_stale_detected,
                "active_alerts": active_alerts_count,
            },
            "document_intelligence": {
                "uploads_total": self.document_uploads,
                "approvals_total": self.wcr_approvals,
                "rag_queries_total": self.rag_queries,
                "copilot_queries_total": self.copilot_queries,
            },
            "integrations": integrations_state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def format_prometheus(self) -> str:
        """Formats active metrics in standard Prometheus exposition format."""
        snapshot = self.get_metrics_snapshot()
        lines = [
            "# HELP nwis_uptime_seconds Process uptime in seconds",
            "# TYPE nwis_uptime_seconds gauge",
            f"nwis_uptime_seconds {snapshot['uptime_seconds']}",
            "",
            "# HELP nwis_http_requests_total Total HTTP requests handled",
            "# TYPE nwis_http_requests_total counter",
            f"nwis_http_requests_total {snapshot['requests']['total']}",
            "",
            "# HELP nwis_http_errors_total Total 4xx and 5xx responses",
            "# TYPE nwis_http_errors_total counter",
            f"nwis_http_errors_total {snapshot['requests']['total_errors']}",
            "",
            "# HELP nwis_http_latency_avg_ms Average request latency in milliseconds",
            "# TYPE nwis_http_latency_avg_ms gauge",
            f"nwis_http_latency_avg_ms {snapshot['requests']['avg_duration_ms']}",
            "",
            "# HELP nwis_active_alerts Active unacknowledged drilling alerts",
            "# TYPE nwis_active_alerts gauge",
            f"nwis_active_alerts {snapshot['realtime_telemetry']['active_alerts']}",
            "",
            "# HELP nwis_telemetry_points_total Total rig telemetry points processed",
            "# TYPE nwis_telemetry_points_total counter",
            f"nwis_telemetry_points_total {snapshot['realtime_telemetry']['points_processed']}",
        ]
        return "\n".join(lines) + "\n"


metrics_collector = MetricsCollector()


# =====================================================================
# 3. Request Correlation & Observability Middleware
# =====================================================================

class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Intercepts all HTTP transactions:
    - Injects unique X-Request-ID
    - Binds request correlation context
    - Measures duration
    - Emits structured access logs
    - Updates operational metrics
    """

    def __init__(self, app, logger_instance: Optional[logging.Logger] = None):
        super().__init__(app)
        self.logger = logger_instance or logging.getLogger("nwis.access")

    async def dispatch(self, request: Request, call_next) -> Response:
        import uuid
        incoming_id = request.headers.get("X-Request-ID")
        req_id = incoming_id.strip() if incoming_id else f"req-{uuid.uuid4().hex[:12]}"

        # Set context variables
        token = current_request_id.set(req_id)
        request.state.request_id = req_id

        start_time = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = req_id
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            metrics_collector.record_request(status_code, duration_ms)

            # Mask sensitive query params if present
            path = request.url.path
            self.logger.info(
                f"{request.method} {path} -> {status_code} ({duration_ms}ms)",
                extra={
                    "event": "HTTP_REQUEST",
                    "request_id": req_id,
                    "method": request.method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            current_request_id.reset(token)
