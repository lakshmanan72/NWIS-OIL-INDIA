"""
NWIS Phase 4 — Entity Extractor
===============================
Extracts structured drilling, geological, and operational engineering entities
strictly from explicit document text. Does not hallucinate or invent values.
Every extracted fact is tagged with unit, confidence, source text snippet, and page number.
"""

from __future__ import annotations
import re
import uuid
from typing import Any, Dict, List, Optional

from .document_repository import DocumentChunk, DocumentExtraction


class EntityExtractor:
    """
    Extracts canonical petroleum engineering entities with strict citation traceability.
    """

    PATTERNS = {
        "well_id": (
            re.compile(r"\b(WELL-[0-9]{6})\b", re.I),
            None,
            0.99,
        ),
        "well_name": (
            re.compile(r"(?:well\s*name|well)\s*[:=\-]\s*([A-Za-z0-9\-_/]+(?:\s+[A-Za-z0-9\-_/]+)?)", re.I),
            None,
            0.95,
        ),
        "field": (
            re.compile(r"(?:field)\s*[:=\-]\s*([A-Za-z0-9\-]+(?:\s+[A-Za-z0-9\-]+)?)", re.I),
            None,
            0.90,
        ),
        "basin": (
            re.compile(r"(?:basin)\s*[:=\-]\s*([A-Za-z0-9\-]+(?:\s+[A-Za-z0-9\-]+)?)", re.I),
            None,
            0.92,
        ),
        "block": (
            re.compile(r"(?:block)\s*[:=\-]\s*([A-Za-z0-9\-/_]+)", re.I),
            None,
            0.90,
        ),
        "latitude": (
            re.compile(r"(?:latitude|lat)\s*[:=\-]?\s*([+\-]?[0-9]{1,2}\.[0-9]{4,8})\s*(?:°|deg)?\s*(?:N|S)?", re.I),
            "deg",
            0.95,
        ),
        "longitude": (
            re.compile(r"(?:longitude|long|lon)\s*[:=\-]?\s*([+\-]?[0-9]{1,3}\.[0-9]{4,8})\s*(?:°|deg)?\s*(?:E|W)?", re.I),
            "deg",
            0.95,
        ),
        "spud_date": (
            re.compile(r"(?:spud\s*date|spudded)\s*[:=\-]?\s*([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4}|[0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})", re.I),
            None,
            0.92,
        ),
        "completion_date": (
            re.compile(r"(?:completion\s*date|rig\s*release)\s*[:=\-]?\s*([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4}|[0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})", re.I),
            None,
            0.90,
        ),
        "total_depth": (
            re.compile(r"(?:total\s*depth|td|final\s*depth)\s*[:=\-]?\s*([0-9]{3,5}(?:\.[0-9]+)?)\s*(m|meter|meters|ft)\b", re.I),
            "m",
            0.96,
        ),
        "mud_weight": (
            re.compile(r"(?:mud\s*weight|density|mw)\s*[:=\-]?\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*(sg|ppg|g/cc|specific gravity)\b", re.I),
            "sg",
            0.92,
        ),
        "rop": (
            re.compile(r"(?:rop|rate\s*of\s*penetration)\s*[:=\-]?\s*([0-9]{1,3}(?:\.[0-9]+)?)\s*(m/hr|m/h|ft/hr)\b", re.I),
            "m/hr",
            0.90,
        ),
        "wob": (
            re.compile(r"(?:wob|weight\s*on\s*bit)\s*[:=\-]?\s*([0-9]{1,3}(?:\.[0-9]+)?)\s*(klbs|klb|tonne|ton|t|kdaN)\b", re.I),
            "tonne",
            0.90,
        ),
        "rpm": (
            re.compile(r"(?:rpm|rotary\s*speed)\s*[:=\-]?\s*([0-9]{2,3})\s*(?:rpm)?\b", re.I),
            "rpm",
            0.88,
        ),
        "torque": (
            re.compile(r"(?:torque)\s*[:=\-]?\s*([0-9]{1,4}(?:\.[0-9]+)?)\s*(kft-lbs|ft-lbs|kn-m|knm)\b", re.I),
            "kft-lbs",
            0.88,
        ),
        "spp": (
            re.compile(r"(?:spp|standpipe\s*pressure|pump\s*pressure)\s*[:=\-]?\s*([0-9]{3,5})\s*(psi|bar)\b", re.I),
            "psi",
            0.90,
        ),
        "ecd": (
            re.compile(r"(?:ecd|equivalent\s*circulating\s*density)\s*[:=\-]?\s*([0-9]{1,2}\.[0-9]+)\s*(sg|ppg)\b", re.I),
            "sg",
            0.92,
        ),
        "npt": (
            re.compile(r"(?:npt|non[\s-]productive\s*time|lost\s*time)\s*[:=\-]?\s*([0-9]{1,4}(?:\.[0-9]+)?)\s*(hrs?|hours?)\b", re.I),
            "hours",
            0.91,
        ),
    }

    # Complex entities (narrative / qualitative observations)
    NARRATIVE_PATTERNS = {
        "casing_issue": re.compile(r"(casing\s*(?:collapse|leak|wear|parted|damage|deformation)[^.]*\.)", re.I),
        "cementing_issue": re.compile(r"((?:poor\s*cement\s*bond|cement\s*channeling|lost\s*slurry|slurry\s*flash\s*set|cbl\s*indicates\s*poor\s*bonding)[^.]*\.)", re.I),
        "fishing": re.compile(r"((?:fishing\s*operation|ran\s*overshot|parted\s*string|jarred\s*on\s*fish|fish\s*recovered)[^.]*\.)", re.I),
        "mitigation": re.compile(r"((?:pumped\s*(?:lcm|gunk\s*pill|heavy\s*pill)|spotted\s*acid|jarred\s*downwards|bullheaded|circulated\s*out\s*kick)[^.]*\.)", re.I),
        "lesson_learned": re.compile(r"((?:recommend(?:ed)?\s*to|lesson(?:s)?\s*learned[:\s]|ensure\s*proper\s*hole\s*cleaning|maintain\s*sufficient\s*overbalance)[^.]*\.)", re.I),
    }

    LITHOLOGY_TERMS = [
        "Sandstone", "Shale", "Claystone", "Siltstone", "Limestone", "Dolomite",
        "Basalt", "Coal", "Anhydrite", "Marl", "Volcanic Ash",
    ]

    def extract_entities_from_chunks(
        self,
        chunks: List[DocumentChunk],
    ) -> List[DocumentExtraction]:
        """
        Extracts all recognized technical entities across chunks.
        """
        extractions: List[DocumentExtraction] = []
        seen_keys = set()

        for chunk in chunks:
            text = chunk.text
            page_num = chunk.page_number
            doc_id = chunk.document_id

            # 1. Regex structured entities
            for field_name, (pattern, default_unit, base_conf) in self.PATTERNS.items():
                for match in pattern.finditer(text):
                    val = match.group(1).strip()
                    unit = match.group(2).strip() if (match.lastindex and match.lastindex >= 2 and match.group(2)) else default_unit

                    # Convert numerical values where applicable
                    try:
                        if field_name in ["total_depth", "latitude", "longitude", "mud_weight", "rop", "wob", "rpm", "torque", "spp", "ecd", "npt"]:
                            val_num = float(val)
                            val = val_num
                    except ValueError:
                        pass

                    # Extract context sentence
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    source_snippet = text[start:end].replace("\n", " ").strip()

                    dedup_key = (doc_id, field_name, str(val))
                    if dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        ext_id = f"EXT-{uuid.uuid4().hex[:8].upper()}"
                        extractions.append(DocumentExtraction(
                            extraction_id=ext_id,
                            document_id=doc_id,
                            field=field_name,
                            value=val,
                            unit=unit,
                            confidence=base_conf,
                            source_text=source_snippet,
                            page_number=page_num,
                            status="REVIEW_REQUIRED",
                        ))

            # 2. Lithology extraction
            for lith in self.LITHOLOGY_TERMS:
                pattern = rf"\b{re.escape(lith)}\b"
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    dedup_key = (doc_id, "lithology", lith.lower())
                    if dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        start = max(0, match.start() - 40)
                        end = min(len(text), match.end() + 40)
                        extractions.append(DocumentExtraction(
                            extraction_id=f"EXT-{uuid.uuid4().hex[:8].upper()}",
                            document_id=doc_id,
                            field="lithology",
                            value=lith,
                            unit=None,
                            confidence=0.88,
                            source_text=text[start:end].replace("\n", " ").strip(),
                            page_number=page_num,
                            status="REVIEW_REQUIRED",
                        ))

            # 3. Narrative qualitative entities
            for field_name, pattern in self.NARRATIVE_PATTERNS.items():
                match = pattern.search(text)
                if match:
                    narrative_text = match.group(1).replace("\n", " ").strip()
                    dedup_key = (doc_id, field_name, narrative_text[:40])
                    if dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        extractions.append(DocumentExtraction(
                            extraction_id=f"EXT-{uuid.uuid4().hex[:8].upper()}",
                            document_id=doc_id,
                            field=field_name,
                            value=narrative_text,
                            unit=None,
                            confidence=0.85,
                            source_text=narrative_text,
                            page_number=page_num,
                            status="REVIEW_REQUIRED",
                        ))

            # 4. Formation extraction
            if chunk.formation:
                dedup_key = (doc_id, "formation", chunk.formation.lower())
                if dedup_key not in seen_keys:
                    seen_keys.add(dedup_key)
                    extractions.append(DocumentExtraction(
                        extraction_id=f"EXT-{uuid.uuid4().hex[:8].upper()}",
                        document_id=doc_id,
                        field="formation",
                        value=chunk.formation,
                        unit=None,
                        confidence=0.92,
                        source_text=f"Formation: {chunk.formation} identified in {chunk.section}",
                        page_number=page_num,
                        status="REVIEW_REQUIRED",
                    ))

        return extractions


entity_extractor = EntityExtractor()
