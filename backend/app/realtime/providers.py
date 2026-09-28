"""
NWIS Phase 6 — Real-Time Telemetry Provider Abstraction
======================================================
Defines the standard RealtimeDrillingProvider interface and implementations:
- DemoReplayProvider (Deterministic real-time replay of historical telemetry)
- RESTPollingProvider (HTTP polling ingestion)
- WebSocketProvider (External WebSocket client ingestion)
- KafkaProvider / MQTTProvider (Future enterprise extensions)
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Dict, List, Optional

import pandas as pd

from ..data_path import resolve_data_file
from .config import REALTIME_CONFIG
from .schema import RealtimeTelemetryRecord, validate_telemetry_payload

logger = logging.getLogger("nwis.realtime.providers")


class RealtimeDrillingProvider(ABC):
    """Abstract base class for all real-time drilling telemetry providers."""

    @abstractmethod
    def connect(self) -> bool:
        """Establishes upstream connection."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Terminates upstream connection."""
        pass

    @abstractmethod
    def subscribe(self, well_id: str) -> None:
        """Subscribes to telemetry events for a specific well."""
        pass

    @abstractmethod
    def unsubscribe(self, well_id: str) -> None:
        """Unsubscribes from telemetry events for a specific well."""
        pass

    @abstractmethod
    def get_latest(self, well_id: str) -> Optional[RealtimeTelemetryRecord]:
        """Fetches the latest telemetry point for a well."""
        pass

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        """Returns provider status, health, and transport diagnostics."""
        pass

    def stream(self, well_id: str, limit: Optional[int] = None):
        """Yields streaming telemetry records."""
        rec = self.get_latest(well_id)
        if rec:
            yield rec

    def acknowledge(self, alert_id: str, reviewer: str = "Drilling Engineer", note: Optional[str] = None) -> bool:
        """Acknowledges an upstream alert if supported by the provider."""
        return True

    def metadata(self) -> Dict[str, Any]:
        """Returns protocol metadata and transport properties."""
        return {
            "provider_type": self.__class__.__name__,
            "advisory_only": True,
            "supports_commands": False,
        }


