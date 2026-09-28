"""
NWIS Phase 4 — Section-Aware Document Chunker
=============================================
Performs semantic, structure-aware chunking of technical drilling reports.
Avoids arbitrary character-boundary splitting by identifying geological and operational
section headers, retaining page numbers, depth boundaries, and formation context.
"""

from __future__ import annotations
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .document_repository import DocumentChunk


class DocumentChunker:
    """
    Intelligent section-aware chunker for WCR, DDR, and engineering reports.
    """

    # Section header patterns
    SECTION_PATTERNS = [
        ("WELL INFORMATION", re.compile(r"^(?:1\.?\s*)?(?:well\s+(?:information|summary|header|identification|data)|general\s+well\s+data)", re.I)),
        ("FORMATION", re.compile(r"^(?:2\.?\s*)?(?:formation\s+(?:tops|evaluation|summary)|stratigraphy|geological\s+summary|lithology\s+summary)", re.I)),
        ("DRILLING PARAMETERS", re.compile(r"^(?:3\.?\s*)?(?:drilling\s+parameters|bha\s+(?:record|summary)|bit\s+(?:record|summary)|hydraulics|drilling\s+assembly)", re.I)),
        ("MUD PROGRAM", re.compile(r"^(?:4\.?\s*)?(?:mud\s+(?:program|properties|system|logging|data)|drilling\s+fluid)", re.I)),
        ("DRILLING EVENTS", re.compile(r"^(?:5\.?\s*)?(?:drilling\s+events|operational\s+(?:narrative|summary|log|history)|daily\s+operations|chronological\s+log)", re.I)),
        ("CASING", re.compile(r"^(?:6\.?\s*)?(?:casing\s+(?:program|record|summary|data)|liner\s+details)", re.I)),
        ("CEMENTING", re.compile(r"^(?:7\.?\s*)?(?:cementing\s+(?:report|operations|summary|data)|slurry\s+properties)", re.I)),
        ("PROBLEMS", re.compile(r"^(?:8\.?\s*)?(?:problems|hazards|drilling\s+incidents|unplanned\s+events|stuck\s+pipe\s+incident|lost\s+circulation\s+event)", re.I)),
        ("NPT", re.compile(r"^(?:9\.?\s*)?(?:npt|non[\s-]productive\s+time|lost\s+time|downtime\s+summary)", re.I)),
        ("LESSONS LEARNED", re.compile(r"^(?:10\.?\s*)?(?:lessons\s+learned|recommendations|conclusions\s+and\s+recommendations)", re.I)),
    ]

    # Known Indian sedimentary basin formations for automatic tagging
    KNOWN_FORMATIONS = [
        "Barail", "Bhuban", "Bokabil", "Renji", "Jenam", "Disang", "Tipam", "Girujan",
        "Kopili", "Sylhet", "Therria", "Langpar", "Mahadek", "Surma", "Kalol", "Kadi",
        "Tarapur", "Ankleshwar", "Olpad", "Cambay Shale", "Vaso", "Chhatral", "Mehsana",
        "Mandapeta", "Raghavapuram", "Gollapalli", "Tirupati", "Vadapalli", "Ravva",
        "Matsya", "Bhuvanagiri", "Nannilam", "Kamalapuram", "Cuddalore", "Subathu", "Dharmsala",
    ]

    DEPTH_INTERVAL_REGEX = re.compile(
        r"(?:depth|interval|from)?\s*([0-9]{1,2},[0-9]{3}(?:\.[0-9]+)?|[0-9]{3,5}(?:\.[0-9]+)?)\s*(?:m|meter|meters)?\s*(?:to|-|–|—)\s*([0-9]{1,2},[0-9]{3}(?:\.[0-9]+)?|[0-9]{3,5}(?:\.[0-9]+)?)\s*(?:m|meter|meters)?",
        re.IGNORECASE,
    )
    DEPTH_SINGLE_REGEX = re.compile(
        r"(?:at|depth|md)\s*([0-9]{1,2},[0-9]{3}(?:\.[0-9]+)?|[0-9]{3,5}(?:\.[0-9]+)?)\s*(?:m|meter|meters)\b",
        re.IGNORECASE,
    )

    def chunk_document(
        self,
        pages: List[Dict[str, Any]],
        document_id: str,
        well_id: str = "UNMATCHED_WELL",
        document_type: str = "WCR",
    ) -> List[DocumentChunk]:
        """
        Splits extracted pages into semantically distinct section chunks.
        """
        chunks: List[DocumentChunk] = []
        current_section = "WELL INFORMATION" if document_type == "WCR" else "DRILLING EVENTS"

        for page in pages:
            page_num = page.get("page_number", 1)
            raw_text = page.get("text", "")
            if not raw_text.strip():
                continue

            # Split text by paragraphs (two newlines or clear headings)
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw_text) if p.strip()]

            for para in paragraphs:
                # Check for section header transitions
                first_line = para.split("\n")[0].strip()
                for section_name, pattern in self.SECTION_PATTERNS:
                    if pattern.search(first_line):
                        current_section = section_name
                        break

                # Extract depth range from paragraph
                depth_from, depth_to = self._extract_depths(para)

                # Extract formation if mentioned
                formation = self._extract_formation(para)

                chunk_id = f"CHK-{uuid.uuid4().hex[:8].upper()}"
                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    well_id=well_id,
                    page_number=page_num,
                    section=current_section,
                    text=para,
                    document_type=document_type,
                    depth_from=depth_from,
                    depth_to=depth_to,
                    formation=formation,
                    is_approved=False,
                )
                chunks.append(chunk)

        return chunks

    def _extract_depths(self, text: str) -> Tuple[Optional[float], Optional[float]]:
        """Extracts depth bounds from text snippet."""
        # Check interval first
        match_interval = self.DEPTH_INTERVAL_REGEX.search(text)
        if match_interval:
            try:
                d1 = float(match_interval.group(1).replace(",", ""))
                d2 = float(match_interval.group(2).replace(",", ""))
                if 100 <= d1 <= 9000 and 100 <= d2 <= 9000:
                    return min(d1, d2), max(d1, d2)
            except ValueError:
                pass

        # Check single depth
        match_single = self.DEPTH_SINGLE_REGEX.search(text)
        if match_single:
            try:
                d = float(match_single.group(1).replace(",", ""))
                if 100 <= d <= 9000:
                    return d, d
            except ValueError:
                pass

        return None, None

    def _extract_formation(self, text: str) -> Optional[str]:
        """Identifies known formation names within text."""
        for form in self.KNOWN_FORMATIONS:
            pattern = rf"\b{re.escape(form)}\b"
            if re.search(pattern, text, re.IGNORECASE):
                return form
        return None


document_chunker = DocumentChunker()
