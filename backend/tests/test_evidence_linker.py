import pytest
from copy import deepcopy

from app.services.evidence.models import (
    Evidence, EvidenceType, EvidenceSource,
    FrameEvidence, VideoSegmentEvidence,
)
from app.services.evidence.linker import EvidenceLinkingService


# --------------- helpers ---------------

def _frame_evidence(ev_id: str = "ev_1",
                    event_id: str = "evt_orig",
                    assessment_id: str = "ass_orig") -> Evidence:
    return Evidence(
        evidence_id=ev_id,
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=42, timestamp_seconds=1.4),
        event_id=event_id,
        assessment_id=assessment_id,
    )


def _segment_evidence(ev_id: str = "ev_2",
                      event_id: str = "evt_orig",
                      assessment_id: str = "ass_orig") -> Evidence:
    return Evidence(
        evidence_id=ev_id,
        evidence_type=EvidenceType.VIDEO_SEGMENT,
        source=EvidenceSource(source_id="cam2", source_type="file"),
        video_segment=VideoSegmentEvidence(
            start_frame_number=10, end_frame_number=20,
            start_timestamp_seconds=0.5, end_timestamp_seconds=1.0,
        ),
        event_id=event_id,
        assessment_id=assessment_id,
    )


@pytest.fixture
def svc():
    return EvidenceLinkingService()


# --------------- event linking ---------------

def test_link_event_only(svc):
    ev = _frame_evidence()
    linked = svc.link(ev, event_id="new_evt")
    assert linked.event_id == "new_evt"
    assert linked.assessment_id == "ass_orig"


def test_link_assessment_only(svc):
    ev = _frame_evidence()
    linked = svc.link(ev, assessment_id="new_ass")
    assert linked.assessment_id == "new_ass"
    assert linked.event_id == "evt_orig"


def test_link_both(svc):
    ev = _frame_evidence()
    linked = svc.link(ev, event_id="new_evt", assessment_id="new_ass")
    assert linked.event_id == "new_evt"
    assert linked.assessment_id == "new_ass"


# --------------- field preservation ---------------

def test_preserves_evidence_id(svc):
    ev = _frame_evidence()
    linked = svc.link(ev, event_id="x")
    assert linked.evidence_id == ev.evidence_id


def test_preserves_evidence_type(svc):
    ev = _frame_evidence()
    linked = svc.link(ev, event_id="x")
    assert linked.evidence_type == EvidenceType.FRAME


def test_preserves_source(svc):
    ev = _frame_evidence()
    linked = svc.link(ev, event_id="x")
    assert linked.source.source_id == "cam1"
    assert linked.source.source_type == "rtsp"


def test_preserves_frame_data(svc):
    ev = _frame_evidence()
    linked = svc.link(ev, event_id="x")
    assert linked.frame.frame_number == 42
    assert linked.frame.timestamp_seconds == 1.4


def test_preserves_segment_data(svc):
    ev = _segment_evidence()
    linked = svc.link(ev, event_id="x")
    assert linked.video_segment.start_frame_number == 10
    assert linked.video_segment.end_frame_number == 20
    assert linked.video_segment.start_timestamp_seconds == 0.5
    assert linked.video_segment.end_timestamp_seconds == 1.0


# --------------- immutability ---------------

def test_input_evidence_is_not_mutated(svc):
    ev = _frame_evidence()
    original_dump = ev.model_dump()
    svc.link(ev, event_id="changed_evt", assessment_id="changed_ass")
    assert ev.model_dump() == original_dump


def test_mutating_linked_does_not_affect_input(svc):
    ev = _frame_evidence()
    linked = svc.link(ev, event_id="new")
    linked.source.source_id = "hacked"
    assert ev.source.source_id == "cam1"


# --------------- rejection ---------------

def test_rejects_neither_event_nor_assessment(svc):
    ev = _frame_evidence()
    with pytest.raises(ValueError, match="At least one"):
        svc.link(ev)


def test_rejects_none_evidence(svc):
    with pytest.raises(ValueError, match="evidence cannot be None"):
        svc.link(None, event_id="x")


def test_rejects_empty_event_id(svc):
    ev = _frame_evidence()
    with pytest.raises(ValueError, match="event_id cannot be empty"):
        svc.link(ev, event_id="")


def test_rejects_whitespace_event_id(svc):
    ev = _frame_evidence()
    with pytest.raises(ValueError, match="event_id cannot be empty"):
        svc.link(ev, event_id="   ")


def test_rejects_empty_assessment_id(svc):
    ev = _frame_evidence()
    with pytest.raises(ValueError, match="assessment_id cannot be empty"):
        svc.link(ev, assessment_id="")


def test_rejects_whitespace_assessment_id(svc):
    ev = _frame_evidence()
    with pytest.raises(ValueError, match="assessment_id cannot be empty"):
        svc.link(ev, assessment_id="  \t ")


# --------------- determinism ---------------

def test_deterministic_repeated_linking(svc):
    ev = _frame_evidence()
    a = svc.link(ev, event_id="x", assessment_id="y")
    b = svc.link(ev, event_id="x", assessment_id="y")
    assert a.model_dump() == b.model_dump()


def test_link_returns_new_instance(svc):
    ev = _frame_evidence()
    linked = svc.link(ev, event_id="x")
    assert linked is not ev


# --------------- segment evidence ---------------

def test_segment_event_linking(svc):
    ev = _segment_evidence()
    linked = svc.link(ev, event_id="seg_evt")
    assert linked.event_id == "seg_evt"
    assert linked.evidence_type == EvidenceType.VIDEO_SEGMENT


def test_segment_assessment_linking(svc):
    ev = _segment_evidence()
    linked = svc.link(ev, assessment_id="seg_ass")
    assert linked.assessment_id == "seg_ass"
    assert linked.evidence_type == EvidenceType.VIDEO_SEGMENT
