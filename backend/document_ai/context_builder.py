"""
NWIS Phase 5 — Context Builder & Evidence Packet Engine
======================================================
Constructs a deterministic, multi-source Evidence Packet for engineering decision support.
Unifies:
1. Active Well Registry & Spatial Offsets (Phase 2)
2. Historical Drilling Events & Hazard Taxonomy (Phase 2 & Phase 4)
3. Approved Technical Document Chunks (Phase 4 & Phase 5 Vector Index)
4. ML Multi-Hazard Risk Indicators (Phase 3 & Phase 3.1)

CRITICAL ARCHITECTURAL CONSTRAINTS:
- The Context Builder is 100% independent of LLMs and fully testable without network access.
- Every retrieved evidence piece is assigned a unique, immutable Evidence ID (e.g. EVID-001).
- Strictly isolates approved material: unapproved/rejected/draft chunks are excluded.
- Never fabricates evidence.
"""

from __future__ import annotations
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

from .document_repository import document_repository
from .embedding_provider import get_embedding_provider, EmbeddingProvider
from .vector_store import local_vector_store, VectorStore
from .reranker import domain_reranker, Reranker

logger = logging.getLogger("nwis.context_builder")


@dataclass
class TargetInterval:
    depth_from: Optional[float]
    depth_to: Optional[float]


@dataclass
class DocumentEvidence:
    evidence_id: str
    chunk_id: str
    document_id: str
    well_id: str
    page_number: int
    section: str
    formation: str
    depth_from: Optional[float]
    depth_to: Optional[float]
    depth_md: Optional[float]
    distance_km: Optional[float]
    excerpt: str
    retrieval_score: float
    component_scores: Dict[str, float]
    document_type: str = "WCR"
    event_type: Optional[str] = None
    approval_status: str = "APPROVED"


