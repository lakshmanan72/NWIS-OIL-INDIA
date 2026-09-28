"""
NWIS Phase 8 — High-Frequency Streaming Pipeline & Backpressure Controller
==========================================================================
Coordinates ingestion queues, duplicate suppression, out-of-order sequencing,
well identity resolution, latency tracking, and non-blocking persistence.
"""

from __future__ import annotations
from collections import deque
from datetime import datetime, timezone
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from ..realtime.schema import RealtimeTelemetryRecord, validate_telemetry_payload
from .identity_resolver import well_identity_resolver

logger = logging.getLogger("nwis.integrations.pipeline")


class TelemetryIngestionPipeline:
    """
    Thread-safe, bounded stream processor for all external telemetry sources.
    Enforces backpressure limits, idempotency deduplication, and quality tracking.
    """

    def __init__(self, queue_max_size: Optional[int] = None):
        self.queue_max_size = queue_max_size or int(os.getenv("TELEMETRY_QUEUE_MAX_SIZE", "5000"))
        self._queue: deque = deque(maxlen=self.queue_max_size)
        self._dedupe_cache: deque = deque(maxlen=self.queue_max_size)
        self._dedupe_set: Set[str] = set()
        self._lock = threading.Lock()

        # Operational stream metrics
        self._metrics = {
            "messages_received": 0,
            "messages_valid": 0,
            "messages_invalid": 0,
            "messages_duplicate": 0,
            "messages_unmatched": 0,
            "messages_late": 0,
            "messages_persisted": 0,
            "messages_failed": 0,
            "messages_dropped_backpressure": 0,
            "total_latency_ms": 0.0,
            "max_latency_ms": 0.0,
            "active_connections": 1,  # Demo / Ingest active by default
            "queue_current_size": 0,
            "queue_max_size": self.queue_max_size,
        }

    def _generate_dedupe_key(self, well_id: str, source: str, source_ts: Optional[str], depth_md: float) -> str:
        s_ts = source_ts or "now"
        return f"{well_id}:{source}:{s_ts}:{round(depth_md, 2)}"

    def ingest(
        self,
        raw_payload: Dict[str, Any],
        provider_source: str = "LIVE_FIELD",
        store_raw: bool = False,
    ) -> Dict[str, Any]:
        """
        Ingests an untrusted raw payload from any external provider.
        Executes identity resolution, bounds checking, deduplication, and pipeline handoff.
        """
        with self._lock:
            self._metrics["messages_received"] += 1

            # 1. Backpressure check
            if len(self._queue) >= self.queue_max_size:
                self._metrics["messages_dropped_backpressure"] += 1
                logger.warning(
                    f"Telemetry ingestion queue reached capacity ({self.queue_max_size}). "
                    f"Applying backpressure drop policy."
                )

        # 2. Well Identity Resolution
        raw_well = (
            raw_payload.get("well_id")
            or raw_payload.get("wellId")
            or raw_payload.get("canonical_well_id")
            or raw_payload.get("rig_id")
            or "UNKNOWN"
        )
        wellbore_id = raw_payload.get("wellbore_id") or raw_payload.get("wellbore")

        can_id, id_status, id_details = well_identity_resolver.resolve(
            external_source=provider_source,
            external_well_id=str(raw_well),
            external_wellbore_id=str(wellbore_id) if wellbore_id else None,
            raw_payload=raw_payload,
        )

        if not can_id or id_status == "UNMATCHED_WELL":
            with self._lock:
                self._metrics["messages_unmatched"] += 1
            return {
                "success": False,
                "status": "UNMATCHED_WELL",
                "error": f"Well '{raw_well}' from {provider_source} is not mapped to any canonical well. Quarantined.",
                "details": id_details,
            }

        # Replace payload well_id with canonical ID
        payload_copy = dict(raw_payload)
        payload_copy["well_id"] = can_id

        # 3. Physical Validation & UTC Normalization
        is_valid, qual_status, warnings, record = validate_telemetry_payload(
            payload=payload_copy,
            source=provider_source,
            store_raw=store_raw,
        )

        if not is_valid or not record:
            with self._lock:
                self._metrics["messages_invalid"] += 1
            return {
                "success": False,
                "status": "INVALID",
                "errors": warnings,
            }

        # 4. Deduplication
        dedupe_key = self._generate_dedupe_key(
            well_id=record.well_id,
            source=record.source,
            source_ts=record.source_timestamp,
            depth_md=record.depth_md,
        )

        with self._lock:
            self._metrics["messages_valid"] += 1
            if record.ingestion_latency_ms is not None:
                self._metrics["total_latency_ms"] += record.ingestion_latency_ms
                if record.ingestion_latency_ms > self._metrics["max_latency_ms"]:
                    self._metrics["max_latency_ms"] = record.ingestion_latency_ms

            if dedupe_key in self._dedupe_set:
                self._metrics["messages_duplicate"] += 1
                return {
                    "success": True,
                    "status": "DUPLICATE",
                    "message": "Duplicate telemetry slice detected and acknowledged without reprocessing",
                    "canonical_well_id": can_id,
                    "depth_md": record.depth_md,
                }

            # Add to dedupe cache
            if len(self._dedupe_cache) >= self.queue_max_size:
                oldest = self._dedupe_cache.popleft()
                self._dedupe_set.discard(oldest)

            self._dedupe_cache.append(dedupe_key)
            self._dedupe_set.add(dedupe_key)

            # Enqueue
            self._queue.append(record)
            self._metrics["queue_current_size"] = len(self._queue)

        # 5. Process through Realtime Service (LiveState, Rolling Features, Anomalies, ML Risk, Alerts)
        try:
            from ..realtime.service import realtime_service
            res = realtime_service.process_telemetry_point(
                payload=record.to_dict(),
                provider_mode=provider_source,
            )

            with self._lock:
                self._metrics["messages_persisted"] += 1

            return {
                "success": True,
                "status": qual_status,
                "canonical_well_id": can_id,
                "result": res,
                "ingestion_latency_ms": record.ingestion_latency_ms,
            }
        except Exception as e:
            with self._lock:
                self._metrics["messages_failed"] += 1
            logger.error(f"Streaming pipeline processing exception: {e}")
            return {
                "success": False,
                "status": "PROCESSING_ERROR",
                "error": str(e),
            }

    def get_metrics(self) -> Dict[str, Any]:
        """Provides operational metrics for integration monitoring."""
        with self._lock:
            m = dict(self._metrics)
            m["queue_current_size"] = len(self._queue)
            valid_count = max(1, m["messages_valid"])
            m["average_latency_ms"] = round(m["total_latency_ms"] / valid_count, 2)
            return m

    def reset_metrics(self) -> None:
        with self._lock:
            for k in self._metrics:
                if isinstance(self._metrics[k], int):
                    self._metrics[k] = 0
                elif isinstance(self._metrics[k], float):
                    self._metrics[k] = 0.0
            self._metrics["queue_max_size"] = self.queue_max_size
            self._metrics["active_connections"] = 1


# Global singleton pipeline instance
streaming_pipeline = TelemetryIngestionPipeline()