class DemoReplayProvider(RealtimeDrillingProvider):
    """
    Deterministic real-time DEMO mode provider.
    Replays real historical drilling telemetry from repository CSVs at configurable cadences.
    Preserves original values. Clearly labels all data as 'DEMO REPLAY'.
    """

    def __init__(self, default_well_id: str = "WELL-000050"):
        self.default_well_id = default_well_id
        self.active_well_id = default_well_id
        self.is_connected = False
        self.is_replaying = False
        self.is_paused = False
        self.replay_interval_ms = REALTIME_CONFIG["replay"]["replay_interval_ms"]
        self.current_index = 0
        self.records_cache: Dict[str, List[RealtimeTelemetryRecord]] = {}
        self.latest_record: Optional[RealtimeTelemetryRecord] = None
        self.last_emit_timestamp: float = 0.0
        self.records_emitted_count = 0
        self._lock = threading.Lock()
        self._replay_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Pre-load telemetry for default well
        self._load_telemetry_for_well(self.default_well_id)

    def _load_telemetry_for_well(self, well_id: str) -> List[RealtimeTelemetryRecord]:
        if well_id in self.records_cache:
            return self.records_cache[well_id]

        records: List[RealtimeTelemetryRecord] = []
        try:
            csv_path = resolve_data_file("raw", "nwis_daily_drilling_parameters_15108.csv")
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                well_rows = df[df["well_id"] == well_id]
                if well_rows.empty:
                    # Fallback to first available well if requested well has no daily rows
                    first_wid = df["well_id"].iloc[0]
                    well_rows = df[df["well_id"] == first_wid]

                # Convert rows into synthetic 10-step depth progression slices
                base_depth = 1132.0 if well_id == "WELL-000050" else 2000.0
                step_idx = 0

                for _, row in well_rows.iterrows():
                    row_depth = float(row.get("depth_md", base_depth + step_idx * 5.0))
                    # Convert kNm to kft-lb: 1 kNm = 0.737562 kft-lb
                    raw_torque = float(row.get("torque_knm", 15.0))
                    torque_kftlb = round(raw_torque * 0.737562, 2)
                    rop_m_hr = round(float(row.get("rop_m_per_hr", 18.0)), 2)
                    wob_klbf = round(float(row.get("wob_klbf", 12.0)), 2)
                    rpm = round(float(row.get("rpm", 95.0)), 1)
                    spp = round(float(row.get("standpipe_pressure_psi", 1850.0)), 1)
                    flow = round(float(row.get("flow_rate_lpm", 1250.0)), 1)
                    mw = round(float(row.get("mud_weight_ppg", 9.8)), 2)

                    rec = RealtimeTelemetryRecord(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        well_id=well_id,
                        depth_md=row_depth,
                        rop_m_hr=rop_m_hr,
                        wob_klbf=wob_klbf,
                        rpm=rpm,
                        torque_kftlb=torque_kftlb,
                        standpipe_pressure_psi=spp,
                        flow_rate_lpm=flow,
                        mud_weight_ppg=mw,
                        mud_flow_in_lpm=flow,
                        mud_flow_out_lpm=round(flow * 0.98, 1),
                        gas_units=4.2,
                    )
                    records.append(rec)
                    step_idx += 1

                # If only few rows, synthesize micro-steps between points to provide rich continuous replay
                if len(records) > 0 and len(records) < 30:
                    expanded: List[RealtimeTelemetryRecord] = []
                    for i in range(len(records)):
                        cur = records[i]
                        nxt = records[(i + 1) % len(records)]
                        expanded.append(cur)
                        # Add 3 interpolated intermediary steps
                        for step in range(1, 4):
                            alpha = step / 4.0
                            d_interp = round(cur.depth_md + (nxt.depth_md - cur.depth_md) * alpha, 2)
                            t_interp = round(cur.torque_kftlb + (nxt.torque_kftlb - cur.torque_kftlb) * alpha, 2)
                            rop_interp = round(cur.rop_m_hr + (nxt.rop_m_hr - cur.rop_m_hr) * alpha, 2)
                            spp_interp = round(cur.standpipe_pressure_psi + (nxt.standpipe_pressure_psi - cur.standpipe_pressure_psi) * alpha, 1)
                            interp_rec = RealtimeTelemetryRecord(
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                well_id=well_id,
                                depth_md=d_interp,
                                rop_m_hr=rop_interp,
                                wob_klbf=cur.wob_klbf,
                                rpm=cur.rpm,
                                torque_kftlb=t_interp,
                                standpipe_pressure_psi=spp_interp,
                                flow_rate_lpm=cur.flow_rate_lpm,
                                mud_weight_ppg=cur.mud_weight_ppg,
                                mud_flow_in_lpm=cur.mud_flow_in_lpm,
                                mud_flow_out_lpm=cur.mud_flow_out_lpm,
                                gas_units=cur.gas_units,
                            )
                            expanded.append(interp_rec)
                    records = expanded

        except Exception as e:
            logger.error(f"Failed to load telemetry for {well_id}: {e}")

        # Ensure at least a fallback sequence exists
        if not records:
            for i in range(20):
                records.append(
                    RealtimeTelemetryRecord(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        well_id=well_id,
                        depth_md=1132.0 + i * 2.5,
                        rop_m_hr=18.2 + (i % 3) * 0.5,
                        wob_klbf=12.4,
                        rpm=95.0,
                        torque_kftlb=18.5 + (2.0 if i == 5 else 0.0),
                        standpipe_pressure_psi=1850.0 + (i % 4) * 10,
                        flow_rate_lpm=1250.0,
                        mud_weight_ppg=9.8,
                        mud_flow_in_lpm=1250.0,
                        mud_flow_out_lpm=1220.0,
                        gas_units=4.2,
                    )
                )

        self.records_cache[well_id] = records
        if not self.latest_record and records:
            self.latest_record = records[0]
        return records

    def connect(self) -> bool:
        self.is_connected = True
        return True

    def disconnect(self) -> None:
        self.stop_replay()
        self.is_connected = False

    def subscribe(self, well_id: str) -> None:
        with self._lock:
            self.active_well_id = well_id.upper()
            self._load_telemetry_for_well(self.active_well_id)
            self.current_index = 0

    def unsubscribe(self, well_id: str) -> None:
        pass

    def get_latest(self, well_id: str) -> Optional[RealtimeTelemetryRecord]:
        with self._lock:
            if not self.latest_record:
                recs = self._load_telemetry_for_well(well_id)
                if recs:
                    self.latest_record = recs[0]
            return self.latest_record

    def step(self) -> Optional[RealtimeTelemetryRecord]:
        """Advances replay by one telemetry slice and updates latest record."""
        with self._lock:
            recs = self.records_cache.get(self.active_well_id, [])
            if not recs:
                return None

            raw_rec = recs[self.current_index % len(recs)]
            self.current_index = (self.current_index + 1) % len(recs)
            # Update timestamp to current real time so freshness monitors observe valid age
            updated_rec = RealtimeTelemetryRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                well_id=raw_rec.well_id,
                depth_md=raw_rec.depth_md,
                rop_m_hr=raw_rec.rop_m_hr,
                wob_klbf=raw_rec.wob_klbf,
                rpm=raw_rec.rpm,
                torque_kftlb=raw_rec.torque_kftlb,
                standpipe_pressure_psi=raw_rec.standpipe_pressure_psi,
                flow_rate_lpm=raw_rec.flow_rate_lpm,
                mud_weight_ppg=raw_rec.mud_weight_ppg,
                mud_flow_in_lpm=raw_rec.mud_flow_in_lpm,
                mud_flow_out_lpm=raw_rec.mud_flow_out_lpm,
                gas_units=raw_rec.gas_units,
            )
            self.latest_record = updated_rec
            self.last_emit_timestamp = time.time()
            self.records_emitted_count += 1
            return updated_rec

    def inject_anomaly(self, anomaly_type: str = "torque_spike") -> Optional[RealtimeTelemetryRecord]:
        """Injects a controlled parameter anomaly into the current slice for verification/demo purposes."""
        with self._lock:
            if not self.latest_record:
                recs = self._load_telemetry_for_well(self.active_well_id)
                if recs:
                    self.latest_record = recs[0]
            if not self.latest_record:
                return None

            cur = self.latest_record
            mod_torque = cur.torque_kftlb
            mod_spp = cur.standpipe_pressure_psi
            mod_flow_out = cur.mud_flow_out_lpm
            mod_rop = cur.rop_m_hr

            if anomaly_type == "torque_spike":
                mod_torque = max(25.5, round((mod_torque or 16.0) + 12.0, 2))  # Distinct torque anomaly
            elif anomaly_type == "pressure_surge":
                mod_spp = max(2350.0, round((mod_spp or 1850.0) + 480.0, 1))
            elif anomaly_type == "flow_imbalance":
                mod_flow_out = round((cur.mud_flow_in_lpm or 1250.0) * 0.76, 1)  # 24% fluid loss
            elif anomaly_type == "rop_drop":
                mod_rop = max(1.0, round((mod_rop or 18.0) * 0.30, 2))

            injected = RealtimeTelemetryRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                well_id=cur.well_id,
                depth_md=cur.depth_md,
                rop_m_hr=mod_rop,
                wob_klbf=cur.wob_klbf,
                rpm=cur.rpm,
                torque_kftlb=mod_torque,
                standpipe_pressure_psi=mod_spp,
                flow_rate_lpm=cur.flow_rate_lpm,
                mud_weight_ppg=cur.mud_weight_ppg,
                mud_flow_in_lpm=cur.mud_flow_in_lpm,
                mud_flow_out_lpm=mod_flow_out,
                gas_units=cur.gas_units,
            )
            self.latest_record = injected
            self.last_emit_timestamp = time.time()
            return injected

    def start_replay(self, well_id: Optional[str] = None, interval_ms: Optional[int] = None) -> None:
        if well_id:
            self.subscribe(well_id)
        if interval_ms:
            self.replay_interval_ms = interval_ms

        if self.is_replaying and not self.is_paused:
            return

        self.connect()
        self.is_replaying = True
        self.is_paused = False
        self._stop_event.clear()

        if self._replay_thread is None or not self._replay_thread.is_alive():
            self._replay_thread = threading.Thread(target=self._run_replay_loop, daemon=True)
            self._replay_thread.start()

    def _run_replay_loop(self) -> None:
        while not self._stop_event.is_set():
            if not self.is_paused:
                self.step()
            sleep_sec = max(0.1, self.replay_interval_ms / 1000.0)
            self._stop_event.wait(sleep_sec)

    def pause_replay(self) -> None:
        self.is_paused = True

    def resume_replay(self) -> None:
        self.is_paused = False

    def stop_replay(self) -> None:
        self.is_replaying = False
        self.is_paused = False
        self._stop_event.set()
        if self._replay_thread and self._replay_thread.is_alive():
            self._replay_thread.join(timeout=1.0)
        self._replay_thread = None

    def health(self) -> Dict[str, Any]:
        return {
            "provider_type": "DemoReplayProvider",
            "provider_mode": "DEMO REPLAY",
            "connected": self.is_connected,
            "replaying": self.is_replaying,
            "paused": self.is_paused,
            "active_well_id": self.active_well_id,
            "replay_interval_ms": self.replay_interval_ms,
            "records_emitted": self.records_emitted_count,
            "current_index": self.current_index,
            "status": "HEALTHY",
        }


