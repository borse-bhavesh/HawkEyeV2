import pytest

from app.services.evidence.models import (
    Evidence, EvidenceType, EvidenceSource,
    FrameEvidence, VideoSegmentEvidence,
)
from app.services.evidence.query import EvidenceQueryService


# --------------- helpers ---------------

def _frame(ev_id, source_id="cam1", source_type="rtsp",
           event_id="evt1", assessment_id="ass1"):
    return Evidence(
        evidence_id=ev_id,
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id=source_id, source_type=source_type),
        frame=FrameEvidence(frame_number=1, timestamp_seconds=0.5),
        event_id=event_id,
        assessment_id=assessment_id,
    )


def _segment(ev_id, source_id="cam2", source_type="file",
             event_id="evt2", assessment_id="ass2"):
    return Evidence(
        evidence_id=ev_id,
        evidence_type=EvidenceType.VIDEO_SEGMENT,
        source=EvidenceSource(source_id=source_id, source_type=source_type),
        video_segment=VideoSegmentEvidence(
            start_frame_number=0, end_frame_number=10,
            start_timestamp_seconds=0.0, end_timestamp_seconds=1.0,
        ),
        event_id=event_id,
        assessment_id=assessment_id,
    )


@pytest.fixture
def svc():
    return EvidenceQueryService()


@pytest.fixture
def mixed():
    return [
        _frame("f1", source_id="cam1", source_type="rtsp", event_id="evt1", assessment_id="ass1"),
        _segment("s1", source_id="cam2", source_type="file", event_id="evt2", assessment_id="ass2"),
        _frame("f2", source_id="cam1", source_type="rtsp", event_id="evt1", assessment_id="ass2"),
        _segment("s2", source_id="cam3", source_type="rtsp", event_id="evt3", assessment_id="ass1"),
    ]


# --------------- no filters ---------------

def test_no_filters_returns_all(svc, mixed):
    result = svc.query(mixed)
    assert len(result) == 4


def test_no_filters_preserves_order(svc, mixed):
    result = svc.query(mixed)
    assert [e.evidence_id for e in result] == ["f1", "s1", "f2", "s2"]


# --------------- evidence_type ---------------

def test_filter_by_frame_type(svc, mixed):
    result = svc.query(mixed, evidence_type=EvidenceType.FRAME)
    assert all(e.evidence_type == EvidenceType.FRAME for e in result)
    assert len(result) == 2


def test_filter_by_segment_type(svc, mixed):
    result = svc.query(mixed, evidence_type=EvidenceType.VIDEO_SEGMENT)
    assert all(e.evidence_type == EvidenceType.VIDEO_SEGMENT for e in result)
    assert len(result) == 2


# --------------- source_id ---------------

def test_filter_by_source_id(svc, mixed):
    result = svc.query(mixed, source_id="cam1")
    assert [e.evidence_id for e in result] == ["f1", "f2"]


def test_filter_by_source_id_no_match(svc, mixed):
    result = svc.query(mixed, source_id="cam99")
    assert result == []


# --------------- source_type ---------------

def test_filter_by_source_type(svc, mixed):
    result = svc.query(mixed, source_type="file")
    assert len(result) == 1
    assert result[0].evidence_id == "s1"


# --------------- event_id ---------------

def test_filter_by_event_id(svc, mixed):
    result = svc.query(mixed, event_id="evt1")
    assert [e.evidence_id for e in result] == ["f1", "f2"]


# --------------- assessment_id ---------------

def test_filter_by_assessment_id(svc, mixed):
    result = svc.query(mixed, assessment_id="ass1")
    assert [e.evidence_id for e in result] == ["f1", "s2"]


# --------------- AND semantics ---------------

def test_two_filters_and(svc, mixed):
    result = svc.query(mixed, evidence_type=EvidenceType.FRAME, event_id="evt1")
    assert [e.evidence_id for e in result] == ["f1", "f2"]


def test_three_filters_and(svc, mixed):
    result = svc.query(mixed, evidence_type=EvidenceType.FRAME, source_id="cam1", assessment_id="ass2")
    assert [e.evidence_id for e in result] == ["f2"]


def test_all_filters_no_match(svc, mixed):
    result = svc.query(mixed, evidence_type=EvidenceType.FRAME, source_id="cam2")
    assert result == []


# --------------- empty input ---------------

def test_empty_input_returns_empty(svc):
    assert svc.query([]) == []


# --------------- event-only / assessment-only evidence ---------------

def test_event_only_evidence(svc):
    ev = _frame("f1", event_id="evt1", assessment_id=None)
    # evidence model requires at least one, so use object override
    object.__setattr__(ev, "assessment_id", None)
    result = svc.query([ev], event_id="evt1")
    assert len(result) == 1


def test_assessment_only_evidence(svc):
    ev = _frame("f1", event_id=None, assessment_id="ass1")
    object.__setattr__(ev, "event_id", None)
    result = svc.query([ev], assessment_id="ass1")
    assert len(result) == 1


def test_assessment_filter_excludes_event_only(svc):
    ev = _frame("f1", event_id="evt1", assessment_id=None)
    object.__setattr__(ev, "assessment_id", None)
    result = svc.query([ev], assessment_id="ass1")
    assert result == []


# --------------- immutability ---------------

def test_input_list_not_mutated(svc, mixed):
    original_len = len(mixed)
    svc.query(mixed, evidence_type=EvidenceType.FRAME)
    assert len(mixed) == original_len


def test_evidence_objects_not_mutated(svc, mixed):
    dumps_before = [e.model_dump() for e in mixed]
    svc.query(mixed, source_id="cam1")
    dumps_after = [e.model_dump() for e in mixed]
    assert dumps_before == dumps_after


# --------------- invalid/blank filters ---------------

def test_none_collection_rejected(svc):
    with pytest.raises(ValueError, match="collection cannot be None"):
        svc.query(None)


def test_blank_source_id_rejected(svc):
    with pytest.raises(ValueError, match="source_id"):
        svc.query([], source_id="")


def test_whitespace_source_id_rejected(svc):
    with pytest.raises(ValueError, match="source_id"):
        svc.query([], source_id="   ")


def test_blank_source_type_rejected(svc):
    with pytest.raises(ValueError, match="source_type"):
        svc.query([], source_type="")


def test_blank_event_id_rejected(svc):
    with pytest.raises(ValueError, match="event_id"):
        svc.query([], event_id="")


def test_blank_assessment_id_rejected(svc):
    with pytest.raises(ValueError, match="assessment_id"):
        svc.query([], assessment_id="")


# --------------- determinism ---------------

def test_repeated_query_identical(svc, mixed):
    a = svc.query(mixed, evidence_type=EvidenceType.FRAME)
    b = svc.query(mixed, evidence_type=EvidenceType.FRAME)
    assert [e.evidence_id for e in a] == [e.evidence_id for e in b]


# --------------- both links ---------------

def test_evidence_with_both_links_matched_by_event(svc, mixed):
    result = svc.query(mixed, event_id="evt1")
    assert all(e.event_id == "evt1" for e in result)


def test_evidence_with_both_links_matched_by_assessment(svc, mixed):
    result = svc.query(mixed, assessment_id="ass2")
    assert [e.evidence_id for e in result] == ["s1", "f2"]
