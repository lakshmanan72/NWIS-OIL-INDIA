"""
NWIS Phase 4 — Test Document Extraction
=======================================
Verifies entity extraction, citation traceability, depth extraction accuracy,
absence of depth hallucination, and alignment with the unified hazard taxonomy.
"""

import pytest
from backend.document_ai.chunker import document_chunker
from backend.document_ai.entity_extractor import entity_extractor
from backend.document_ai.event_extractor import event_extractor
from backend.document_ai.document_repository import DocumentChunk


def test_entity_extraction_traceability():
    """Verifies entities are extracted with exact page, confidence, and source citations."""
    sample_text = (
        "WELL INFORMATION\n"
        "Well Name: KK-DW-17-1\n"
        "Well ID: WELL-000050\n"
        "Latitude: 13.525000\n"
        "Longitude: 72.556400\n"
        "Spud Date: 15/02/2020\n"
        "Total Depth: 3450.5 m\n"
        "Mud Weight: 1.25 sg\n"
        "ROP: 18.5 m/hr\n"
        "WOB: 22.0 tonne\n"
        "RPM: 120\n"
    )

    chunks = [
        DocumentChunk(
            chunk_id="CHK-T1",
            document_id="DOC-T1",
            well_id="WELL-000050",
            page_number=3,
            section="WELL INFORMATION",
            text=sample_text,
            document_type="WCR",
        )
    ]

    extractions = entity_extractor.extract_entities_from_chunks(chunks)

    ext_map = {e.field: e for e in extractions}

    # Verify well_id
    assert "well_id" in ext_map
    assert ext_map["well_id"].value == "WELL-000050"
    assert ext_map["well_id"].page_number == 3
    assert ext_map["well_id"].confidence >= 0.95
    assert "WELL-000050" in ext_map["well_id"].source_text

    # Verify total_depth
    assert "total_depth" in ext_map
    assert ext_map["total_depth"].value == 3450.5
    assert ext_map["total_depth"].unit == "m"

    # Verify coordinates
    assert ext_map["latitude"].value == 13.525
    assert ext_map["longitude"].value == 72.5564

    # Verify drilling parameters
    assert ext_map["mud_weight"].value == 1.25
    assert ext_map["rop"].value == 18.5
    assert ext_map["wob"].value == 22.0
    assert ext_map["rpm"].value == 120.0 or ext_map["rpm"].value == 120


def test_depth_aware_event_extraction():
    """Verifies depth-aware event extraction aligns with taxonomy and extracts exact MD."""
    text_with_depth = (
        "DRILLING EVENTS\n"
        "While drilling through the Barail formation, severe mud losses were observed at 3,185 m MD. "
        "Pumped 40 bbls of coarse LCM pill.\n"
        "Encountered high torque and drag at 2950 m indicating potential keyseating."
    )

    chunks = [
        DocumentChunk(
            chunk_id="CHK-T2",
            document_id="DOC-T2",
            well_id="WELL-000050",
            page_number=47,
            section="DRILLING EVENTS",
            text=text_with_depth,
            document_type="WCR",
            formation="Barail",
        )
    ]

    events = event_extractor.extract_events_from_chunks(chunks)
    assert len(events) >= 2

    # Check mud_loss
    mud_loss_evt = next((ev for ev in events if ev.event_type == "mud_loss"), None)
    assert mud_loss_evt is not None
    assert mud_loss_evt.depth_md == 3185.0
    assert mud_loss_evt.source_page == 47
    assert mud_loss_evt.formation == "Barail"
    assert "mud losses were observed at 3,185 m" in mud_loss_evt.raw_event_text.lower()

    # Check torque_spike
    torque_evt = next((ev for ev in events if ev.event_type == "torque_spike"), None)
    assert torque_evt is not None
    assert torque_evt.depth_md == 2950.0


def test_no_depth_hallucination_when_depth_absent():
    """Confirms that when depth is not mentioned in text or chunk, depth_md remains None."""
    text_no_depth = (
        "PROBLEMS\n"
        "Encountered unexpected gas influx and kick during connection. Flow check positive, shut in well."
    )

    chunks = [
        DocumentChunk(
            chunk_id="CHK-T3",
            document_id="DOC-T3",
            well_id="WELL-000050",
            page_number=12,
            section="PROBLEMS",
            text=text_no_depth,
            document_type="WCR",
            depth_from=None,
            depth_to=None,
        )
    ]

    events = event_extractor.extract_events_from_chunks(chunks)
    assert len(events) >= 1
    kick_evt = events[0]
    assert kick_evt.event_type == "kick"
    assert kick_evt.depth_md is None, "Depth was hallucinated when absent from text!"


def test_event_taxonomy_alignment():
    """Verifies that extracted events map strictly to canonical taxonomy categories."""
    valid_categories = {"mud_loss", "stuck_pipe", "kick", "overpressure", "torque_spike", "UNKNOWN"}

    test_scenarios = [
        ("Lost circulation occurred while drilling ahead.", "mud_loss"),
        ("Differential sticking immobilized drillstring.", "stuck_pipe"),
        ("Cuttings pack-off caused pipe stalling.", "stuck_pipe"),
        ("Gas kick observed with 15 bbl pit gain.", "kick"),
        ("Abnormal pressure zone encountered requiring weighted mud.", "overpressure"),
        ("Severe torque spike observed on top drive.", "torque_spike"),
    ]

    for snippet, expected_hazard in test_scenarios:
        chunks = [
            DocumentChunk(
                chunk_id="CHK-TEST",
                document_id="DOC-TEST",
                well_id="WELL-000001",
                page_number=1,
                section="DRILLING EVENTS",
                text=snippet,
                document_type="DDR",
            )
        ]
        evts = event_extractor.extract_events_from_chunks(chunks)
        assert len(evts) >= 1, f"Failed to detect event in: '{snippet}'"
        assert evts[0].event_type == expected_hazard
        assert evts[0].event_type in valid_categories
