"""
NWIS Phase 5 — Deterministic Multi-Factor Reranker
=================================================
Calculates structured retrieval ordering scores across semantic, stratigraphic,
depth, spatial, and operational hazard dimensions.

CRITICAL ARCHITECTURAL CONSTRAINTS:
- Deterministic and explainable component breakdown.
- Do NOT represent final_relevance as a scientifically calibrated probability.
- Clearly designated as a retrieval ordering and evidence prioritization score.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("nwis.reranker")


@dataclass
class RerankedItem:
    item: Dict[str, Any]
    semantic_score: float
    formation_score: float
    depth_score: float
    spatial_score: float
    event_score: float
    final_relevance: float

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.item)
        d["semantic_score"] = round(self.semantic_score, 3)
        d["formation_score"] = round(self.formation_score, 3)
        d["depth_score"] = round(self.depth_score, 3)
        d["spatial_score"] = round(self.spatial_score, 3)
        d["event_score"] = round(self.event_score, 3)
        d["final_relevance"] = round(self.final_relevance, 3)
        return d


class Reranker:
    """
    Deterministic domain-aware reranker for NWIS drilling intelligence evidence.
    Weights domain physics, stratigraphy, and spatial offset evidence alongside
    raw semantic vector similarity.
    """

    def __init__(
        self,
        weight_semantic: float = 0.35,
        weight_formation: float = 0.25,
        weight_depth: float = 0.20,
        weight_spatial: float = 0.15,
        weight_event: float = 0.05,
    ):
        self.w_sem = weight_semantic
        self.w_form = weight_formation
        self.w_depth = weight_depth
        self.w_spat = weight_spatial
        self.w_evt = weight_event

    def calculate_formation_score(
        self,
        candidate_formation: Optional[str],
        target_formation: Optional[str],
    ) -> float:
        """Evaluates stratigraphic alignment."""
        if not target_formation:
            return 0.5  # Neutral when no target formation specified
        if not candidate_formation or candidate_formation.lower() in ("unspecified", "unknown"):
            return 0.4  # Slightly penalized if candidate formation unspecified

        cf = candidate_formation.lower().strip()
        tf = target_formation.lower().strip()

        if cf == tf or tf in cf or cf in tf:
            return 1.0  # Exact or direct sub-interval match

        # Known regional geological groups / equivalents (e.g. Barail Group)
        if ("barail" in tf and "barail" in cf) or ("tipam" in tf and "tipam" in cf):
            return 0.95

        return 0.15  # Distinct formation

    def calculate_depth_score(
        self,
        candidate_depth_from: Optional[float],
        candidate_depth_to: Optional[float],
        candidate_depth_md: Optional[float],
        target_depth_md: Optional[float],
    ) -> float:
        """Evaluates measured depth proximity."""
        if target_depth_md is None:
            return 0.5  # Neutral when depth is omitted

        # Determine effective candidate depth
        cand_depth = candidate_depth_md
        if cand_depth is None and candidate_depth_from is not None:
            if candidate_depth_to is not None:
                cand_depth = (candidate_depth_from + candidate_depth_to) / 2.0
            else:
                cand_depth = candidate_depth_from

        if cand_depth is None:
            return 0.4  # Neutral-low when candidate has no depth recorded

        delta = abs(cand_depth - target_depth_md)
        if delta <= 50:
            return 1.0
        elif delta <= 150:
            return 0.85
        elif delta <= 300:
            return 0.65
        elif delta <= 500:
            return 0.45
        elif delta <= 800:
            return 0.25
        else:
            return 0.10

    def calculate_spatial_score(self, distance_km: Optional[float]) -> float:
        """Evaluates geographic proximity to active well."""
        if distance_km is None:
            return 0.5  # Neutral if offset distance not computed
        if distance_km == 0.0:
            return 1.0  # Same active well
        elif distance_km <= 5.0:
            return 0.90
        elif distance_km <= 15.0:
            return 0.75
        elif distance_km <= 30.0:
            return 0.55
        elif distance_km <= 50.0:
            return 0.35
        else:
            return 0.20

    def calculate_event_score(
        self,
        item_text: str,
        item_event_type: Optional[str],
        query: str,
    ) -> float:
        """Evaluates operational hazard topic alignment."""
        q_lower = query.lower()
        hazards = ["mud_loss", "lost circulation", "stuck_pipe", "pack off", "kick", "overpressure", "torque_spike"]
        detected_hazards = [h for h in hazards if h in q_lower]

        if not detected_hazards:
            return 0.5  # Generic query

        text_lower = (item_text + " " + (item_event_type or "")).lower()
        if any(h in text_lower for h in detected_hazards):
            return 1.0
        return 0.3

    def rerank(
        self,
        candidates: List[Tuple[Dict[str, Any], float]],
        target_well_id: Optional[str] = None,
        target_depth_md: Optional[float] = None,
        target_formation: Optional[str] = None,
        query: str = "",
    ) -> List[RerankedItem]:
        """
        Reranks vector search candidates using multi-factor domain weighting.
        """
        reranked = []
        for meta, raw_sim in candidates:
            # Bound semantic similarity to [0, 1]
            sem_score = max(0.0, min(1.0, float(raw_sim)))

            form_score = self.calculate_formation_score(
                candidate_formation=meta.get("formation"),
                target_formation=target_formation,
            )

            depth_score = self.calculate_depth_score(
                candidate_depth_from=meta.get("depth_from"),
                candidate_depth_to=meta.get("depth_to"),
                candidate_depth_md=meta.get("depth_md"),
                target_depth_md=target_depth_md,
            )

            dist_km = meta.get("distance_km")
            spat_score = self.calculate_spatial_score(dist_km)

            text_content = meta.get("text") or meta.get("excerpt") or ""
            evt_type = meta.get("event_type") or meta.get("event")
            evt_score = self.calculate_event_score(text_content, evt_type, query)

            final_rel = (
                self.w_sem * sem_score
                + self.w_form * form_score
                + self.w_depth * depth_score
                + self.w_spat * spat_score
                + self.w_evt * evt_score
            )

            reranked.append(
                RerankedItem(
                    item=meta,
                    semantic_score=sem_score,
                    formation_score=form_score,
                    depth_score=depth_score,
                    spatial_score=spat_score,
                    event_score=evt_score,
                    final_relevance=final_rel,
                )
            )

        # Sort by final relevance descending
        reranked.sort(key=lambda r: r.final_relevance, reverse=True)
        return reranked


# Global reranker instance
domain_reranker = Reranker()
