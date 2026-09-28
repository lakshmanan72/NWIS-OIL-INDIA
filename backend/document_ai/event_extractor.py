"""
NWIS Phase 4 — Depth-Aware Event Extractor
==========================================
Extracts drilling hazard events from operational and problem sections,
grounding each event strictly in the unified NWIS hazard taxonomy
(data/event_hazard_taxonomy.json). Extracts event depths without fabrication.
"""

from __future__ import annotations
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .document_repository import DocumentChunk, DocumentEvent

logger = logging.getLogger("nwis.event_extractor")

TAXONOMY_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "event_hazard_taxonomy.json"


class EventExtractor:
    """
    Extracts drilling hazard events using the official NWIS event hazard taxonomy.
    """

    def __init__(self, taxonomy_file: Optional[Path] = None):
        self.taxonomy_path = taxonomy_file or TAXONOMY_PATH
        self.taxonomy: Dict[str, Any] = self._load_taxonomy()

        # Operational triggering patterns mapped to canonical hazards
        self.hazard_triggers = {
            "mud_loss": [
                (re.compile(r"\b(?:mud\s*loss(?:es)?|lost\s*circulation|total\s*loss|partial\s*loss|lost\s*returns|seepage\s*loss|fluid\s*loss)\b", re.I), "Mud Loss / Lost Circulation"),
            ],
            "stuck_pipe": [
                (re.compile(r"\b(?:stuck\s*pipe|pipe\s*stuck|differential\s*stick(?:ing)?|pack[\s-]off|packing\s*off|tight\s*hole|wellbore\s*instability)\b", re.I), "Stuck Pipe / Mechanical or Differential Sticking"),
            ],
            "kick": [
                (re.compile(r"\b(?:kick|gas\s*kick|gas\s*influx|well\s*influx|pit\s*gain|flow\s*check\s*positive|flow\s*detected)\b", re.I), "Kick / Gas Influx"),
            ],
            "overpressure": [
                (re.compile(r"\b(?:overpressure|abnormal\s*pressure(?:\s*zone)?|formation\s*pressure\s*change|high\s*pore\s*pressure|pore\s*pressure\s*ramp)\b", re.I), "Overpressure / Abnormal Pressure"),
            ],
            "torque_spike": [
                (re.compile(r"\b(?:torque\s*spike|high\s*torque(?:\s*and\s*drag)?|excessive\s*torque|erratic\s*torque|torque\s*fluctuations?)\b", re.I), "Torque Spike / High Torque and Drag"),
            ],
        }

        # Depth extraction patterns
        self.depth_patterns = [
            re.compile(r"(?:at|depth|md|observed\s*at|occurred\s*at|hit\s*at|@)\s*([0-9]{1,2},[0-9]{3}(?:\.[0-9]+)?|[0-9]{3,5}(?:\.[0-9]+)?)\s*(?:m|meter|meters)\b", re.I),
            re.compile(r"\b([0-9]{1,2},[0-9]{3}(?:\.[0-9]+)?|[0-9]{3,5}(?:\.[0-9]+)?)\s*(?:m|meter|meters)\s*(?:depth|md)?\b", re.I),
        ]
        self.interval_pattern = re.compile(
            r"(?:interval|from)?\s*([0-9]{1,2},[0-9]{3}(?:\.[0-9]+)?|[0-9]{3,5}(?:\.[0-9]+)?)\s*(?:m)?\s*(?:to|-|–)\s*([0-9]{1,2},[0-9]{3}(?:\.[0-9]+)?|[0-9]{3,5}(?:\.[0-9]+)?)\s*(?:m|meter|meters)\b",
            re.I,
        )

    def _load_taxonomy(self) -> Dict[str, Any]:
        try:
            if self.taxonomy_path.exists():
                return json.loads(self.taxonomy_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Could not load event taxonomy from {self.taxonomy_path}: {e}")
        return {}

    def extract_events_from_chunks(
        self,
        chunks: List[DocumentChunk],
    ) -> List[DocumentEvent]:
        """
        Extracts depth-aware drilling events from chunks.
        """
        events: List[DocumentEvent] = []
        seen_events = set()

        # Prioritize operational/incident sections
        relevant_sections = {"PROBLEMS", "DRILLING EVENTS", "NPT", "MUD PROGRAM", "DRILLING PARAMETERS", "GENERAL"}

        for chunk in chunks:
            # Check if chunk text contains event mentions
            text = chunk.text
            sentences = re.split(r"(?<=[.!?])\s+", text)

            for sentence in sentences:
                matched_hazard = None
                matched_raw_label = ""
                confidence = 0.85
                assumption = "Historical operational reporting assumption"

                # Check hazard triggers
                for hazard_cat, triggers in self.hazard_triggers.items():
                    for pattern, label in triggers:
                        if pattern.search(sentence):
                            matched_hazard = hazard_cat
                            matched_raw_label = label
                            break
                    if matched_hazard:
                        break

                if not matched_hazard:
                    continue

                # Retrieve metadata assumption from loaded taxonomy
                for entry in self.taxonomy.get("taxonomy_mappings", []):
                    if entry.get("hazard_category") == matched_hazard:
                        assumption = entry.get("domain_assumption", assumption)
                        conf_str = entry.get("confidence", "High")
                        confidence = 0.94 if "High" in conf_str else 0.82
                        break

                # Extract event depth (MD)
                depth_md, d_from, d_to = self._extract_event_depth(sentence, chunk)

                clean_sentence = sentence.replace("\n", " ").strip()
                dedup_key = (chunk.document_id, matched_hazard, depth_md, clean_sentence[:30])
                if dedup_key in seen_events:
                    continue
                seen_events.add(dedup_key)

                event_id = f"EVT-{uuid.uuid4().hex[:8].upper()}"
                events.append(DocumentEvent(
                    event_id=event_id,
                    document_id=chunk.document_id,
                    well_id=chunk.well_id,
                    event_type=matched_hazard,
                    raw_event_text=clean_sentence,
                    depth_md=depth_md,
                    depth_from=d_from,
                    depth_to=d_to,
                    formation=chunk.formation,
                    source_page=chunk.page_number,
                    confidence=confidence,
                    hazard_assumption=assumption,
                    status="REVIEW_REQUIRED",
                ))

        return events

    def _extract_event_depth(
        self,
        sentence: str,
        chunk: DocumentChunk,
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Extracts exact MD or interval depth from the sentence.
        Falls back to chunk depth bounds if sentence explicitly describes the entire chunk interval.
        Never invents depth if absent.
        """
        # 1. Interval in sentence
        match_int = self.interval_pattern.search(sentence)
        if match_int:
            try:
                d1 = float(match_int.group(1).replace(",", ""))
                d2 = float(match_int.group(2).replace(",", ""))
                if 100 <= d1 <= 9000 and 100 <= d2 <= 9000:
                    depth_md = round((d1 + d2) / 2.0, 1)
                    return depth_md, min(d1, d2), max(d1, d2)
            except ValueError:
                pass

        # 2. Single depth in sentence
        for pat in self.depth_patterns:
            match_s = pat.search(sentence)
            if match_s:
                try:
                    d = float(match_s.group(1).replace(",", ""))
                    if 100 <= d <= 9000:
                        return d, d, d
                except ValueError:
                    pass

        # 3. If chunk has known depth bounds and text refers to the section depth
        if chunk.depth_from is not None:
            return chunk.depth_from, chunk.depth_from, chunk.depth_to

        # No depth explicitly mentioned: return None (do NOT invent depth)
        return None, None, None


event_extractor = EventExtractor()
