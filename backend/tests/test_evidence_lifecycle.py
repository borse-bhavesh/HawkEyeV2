import pytest

from app.services.evidence.models import (
    Evidence, EvidenceType, EvidenceSource,
    FrameEvidence, VideoSegmentEvidence,
)
from app.services.evidence.lifecycle import (
    EvidenceLifecycleService,
    EvidenceValidationError,
)


# --------------- helpers ---------------

def _frame(ev_id="ev1", event_id="evt1", assessment_id="ass1"):
    return Evidence(
        evidence_id=ev_id,
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=0.5),
        event_id=event_id,
        assessment_id=assessment_id,
    )


def _segment(ev_id="ev2", event_id="evt2", assessment_id="ass2"):
    return Evidence(
        evidence_id=ev_id,
        evidence_type=EvidenceType.VIDEO_SEGMENT,
        source=EvidenceSource(source_id="cam2", source_type="file"),
        video_segment=VideoSegmentEvidence(
            start_frame_number=0, end_frame_number=30,
            start_timestamp_seconds=0.0, end_timestamp_seconds=1.0,
        ),
        event_id=event_id,
        assessment_id=assessment_id,
    )


@pytest.fixture
def svc():
    return EvidenceLifecycleService()


# --------------- valid evidence ---------------

def test_valid_frame_evidence(svc):
    ev = _frame()
    result = svc.validate(ev)
    assert result.evidence_id == "ev1"
    assert result.evidence_type == EvidenceType.FRAME


def test_valid_segment_evidence(svc):
    ev = _segment()
    result = svc.validate(ev)
    assert result.evidence_id == "ev2"
    assert result.evidence_type == EvidenceType.VIDEO_SEGMENT


def test_event_linked_evidence(svc):
    ev = _frame(event_id="evt1", assessment_id=None)
    object.__setattr__(ev, "assessment_id", None)
    # Re-create properly
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=0.5),
        event_id="evt1",
    )
    result = svc.validate(ev)
    assert result.event_id == "evt1"


def test_assessment_linked_evidence(svc):
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=0.5),
        assessment_id="ass1",
    )
    result = svc.validate(ev)
    assert result.assessment_id == "ass1"


def test_both_linked_evidence(svc):
    ev = _frame(event_id="evt1", assessment_id="ass1")
    result = svc.validate(ev)
    assert result.event_id == "evt1"
    assert result.assessment_id == "ass1"


# --------------- field preservation ---------------

def test_preserves_evidence_id(svc):
    ev = _frame()
    assert svc.validate(ev).evidence_id == ev.evidence_id


def test_preserves_source(svc):
    ev = _frame()
    result = svc.validate(ev)
    assert result.source.source_id == "cam1"
    assert result.source.source_type == "rtsp"


def test_preserves_frame_data(svc):
    ev = _frame()
    result = svc.validate(ev)
    assert result.frame.frame_number == 10
    assert result.frame.timestamp_seconds == 0.5


def test_preserves_segment_data(svc):
    ev = _segment()
    result = svc.validate(ev)
    assert result.video_segment.start_frame_number == 0
    assert result.video_segment.end_frame_number == 30


# --------------- invalid evidence ---------------

def test_rejects_none(svc):
    with pytest.raises(ValueError, match="evidence cannot be None"):
        svc.validate(None)


def test_rejects_tampered_missing_event_and_assessment(svc):
    ev = _frame()
    # Bypass pydantic to create an invalid state
    object.__setattr__(ev, "event_id", None)
    object.__setattr__(ev, "assessment_id", None)
    with pytest.raises(EvidenceValidationError):
        svc.validate(ev)


def test_rejects_tampered_frame_with_segment(svc):
    ev = _frame()
    object.__setattr__(ev, "video_segment", VideoSegmentEvidence(
        start_frame_number=0, end_frame_number=5,
        start_timestamp_seconds=0.0, end_timestamp_seconds=0.5,
    ))
    with pytest.raises(EvidenceValidationError):
        svc.validate(ev)


def test_rejects_tampered_empty_evidence_id(svc):
    ev = _frame()
    object.__setattr__(ev, "evidence_id", "")
    with pytest.raises(EvidenceValidationError):
        svc.validate(ev)


def test_rejects_tampered_missing_frame(svc):
    ev = _frame()
    object.__setattr__(ev, "frame", None)
    with pytest.raises(EvidenceValidationError):
        svc.validate(ev)


# --------------- immutability ---------------

def test_input_not_mutated(svc):
    ev = _frame()
    original = ev.model_dump()
    svc.validate(ev)
    assert ev.model_dump() == original


def test_validate_returns_separate_instance(svc):
    ev = _frame()
    result = svc.validate(ev)
    assert result is not ev


# --------------- validate_many ---------------

def test_validate_many_valid(svc):
    items = [_frame("a"), _segment("b")]
    results = svc.validate_many(items)
    assert len(results) == 2
    assert results[0].evidence_id == "a"
    assert results[1].evidence_id == "b"


def test_validate_many_empty(svc):
    assert svc.validate_many([]) == []


def test_validate_many_none_collection(svc):
    with pytest.raises(ValueError, match="collection cannot be None"):
        svc.validate_many(None)


def test_validate_many_preserves_order(svc):
    items = [_frame("c"), _frame("a"), _segment("b")]
    results = svc.validate_many(items)
    assert [r.evidence_id for r in results] == ["c", "a", "b"]


def test_validate_many_input_not_mutated(svc):
    items = [_frame(), _segment()]
    dumps_before = [e.model_dump() for e in items]
    svc.validate_many(items)
    assert [e.model_dump() for e in items] == dumps_before


def test_validate_many_stops_on_first_invalid(svc):
    good = _frame("ok")
    bad = _frame("bad")
    object.__setattr__(bad, "event_id", None)
    object.__setattr__(bad, "assessment_id", None)
    with pytest.raises(EvidenceValidationError):
        svc.validate_many([good, bad])


# --------------- determinism ---------------

def test_repeated_validation_deterministic(svc):
    ev = _frame()
    a = svc.validate(ev)
    b = svc.validate(ev)
    assert a.model_dump() == b.model_dump()


def test_repeated_validate_many_deterministic(svc):
    items = [_frame("x"), _segment("y")]
    a = svc.validate_many(items)
    b = svc.validate_many(items)
    assert [r.model_dump() for r in a] == [r.model_dump() for r in b]