@dataclass
class EvidencePacket:
    active_well: str
    current_depth: Optional[float]
    target_interval: Dict[str, Optional[float]]
    formation: str
    nearby_wells: List[Dict[str, Any]]
    historical_events: List[Dict[str, Any]]
    document_evidence: List[Dict[str, Any]]
    risk_indicators: List[Dict[str, Any]]
    retrieval_mode: str
    query: str
    total_candidates: int
    filtered_candidates: int
    evidence_status: str  # EVIDENCE_SUPPORTED, PARTIALLY_SUPPORTED, INSUFFICIENT_EVIDENCE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContextBuilder:
    """
    Deterministic context engine that assembles verified drilling intelligence.
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        reranker: Optional[Reranker] = None,
    ):
        self._vector_store = vector_store or local_vector_store
        self._provider = embedding_provider
        self._reranker = reranker or domain_reranker

    def _get_provider(self) -> EmbeddingProvider:
        if self._provider is None:
            self._provider = get_embedding_provider()
        return self._provider

    def build_context(
        self,
        query: str,
        well_id: Optional[str] = "WELL-000050",
        depth_md: Optional[float] = None,
        formation: Optional[str] = None,
        radius_km: float = 25.0,
        max_evidence: int = 8,
    ) -> EvidencePacket:
        """
        Builds a comprehensive Evidence Packet for the query and operational coordinates.
        """
        from ..app.repositories.well_repository import well_repository
        from ..app.services.spatial_service import spatial_service, haversine_distance

        provider = self._get_provider()
        retrieval_mode = provider.mode

        # 1. Active Well & Spatial Offsets
        active_well_id = well_id or "UNSPECIFIED"
        active_coords = None
        nearby_wells_list: List[Dict[str, Any]] = []
        nearby_well_id_set: Set[str] = set()

        if well_id and well_id != "UNSPECIFIED":
            active_coords = well_repository.get_well_location(well_id)
            if active_coords:
                try:
                    nearby_resp = spatial_service.get_nearby_wells(well_id=well_id, radius_km=radius_km)
                    for nw in nearby_resp.nearby_wells:
                        nearby_wells_list.append({
                            "well_id": nw.well_id,
                            "well_name": nw.well_name,
                            "distance_km": round(nw.distance_km, 2),
                        })
                        nearby_well_id_set.add(nw.well_id)
                except Exception as e:
                    logger.warning(f"Spatial nearby lookup failed for {well_id}: {e}")
            nearby_well_id_set.add(well_id)

        # 2. Formation context
        resolved_formation = formation or "Unspecified"
        if resolved_formation == "Unspecified" and well_id and depth_md:
            # Query well formation if depth matches a recorded layer
            try:
                from ..app.services.formation_service import formation_service
                form_info = formation_service.get_formation_for_depth(well_id, depth_md)
                if form_info and form_info.formation_name:
                    resolved_formation = form_info.formation_name
            except Exception:
                pass

        # 3. Target Depth Interval (window of +/- 150m)
        target_interval = {
            "from": max(0.0, depth_md - 150.0) if depth_md is not None else None,
            "to": (depth_md + 150.0) if depth_md is not None else None,
        }

        # 4. Historical Events (approved institutional events and CSV records)
        import re
        q_lower = query.lower().strip()
        STOPWORDS = {
            "what", "which", "where", "when", "who", "how", "did", "does", "occurred",
            "occur", "happened", "is", "are", "was", "were", "in", "on", "at", "to",
            "for", "of", "with", "a", "an", "the", "and", "or", "near", "this", "well",
            "depth", "m", "md", "problems", "records",
        }
        query_keywords = [
            w for w in re.findall(r"\b[a-zA-Z0-9_\-]+\b", q_lower)
            if w not in STOPWORDS and len(w) > 2
        ]

        historical_events: List[Dict[str, Any]] = []
        approved_events = document_repository.get_approved_events()
        for evt in approved_events:
            evt_dist = None
            if active_coords and evt.well_id and evt.well_id != "UNMATCHED_WELL":
                wloc = well_repository.get_well_location(evt.well_id)
                if wloc:
                    evt_dist = round(haversine_distance(active_coords[0], active_coords[1], wloc[0], wloc[1]), 2)

            # Apply spatial radius if well_id specified
            if nearby_well_id_set and evt.well_id not in nearby_well_id_set and evt.well_id != "UNMATCHED_WELL":
                continue

            # Apply depth proximity if depth_md specified (+/- 400m)
            if depth_md is not None:
                if evt.depth_md is None or abs(evt.depth_md - depth_md) > 400:
                    continue

            # Apply query keyword alignment
            text_combo = f"{evt.event_type} {evt.raw_event_text} {evt.formation or ''}".lower()
            if query_keywords and not any(term in text_combo for term in query_keywords):
                continue

            historical_events.append({
                "event_id": evt.event_id,
                "document_id": evt.document_id,
                "well_id": evt.well_id,
                "event_type": evt.event_type,
                "depth_md": evt.depth_md,
                "formation": evt.formation or "Unspecified",
                "distance_km": evt_dist,
                "description": evt.raw_event_text,
                "confidence": evt.confidence,
                "page": evt.source_page,
            })

        # 5. Semantic Vector Retrieval & Metadata Filtering
        q_emb = provider.embed_text(query)

        # Metadata Predicate:
        # Strictly ensures chunk is APPROVED and matches spatial radius if active well has coordinates
        def metadata_predicate(meta: Dict[str, Any]) -> bool:
            # 1. Approval Gate Check
            if meta.get("approval_status") != "APPROVED" and not meta.get("is_approved"):
                return False
            if meta.get("well_id") == "UNMATCHED_WELL":
                return False

            # 2. Spatial Check
            w_id = meta.get("well_id")
            if nearby_well_id_set and w_id and w_id not in nearby_well_id_set:
                return False

            # 3. Depth check (when depth_md is specified, chunk must fall within +/- 400m)
            if depth_md is not None:
                d_from = meta.get("depth_from")
                d_to = meta.get("depth_to")
                d_val = meta.get("depth_md") or d_from
                if d_val is None or abs(d_val - depth_md) > 400:
                    return False

            return True

        # Initial candidates from vector store
        raw_candidates = self._vector_store.search(
            query_embedding=q_emb,
            top_k=30,
            predicate=metadata_predicate,
        )
        # Filter candidates by minimum semantic similarity (>= 0.12)
        raw_candidates = [(m, s) for m, s in raw_candidates if s >= 0.12]
        total_candidates_found = len(raw_candidates)

        # If local vector store has no entries or is not yet populated with approved chunks,
        # fallback to approved chunks in repository directly
        if not raw_candidates:
            appr_chunks = document_repository.get_approved_chunks()
            if appr_chunks:
                # Add distances to chunks
                chunk_dicts = []
                chunk_texts = []
                for chk in appr_chunks:
                    c_dict = {
                        "chunk_id": chk.chunk_id,
                        "document_id": chk.document_id,
                        "well_id": chk.well_id,
                        "page_number": chk.page_number,
                        "section": chk.section,
                        "formation": chk.formation,
                        "depth_from": chk.depth_from,
                        "depth_to": chk.depth_to,
                        "document_type": chk.document_type,
                        "text": chk.text,
                        "approval_status": "APPROVED",
                    }
                    if metadata_predicate(c_dict):
                        dist_km = None
                        if active_coords and chk.well_id and chk.well_id != "UNMATCHED_WELL":
                            wloc = well_repository.get_well_location(chk.well_id)
                            if wloc:
                                dist_km = round(haversine_distance(active_coords[0], active_coords[1], wloc[0], wloc[1]), 2)
                        c_dict["distance_km"] = dist_km
                        chunk_dicts.append(c_dict)
                        chunk_texts.append(f"{chk.section} | {chk.formation or ''} | {chk.text}")

                if chunk_dicts:
                    # Index in vector store incrementally
                    embs = provider.embed_batch(chunk_texts)
                    self._vector_store.add_chunks(chunk_dicts, embs)
                    raw_candidates = self._vector_store.search(
                        query_embedding=q_emb,
                        top_k=30,
                        predicate=metadata_predicate,
                    )
                    total_candidates_found = len(raw_candidates)

        # 6. Reranking
        # Compute distances for candidate chunks if not present
        prepared_candidates = []
        for meta, sim in raw_candidates:
            meta_copy = dict(meta)
            if "distance_km" not in meta_copy or meta_copy["distance_km"] is None:
                c_wid = meta_copy.get("well_id")
                if active_coords and c_wid and c_wid != "UNMATCHED_WELL":
                    wloc = well_repository.get_well_location(c_wid)
                    if wloc:
                        meta_copy["distance_km"] = round(haversine_distance(active_coords[0], active_coords[1], wloc[0], wloc[1]), 2)
            prepared_candidates.append((meta_copy, sim))

        reranked_items = self._reranker.rerank(
            candidates=prepared_candidates,
            target_well_id=active_well_id,
            target_depth_md=depth_md,
            target_formation=resolved_formation,
            query=query,
        )

        filtered_count = len(reranked_items)

        # 7. Assign Unique Evidence IDs (EVID-001, EVID-002, ...)
        document_evidence_list: List[Dict[str, Any]] = []
        for idx, r_item in enumerate(reranked_items[:max_evidence]):
            evid_id = f"EVID-{idx + 1:03d}"
            item = r_item.item
            doc_ev = DocumentEvidence(
                evidence_id=evid_id,
                chunk_id=item.get("chunk_id", f"chk-{idx}"),
                document_id=item.get("document_id", "DOC-UNKNOWN"),
                well_id=item.get("well_id", "UNKNOWN"),
                page_number=int(item.get("page_number", 1)),
                section=item.get("section", "DRILLING"),
                formation=item.get("formation") or "Unspecified",
                depth_from=item.get("depth_from"),
                depth_to=item.get("depth_to"),
                depth_md=item.get("depth_md") or item.get("depth_from"),
                distance_km=item.get("distance_km"),
                excerpt=item.get("text", "")[:350],
                retrieval_score=r_item.final_relevance,
                component_scores={
                    "semantic_score": round(r_item.semantic_score, 3),
                    "formation_score": round(r_item.formation_score, 3),
                    "depth_score": round(r_item.depth_score, 3),
                    "spatial_score": round(r_item.spatial_score, 3),
                    "event_score": round(r_item.event_score, 3),
                },
                document_type=item.get("document_type", "WCR"),
                event_type=item.get("event_type"),
                approval_status="APPROVED",
            )
            document_evidence_list.append(asdict(doc_ev))

        # 8. ML Multi-Hazard Risk Indicators (from Phase 3.1)
        risk_indicators_list: List[Dict[str, Any]] = []
        if active_well_id and depth_md is not None and active_well_id != "UNSPECIFIED":
            try:
                from ..ml.predict import RiskPredictor, CSVDataProvider
                predictor = RiskPredictor(CSVDataProvider())
                pred_res = predictor.predict(well_id=active_well_id, depth_md=depth_md)
                for h_name, h_val in pred_res.hazard_predictions.items():
                    prob = h_val.probability
                    # Note: explicitly labelled as 'model_risk_indicator', not calibrated probability
                    risk_indicators_list.append({
                        "hazard": h_name,
                        "model_risk_indicator": round(prob, 3),
                        "model_risk_indicator_pct": round(prob * 100.0, 1),
                        "algorithm": h_val.algorithm or "Random Forest",
                        "threshold": h_val.threshold,
                        "threshold_version": h_val.threshold_version,
                    })
            except Exception as e:
                logger.info(f"ML risk prediction lookup for context packet omitted: {e}")

        # 9. Evaluate Overall Evidence Status
        if len(document_evidence_list) == 0 and len(historical_events) == 0:
            evidence_status = "INSUFFICIENT_EVIDENCE"
        elif len(document_evidence_list) >= 2:
            evidence_status = "EVIDENCE_SUPPORTED"
        else:
            evidence_status = "PARTIALLY_SUPPORTED"

        packet = EvidencePacket(
            active_well=active_well_id,
            current_depth=depth_md,
            target_interval=target_interval,
            formation=resolved_formation,
            nearby_wells=nearby_wells_list,
            historical_events=historical_events[:10],
            document_evidence=document_evidence_list,
            risk_indicators=risk_indicators_list,
            retrieval_mode=retrieval_mode,
            query=query,
            total_candidates=total_candidates_found,
            filtered_candidates=filtered_count,
            evidence_status=evidence_status,
        )

        return packet


# Global context builder instance
context_builder = ContextBuilder()