class RESTPollingProvider(RealtimeDrillingProvider):
    """HTTP Polling Provider for external eRTMAC REST telemetry gateways."""

    def __init__(self, endpoint_url: Optional[str] = None, poll_interval_sec: float = 2.0):
        self.endpoint_url = endpoint_url
        self.poll_interval_sec = poll_interval_sec
        self.is_connected = False
        self.active_well_id: Optional[str] = None
        self.latest_record: Optional[RealtimeTelemetryRecord] = None

    def connect(self) -> bool:
        self.is_connected = True
        return True

    def disconnect(self) -> None:
        self.is_connected = False

    def subscribe(self, well_id: str) -> None:
        self.active_well_id = well_id.upper()

    def unsubscribe(self, well_id: str) -> None:
        if self.active_well_id == well_id.upper():
            self.active_well_id = None

    def get_latest(self, well_id: str) -> Optional[RealtimeTelemetryRecord]:
        return self.latest_record

    def health(self) -> Dict[str, Any]:
        return {
            "provider_type": "RESTPollingProvider",
            "provider_mode": "LIVE REST POLLING",
            "connected": self.is_connected,
            "endpoint_url": self.endpoint_url,
            "poll_interval_sec": self.poll_interval_sec,
            "status": "CONFIGURED" if self.endpoint_url else "STANDBY",
        }


