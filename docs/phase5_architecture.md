# NWIS Phase 5: Semantic RAG & Engineering Copilot Architecture

> **CRITICAL OPERATIONAL ADVISORY**  
> **NWIS is an advisory decision-support system, NOT an autonomous drilling system.**  
> All model risk indicators, historical offset correlations, and copilot syntheses are strictly informative decision aids requiring licensed human engineer review before any operational decisions are made.

---

## 1. Architectural Evolution

### Phase 4 Architecture: Document Ingestion & TF-IDF Retrieval
```
PDF Document
     ↓
PDF Text Extraction / OCR (PyMuPDF / pdfplumber / Tesseract OCR fallback)
     ↓
Layout + Section Detection (Regex + Heuristic Parsers)
     ↓
Rule-Based NLP & Domain Entity Extraction (Wells, Formations, Depths, Hazards)
     ↓
Event Extraction (Structured drilling event taxonomy)
     ↓
[MANDATORY APPROVAL GATE] (Engineer Review: DRAFT / REVIEW_REQUIRED / REJECTED / APPROVED)
     ↓
TF-IDF Keyword Similarity Retrieval
     ↓
Source-Grounded Evidence
```

### Phase 5 Architecture: Semantic RAG & Engineering Copilot
```
Approved Technical Document (WCR / DDR)
     ↓
Semantic Section-Aware Chunks (with page, well, depth interval, formation metadata)
     ↓
Embedding Provider Abstraction (Local sentence-transformers / External API / TF-IDF Fallback)
     ↓
Vector Store Abstraction (In-Memory / Local NumPy Cosine / Future pgvector)
     ↓
Metadata Filtering (Well ID, Radius, Depth Proximity Window, Formation, Approval Status)
     ↓
Semantic Vector Retrieval (Cosine Similarity)
     ↓
Multi-Factor Deterministic Reranker (Semantic + Stratigraphy + Depth + Spatial + Hazard bonuses)
     ↓
Context Builder (Active Well + Nearby Wells + Historical Events + Approved Documents + Phase 3.1 ML Risk Indicators)
     ↓
Evidence Packet (Traceable EVID-XXX Identifiers)
     ↓
Prompt Injection Quarantine (<untrusted_document_data> isolation)
     ↓
Engineering LLM Provider (External OpenAI-compatible / Local LLM / Deterministic Fallback)
     ↓
Citation Validator & Factual Claim Grounding
     ↓
Source-Cited Engineering Answer + Verified Evidence Cards + Model Risk Indicators
     ↓
Mandatory Human Engineer Review
```

---

## 2. Core Architectural Pillars

### A. Approval Gate Isolation
Only records with `approval_status == "APPROVED"` and `matched_well_id != "UNMATCHED_WELL"` can ever enter the semantic vector store, TF-IDF index, institutional memory, or Context Builder. `DRAFT`, `REVIEW_REQUIRED`, `REJECTED`, and `UNMATCHED_WELL` records are strictly quarantined from retrieval.

### B. Embedding & LLM Provider Abstractions
- **Embedding Provider**: Pluggable provider hierarchy:
  - `LocalEmbeddingProvider`: Discovers pre-installed local models (e.g., `BAAI/bge-small-en-v1.5`, `all-MiniLM-L6-v2`) without forcing internet downloads.
  - `ExternalEmbeddingProvider`: Dispatches to OpenAI/Azure embeddings if API credentials are configured.
  - `TFIDFFallbackProvider`: Scikit-learn based term-frequency vectorizer ensuring 100% offline, zero-credential operation.
  - Active mode is transparently exposed (`semantic` vs `tfidf_fallback`).
- **LLM Provider**:
  - `ExternalLLMProvider`: Calls secure API endpoints using environment-configured credentials.
  - `DeterministicFallbackProvider`: Produces structured, factual, retrieval-only synthesis without LLM hallucinations or fabricated text.

### C. Multi-Factor Deterministic Reranker
Retrieval relevance is computed deterministically across 5 engineering dimensions:
$$\text{Final Score} = S_{\text{semantic}} + B_{\text{formation}} + B_{\text{depth}} + B_{\text{spatial}} + B_{\text{hazard}}$$
- Formation match bonus: $+0.15$ if formations match exactly.
- Depth proximity bonus: Linear decay from $+0.10$ within $\pm 200\text{ m}$.
- Spatial proximity bonus: $+0.05$ for immediate offset wells ($< 15\text{ km}$).
- Hazard taxonomy bonus: $+0.10$ if matching active query risk domains.

### D. Strict Prompt-Injection Defense
Retrieved technical documents are treated as **untrusted data**. Document text is enclosed within strict `<untrusted_document_data>` XML containers. System prompts instruct the LLM that text within this container must be parsed exclusively as historical data and never executed as prompt instructions.

### E. Citation Validator & Evidence Traceability
Every retrieved excerpt receives a persistent `EVID-XXX` identifier. Before any synthesis is emitted:
1. All assertions are verified against `EVID-XXX` references in the evidence packet.
2. If citations fail or reference unapproved documents, the system flags the response as ungrounded and falls back to raw evidence display.
3. Unsupported outcome queries (e.g., "What will definitely happen at depth X?") are proactively flagged with `INSUFFICIENT_EVIDENCE` and decision-support disclaimers.

---

## 3. Confidence Model Separation

Confidence is strictly disaggregated into four non-interchangeable indicators:
1. **Extraction Confidence**: Confidence of the OCR / NLP parser in extracting tabular or unstructured entities ($0.0 - 1.0$).
2. **Retrieval Relevance**: Multi-factor reranking score reflecting stratigraphy, spatial distance, and depth overlap ($0.0 - 1.0$).
3. **Evidence Status**: Categorical grounding status:
   - `EVIDENCE_SUPPORTED`: High-relevance approved historical evidence directly corroborates query.
   - `PARTIALLY_SUPPORTED`: Moderate relevance or spatial/stratigraphic proxy evidence.
   - `INSUFFICIENT_EVIDENCE`: No approved evidence within specified depth window or radius.
   - `RETRIEVAL_ONLY`: Direct evidence retrieved, synthesis generated via deterministic fallback.
   - `LLM_UNAVAILABLE`: External generative service disabled or unreachable.
4. **Answer Confidence**: `SUPPORTED` vs `UNSUPPORTED`.
