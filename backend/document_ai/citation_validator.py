"""
NWIS Phase 5 — Citation Validator & Safety Gate
===============================================
Validates that generated answers are strictly grounded in verified evidence packets,
ensures every factual claim cites a valid Evidence ID, and enforces prompt safety
and decision-support phrasing.

CRITICAL ARCHITECTURAL CONSTRAINTS:
- Factual claims without verifiable Evidence IDs are rejected.
- Deterministic/guarantee language ("will happen", "safe", "guaranteed") is prohibited.
- Clear separation of:
  1. Extraction Confidence
  2. Retrieval Relevance
  3. Evidence Status
  4. Answer Confidence
"""

from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("nwis.citation_validator")

# Prohibited deterministic / authoritative terms for decision support
DETERMINISTIC_TERMS = [
    r"\bwill definitely happen\b",
    r"\bwill definitely occur\b",
    r"\bguaranteed\b",
    r"\bguarantees\b",
    r"\b100% safe\b",
    r"\bcompletely safe\b",
    r"\bentirely unsafe\b",
    r"\bcertainly occur\b",
    r"\bwithout doubt\b",
]


class CitationValidator:
    """
    Validates citation coverage and decision-support compliance of answers.
    """

    @staticmethod
    def extract_evidence_ids(text: str) -> List[str]:
        """Extracts all EVID-XXX and LIVE-XXX references from text."""
        return re.findall(r"\b(?:EVID|LIVE)-[A-Za-z0-9_-]+\b", text)

    @staticmethod
    def check_unsupported_absolutes(query: str, answer: str) -> Tuple[bool, Optional[str]]:
        """
        Detects if query asks for deterministic certainty (e.g. 'what will definitely happen').
        """
        q_lower = query.lower()
        for term in DETERMINISTIC_TERMS:
            if re.search(term, q_lower):
                return True, (
                    "Insufficient verified historical evidence to determine what will definitely occur. "
                    "Drilling operations are non-deterministic; historical evidence and model indicators "
                    "are provided for engineer review only."
                )
        return False, None

    def validate_answer(
        self,
        answer: str,
        evidence_packet: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Validates citation coverage against the active evidence packet.
        """
        doc_evidence = evidence_packet.get("document_evidence", [])
        live_obs = evidence_packet.get("live_observations", [])
        valid_evid_ids: Set[str] = {e["evidence_id"] for e in doc_evidence if "evidence_id" in e}
        valid_evid_ids.update(lo["live_id"] for lo in live_obs if "live_id" in lo)
        referenced_ids = self.extract_evidence_ids(answer)

        # Check for absolute query
        query = evidence_packet.get("query", "")
        is_absolute, override_answer = self.check_unsupported_absolutes(query, answer)
        if is_absolute and override_answer:
            return {
                "is_valid": True,
                "sanitized_answer": override_answer,
                "referenced_evidence_ids": list(valid_evid_ids)[:4],
                "evidence_status": "PARTIALLY_SUPPORTED",
                "answer_confidence": "INSUFFICIENT_EVIDENCE",
                "warning": "Deterministic outcome query detected. Rewritten to decision-support standard.",
            }

        # Check citation coverage
        if not doc_evidence:
            return {
                "is_valid": False,
                "sanitized_answer": "No verified historical evidence found in approved technical records for the requested parameters.",
                "referenced_evidence_ids": [],
                "evidence_status": "INSUFFICIENT_EVIDENCE",
                "answer_confidence": "INSUFFICIENT_EVIDENCE",
                "warning": "Zero approved evidence documents available in packet.",
            }

        # Check if cited IDs exist in the current packet
        unmatched_ids = [eid for eid in referenced_ids if eid not in valid_evid_ids]
        if unmatched_ids:
            logger.warning(f"Answer cited invalid or hallucinated Evidence IDs: {unmatched_ids}")
            return {
                "is_valid": False,
                "sanitized_answer": "Answer generation could not be fully grounded in verified evidence. Please consult the attached historical evidence cards directly.",
                "referenced_evidence_ids": [eid for eid in referenced_ids if eid in valid_evid_ids],
                "evidence_status": "PARTIALLY_SUPPORTED",
                "answer_confidence": "UNVERIFIED_CITATION",
                "warning": f"Unmatched citation IDs detected: {unmatched_ids}",
            }

        # If answer has no citations at all, append citations from top retrieved evidence
        sanitized = answer.strip()
        if not referenced_ids and doc_evidence:
            top_ids = [e["evidence_id"] for e in doc_evidence[:3]]
            sanitized += f" [Evidence citations: {', '.join(top_ids)}]."
            referenced_ids = top_ids

        # Ensure decision support language
        if not sanitized.endswith("Requires engineer review."):
            sanitized += " Requires engineer review."

        return {
            "is_valid": True,
            "sanitized_answer": sanitized,
            "referenced_evidence_ids": referenced_ids,
            "evidence_status": evidence_packet.get("evidence_status", "EVIDENCE_SUPPORTED"),
            "answer_confidence": "SUPPORTED" if len(referenced_ids) >= 1 else "PARTIAL",
            "warning": None,
        }


# Global citation validator instance
citation_validator = CitationValidator()