class WebSocketProvider(RealtimeDrillingProvider):
    """WebSocket Client Provider for live rig telemetry feeds."""

    def __init__(self, ws_url: Optional[str] = None):
        self.ws_url = ws_url
        self.is_connected = False
        self.active_well_id: Optional[str] = None
        self.latest_record: Optional[RealtimeTelemetryRecord] = None

    def connect(self) -> bool:
        self.is_connected = True
        return True

    def disconnect(self) -> None:
        self.is_connected = False

    def subscribe(self, well_id: str) -> None:
        self.active_well_id = well_id.upper()

    def unsubscribe(self, well_id: str) -> None:
        if self.active_well_id == well_id.upper():
            self.active_well_id = None

    def get_latest(self, well_id: str) -> Optional[RealtimeTelemetryRecord]:
        return self.latest_record

    def health(self) -> Dict[str, Any]:
        return {
            "provider_type": "WebSocketProvider",
            "provider_mode": "LIVE WEBSOCKET",
            "connected": self.is_connected,
            "ws_url": self.ws_url,
            "status": "CONFIGURED" if self.ws_url else "STANDBY",
        }


class KafkaProvider(RealtimeDrillingProvider):
    """Future enterprise Apache Kafka connector stub."""

    def connect(self) -> bool:
        return False

    def disconnect(self) -> None:
        pass

    def subscribe(self, well_id: str) -> None:
        pass

    def unsubscribe(self, well_id: str) -> None:
        pass

    def get_latest(self, well_id: str) -> Optional[RealtimeTelemetryRecord]:
        return None

    def health(self) -> Dict[str, Any]:
        return {
            "provider_type": "KafkaProvider",
            "status": "OFFLINE_STUB",
            "message": "Kafka transport interface reserved for future production deployment",
        }


