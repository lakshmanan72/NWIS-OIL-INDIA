"""
NWIS Phase 4 — Document Classifier
==================================
Classifies petroleum engineering technical documents into domain categories:
- WCR (Well Completion Report)
- DDR (Daily Drilling Report)
- DRILLING_REPORT
- MUD_LOG
- COMPLETION_REPORT
- OTHER

Provides confidence estimation and flags uncertain classifications for engineer confirmation.
"""

from __future__ import annotations
import re
from typing import Dict, List, Tuple


class DocumentClassifier:
    """
    Keyword and semantic frequency classifier tailored for drilling operations reports.
    """

    def __init__(self):
        # Weighted domain terms per document type
        self.signatures: Dict[str, Dict[str, float]] = {
            "WCR": {
                "well completion report": 4.0,
                "wcr": 3.0,
                "completion report": 3.0,
                "final well report": 2.5,
                "perforation summary": 2.0,
                "initial production test": 2.0,
                "casing and cementing summary": 1.5,
                "geological summary": 1.5,
                "spud date": 1.0,
                "rig release": 1.0,
                "total depth reached": 1.5,
            },
            "DDR": {
                "daily drilling report": 4.0,
                "ddr": 3.0,
                "24 hour operations": 3.0,
                "midnight depth": 2.5,
                "operations at 06:00": 2.5,
                "current operation": 2.0,
                "bha record": 1.5,
                "bit record": 1.5,
                "time breakdown": 1.5,
                "drilling parameters": 1.0,
                "pump pressure": 1.0,
            },
            "MUD_LOG": {
                "mud log": 4.0,
                "gas chromatography": 3.0,
                "total gas": 2.5,
                "chromatograph": 2.5,
                "shale density": 2.0,
                "calcimetry": 2.0,
                "c1": 1.5,
                "c2": 1.5,
                "c3": 1.5,
                "lag depth": 2.0,
                "cuttings description": 1.5,
                "lithological log": 1.5,
            },
            "DRILLING_REPORT": {
                "end of well report": 3.0,
                "drilling recap": 3.0,
                "drilling summary": 2.5,
                "bit performance": 2.0,
                "directional survey summary": 2.0,
                "hydraulics summary": 1.5,
                "npt breakdown": 2.0,
                "lost time report": 2.0,
            },
            "COMPLETION_REPORT": {
                "well completion summary": 3.5,
                "packer setting": 2.5,
                "tubing tally": 2.5,
                "stimulation report": 2.0,
                "frac report": 2.0,
                "flow test": 2.0,
                "xmas tree installation": 2.0,
            },
        }

    def classify(self, text: str, filename: str = "") -> Tuple[str, float]:
        """
        Classifies document text and filename into a document type and confidence score.
        Returns:
            (document_type: str, confidence: float)
        """
        text_lower = (text or "").lower()
        filename_lower = (filename or "").lower()

        # Filename strong heuristics
        if "wcr" in filename_lower or "well_completion" in filename_lower:
            return "WCR", 0.95
        if "ddr" in filename_lower or "daily_drilling" in filename_lower or "daily_report" in filename_lower:
            return "DDR", 0.95
        if "mud_log" in filename_lower or "mudlog" in filename_lower:
            return "MUD_LOG", 0.95
        if "completion" in filename_lower:
            return "COMPLETION_REPORT", 0.90
        if "drilling_report" in filename_lower:
            return "DRILLING_REPORT", 0.90

        # Text scoring
        scores: Dict[str, float] = {k: 0.0 for k in self.signatures}

        for doc_type, terms in self.signatures.items():
            for term, weight in terms.items():
                if term in text_lower:
                    occurrences = text_lower.count(term)
                    scores[doc_type] += weight * min(occurrences, 4)

        best_type = "OTHER"
        best_score = 0.0

        for doc_type, score in scores.items():
            if score > best_score:
                best_score = score
                best_type = doc_type

        if best_score < 4.0:
            return "OTHER", 0.40

        # Normalize confidence to [0.60, 0.98]
        confidence = min(0.98, 0.60 + (best_score / 30.0) * 0.38)
        return best_type, round(confidence, 2)


document_classifier = DocumentClassifier()