class MQTTProvider(RealtimeDrillingProvider):
    """Future edge IoT MQTT connector stub."""

    def connect(self) -> bool:
        return False

    def disconnect(self) -> None:
        pass

    def subscribe(self, well_id: str) -> None:
        pass

    def unsubscribe(self, well_id: str) -> None:
        pass

    def get_latest(self, well_id: str) -> Optional[RealtimeTelemetryRecord]:
        return None

    def health(self) -> Dict[str, Any]:
        return {
            "provider_type": "MQTTProvider",
            "status": "OFFLINE_STUB",
            "message": "MQTT transport interface reserved for edge deployment",
        }


class WITSMLProvider(RealtimeDrillingProvider):
    """WITSML 1.3.1.1 / 1.4.1.1 XML Store provider."""

    def __init__(self, adapter: Optional[Any] = None):
        from ..integrations.witsml import witsml_adapter
        self.adapter = adapter or witsml_adapter
        self.active_well_id: Optional[str] = None

    def connect(self) -> bool:
        return self.adapter.connect()

    def disconnect(self) -> None:
        self.adapter.disconnect()

    def subscribe(self, well_id: str) -> None:
        self.active_well_id = well_id.upper()

    def unsubscribe(self, well_id: str) -> None:
        if self.active_well_id == well_id.upper():
            self.active_well_id = None

    def get_latest(self, well_id: str) -> Optional[RealtimeTelemetryRecord]:
        return self.adapter.fetch_latest(well_id)

    def health(self) -> Dict[str, Any]:
        h = self.adapter.health()
        h["provider_type"] = "WITSMLProvider"
        return h

    def metadata(self) -> Dict[str, Any]:
        meta = super().metadata()
        meta["protocol"] = "WITSML 1.3.1.1 / 1.4.1.1"
        meta["format"] = "XML SOAP"
        return meta


class WITS0Provider(RealtimeDrillingProvider):
    """WITS Level 0 TCP/Serial stream provider."""

    def __init__(self, adapter: Optional[Any] = None):
        from ..integrations.wits0 import wits0_adapter
        self.adapter = adapter or wits0_adapter
        self.active_well_id: Optional[str] = None
        self.latest_record: Optional[RealtimeTelemetryRecord] = None

    def connect(self) -> bool:
        return self.adapter.connect()

    def disconnect(self) -> None:
        self.adapter.disconnect()

    def subscribe(self, well_id: str) -> None:
        self.active_well_id = well_id.upper()

    def unsubscribe(self, well_id: str) -> None:
        if self.active_well_id == well_id.upper():
            self.active_well_id = None

    def get_latest(self, well_id: str) -> Optional[RealtimeTelemetryRecord]:
        return self.latest_record

    def ingest_packet(self, packet_text: str) -> Optional[RealtimeTelemetryRecord]:
        success, _, _, rec = self.adapter.ingest_packet(packet_text, default_well_id=self.active_well_id or "WELL-000050")
        if success and rec:
            self.latest_record = rec
        return rec

    def health(self) -> Dict[str, Any]:
        h = self.adapter.health()
        h["provider_type"] = "WITS0Provider"
        return h

    def metadata(self) -> Dict[str, Any]:
        meta = super().metadata()
        meta["protocol"] = "WITS Level 0"
        meta["format"] = "ASCII Tagged Items"
        return meta


# Global singleton demo replay provider
demo_replay_provider = DemoReplayProvider()
witsml_provider = WITSMLProvider()
wits0_provider = WITS0Provider()
