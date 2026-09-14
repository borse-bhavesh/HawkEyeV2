import pytest
from pydantic import ValidationError

from app.services.evidence.models import (
    EvidenceType,
    EvidenceSource,
    FrameEvidence,
    VideoSegmentEvidence,
    Evidence
)

# 1. EvidenceType contains exactly FRAME and VIDEO_SEGMENT.
def test_evidence_type_exact_values():
    values = set(item.value for item in EvidenceType)
    assert values == {"FRAME", "VIDEO_SEGMENT"}

# 2. Valid EvidenceSource construction.
def test_valid_evidence_source_construction():
    source = EvidenceSource(source_id="cam1", source_type="rtsp")
    assert source.source_id == "cam1"
    assert source.source_type == "rtsp"

# 3. Empty source_id rejected.
def test_empty_source_id_rejected():
    with pytest.raises(ValidationError):
        EvidenceSource(source_id="", source_type="rtsp")

# 4. Empty source_type rejected.
def test_empty_source_type_rejected():
    with pytest.raises(ValidationError):
        EvidenceSource(source_id="cam1", source_type="")

# 5. Valid FrameEvidence.
def test_valid_frame_evidence():
    frame = FrameEvidence(frame_number=10, timestamp_seconds=1.5)
    assert frame.frame_number == 10
    assert frame.timestamp_seconds == 1.5

# 6. Negative frame_number rejected.
def test_negative_frame_number_rejected():
    with pytest.raises(ValidationError):
        FrameEvidence(frame_number=-1, timestamp_seconds=1.5)

# 7. Negative timestamp rejected.
def test_negative_timestamp_rejected():
    with pytest.raises(ValidationError):
        FrameEvidence(frame_number=10, timestamp_seconds=-1.5)

# 8. Valid VideoSegmentEvidence.
def test_valid_video_segment_evidence():
    segment = VideoSegmentEvidence(
        start_frame_number=10,
        end_frame_number=20,
        start_timestamp_seconds=1.5,
        end_timestamp_seconds=3.0
    )
    assert segment.start_frame_number == 10
    assert segment.end_frame_number == 20

# 9. Negative start frame rejected.
def test_negative_start_frame_rejected():
    with pytest.raises(ValidationError):
        VideoSegmentEvidence(start_frame_number=-1, end_frame_number=10, start_timestamp_seconds=0.0, end_timestamp_seconds=1.0)

# 10. Negative end frame rejected.
def test_negative_end_frame_rejected():
    with pytest.raises(ValidationError):
        VideoSegmentEvidence(start_frame_number=10, end_frame_number=-1, start_timestamp_seconds=0.0, end_timestamp_seconds=1.0)

# 11. Negative start timestamp rejected.
def test_negative_start_timestamp_rejected():
    with pytest.raises(ValidationError):
        VideoSegmentEvidence(start_frame_number=0, end_frame_number=10, start_timestamp_seconds=-1.0, end_timestamp_seconds=1.0)

# 12. Negative end timestamp rejected.
def test_negative_end_timestamp_rejected():
    with pytest.raises(ValidationError):
        VideoSegmentEvidence(start_frame_number=0, end_frame_number=10, start_timestamp_seconds=0.0, end_timestamp_seconds=-1.0)

# 13. End frame before start frame rejected.
def test_end_frame_before_start_frame_rejected():
    with pytest.raises(ValidationError):
        VideoSegmentEvidence(start_frame_number=20, end_frame_number=10, start_timestamp_seconds=0.0, end_timestamp_seconds=1.0)

# 14. End timestamp before start timestamp rejected.
def test_end_timestamp_before_start_timestamp_rejected():
    with pytest.raises(ValidationError):
        VideoSegmentEvidence(start_frame_number=0, end_frame_number=10, start_timestamp_seconds=2.0, end_timestamp_seconds=1.0)

# 15. Valid FRAME Evidence.
def test_valid_frame_evidence_model():
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        event_id="evt1"
    )
    assert ev.evidence_id == "ev1"

# 16. Valid VIDEO_SEGMENT Evidence.
def test_valid_video_segment_evidence_model():
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.VIDEO_SEGMENT,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        video_segment=VideoSegmentEvidence(start_frame_number=10, end_frame_number=20, start_timestamp_seconds=1.5, end_timestamp_seconds=3.0),
        event_id="evt1"
    )
    assert ev.evidence_id == "ev1"

# 17. FRAME requires frame.
def test_frame_requires_frame():
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="ev1",
            evidence_type=EvidenceType.FRAME,
            source=EvidenceSource(source_id="cam1", source_type="rtsp"),
            event_id="evt1"
        )

# 18. FRAME rejects video_segment.
def test_frame_rejects_video_segment():
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="ev1",
            evidence_type=EvidenceType.FRAME,
            source=EvidenceSource(source_id="cam1", source_type="rtsp"),
            frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
            video_segment=VideoSegmentEvidence(start_frame_number=10, end_frame_number=20, start_timestamp_seconds=1.5, end_timestamp_seconds=3.0),
            event_id="evt1"
        )

# 19. VIDEO_SEGMENT requires video_segment.
def test_video_segment_requires_video_segment():
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="ev1",
            evidence_type=EvidenceType.VIDEO_SEGMENT,
            source=EvidenceSource(source_id="cam1", source_type="rtsp"),
            event_id="evt1"
        )

# 20. VIDEO_SEGMENT rejects frame.
def test_video_segment_rejects_frame():
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="ev1",
            evidence_type=EvidenceType.VIDEO_SEGMENT,
            source=EvidenceSource(source_id="cam1", source_type="rtsp"),
            frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
            video_segment=VideoSegmentEvidence(start_frame_number=10, end_frame_number=20, start_timestamp_seconds=1.5, end_timestamp_seconds=3.0),
            event_id="evt1"
        )

# 21. evidence_id cannot be empty.
def test_evidence_id_cannot_be_empty():
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="",
            evidence_type=EvidenceType.FRAME,
            source=EvidenceSource(source_id="cam1", source_type="rtsp"),
            frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
            event_id="evt1"
        )

# 22. source is mandatory.
def test_source_is_mandatory():
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="ev1",
            evidence_type=EvidenceType.FRAME,
            frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
            event_id="evt1"
        )

# 23. At least event_id or assessment_id must be present.
def test_at_least_event_id_or_assessment_id_must_be_present():
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="ev1",
            evidence_type=EvidenceType.FRAME,
            source=EvidenceSource(source_id="cam1", source_type="rtsp"),
            frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5)
        )

# 24. event_id-only Evidence is valid.
def test_event_id_only_evidence_is_valid():
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        event_id="evt1"
    )
    assert ev.event_id == "evt1"
    assert ev.assessment_id is None

# 25. assessment_id-only Evidence is valid.
def test_assessment_id_only_evidence_is_valid():
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        assessment_id="ass1"
    )
    assert ev.assessment_id == "ass1"
    assert ev.event_id is None

# 26. Both event_id and assessment_id are valid.
def test_both_event_id_and_assessment_id_are_valid():
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        event_id="evt1",
        assessment_id="ass1"
    )
    assert ev.event_id == "evt1"
    assert ev.assessment_id == "ass1"

# 27. Empty event_id does not satisfy reference requirement.
def test_empty_event_id_does_not_satisfy_reference_requirement():
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="ev1",
            evidence_type=EvidenceType.FRAME,
            source=EvidenceSource(source_id="cam1", source_type="rtsp"),
            frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
            event_id=""
        )

# 28. Empty assessment_id does not satisfy reference requirement.
def test_empty_assessment_id_does_not_satisfy_reference_requirement():
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="ev1",
            evidence_type=EvidenceType.FRAME,
            source=EvidenceSource(source_id="cam1", source_type="rtsp"),
            frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
            assessment_id=""
        )

# 29. event_id is preserved.
def test_event_id_is_preserved():
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        event_id="evt1"
    )
    assert ev.event_id == "evt1"

# 30. assessment_id is preserved.
def test_assessment_id_is_preserved():
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        assessment_id="ass1"
    )
    assert ev.assessment_id == "ass1"

# 31. evidence_id is preserved.
def test_evidence_id_is_preserved():
    ev = Evidence(
        evidence_id="ev_preserved_123",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        event_id="evt1"
    )
    assert ev.evidence_id == "ev_preserved_123"

# 32. source identity is preserved.
def test_source_identity_is_preserved():
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam_identity", source_type="rtsp_identity"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        event_id="evt1"
    )
    assert ev.source.source_id == "cam_identity"
    assert ev.source.source_type == "rtsp_identity"

# 33. Frame timestamp is video-relative.
def test_frame_timestamp_is_video_relative():
    ev = FrameEvidence(frame_number=10, timestamp_seconds=42.5)
    assert isinstance(ev.timestamp_seconds, float)
    assert ev.timestamp_seconds == 42.5

# 34. Frame number is non-negative.
def test_frame_number_is_non_negative():
    ev = FrameEvidence(frame_number=0, timestamp_seconds=0.0)
    assert ev.frame_number == 0

# 35. Segment frame ordering is enforced.
def test_segment_frame_ordering_is_enforced():
    with pytest.raises(ValidationError):
        VideoSegmentEvidence(start_frame_number=10, end_frame_number=9, start_timestamp_seconds=1.0, end_timestamp_seconds=2.0)

# 36. Segment timestamp ordering is enforced.
def test_segment_timestamp_ordering_is_enforced():
    with pytest.raises(ValidationError):
        VideoSegmentEvidence(start_frame_number=1, end_frame_number=2, start_timestamp_seconds=2.0, end_timestamp_seconds=1.0)

# 37. Evidence does not contain raw image arrays.
def test_evidence_does_not_contain_raw_image_arrays():
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        event_id="evt1"
    )
    assert not hasattr(ev, "image")
    assert not hasattr(ev.frame, "image")

# 38. Evidence does not contain raw video data.
def test_evidence_does_not_contain_raw_video_data():
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.VIDEO_SEGMENT,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        video_segment=VideoSegmentEvidence(start_frame_number=1, end_frame_number=2, start_timestamp_seconds=1.0, end_timestamp_seconds=2.0),
        event_id="evt1"
    )
    assert not hasattr(ev, "video")
    assert not hasattr(ev.video_segment, "video")

# 39. Evidence does not require filesystem existence.
def test_evidence_does_not_require_filesystem_existence():
    ev = Evidence(
        evidence_id="virtual_ev",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="virtual_cam", source_type="virtual"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        event_id="virtual_evt"
    )
    assert ev.evidence_id == "virtual_ev"

# 40. Evidence does not require URL/path storage.
def test_evidence_does_not_require_url_path_storage():
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        event_id="evt1"
    )
    assert not hasattr(ev, "url")
    assert not hasattr(ev, "path")

# 41. Evidence does not contain Event objects.
def test_evidence_does_not_contain_event_objects():
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        event_id="evt1"
    )
    assert ev.event_id == "evt1"
    assert not hasattr(ev, "event")

# 42. Evidence does not contain RiskAssessment objects.
def test_evidence_does_not_contain_risk_assessment_objects():
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        assessment_id="ass1"
    )
    assert ev.assessment_id == "ass1"
    assert not hasattr(ev, "assessment")

# 43. No numeric risk score field exists.
def test_no_numeric_risk_score_field_exists():
    ev = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        assessment_id="ass1"
    )
    assert not hasattr(ev, "score")
    assert not hasattr(ev, "risk_score")

# 44. Model construction is deterministic.
def test_model_construction_is_deterministic():
    ev1 = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        assessment_id="ass1"
    )
    ev2 = Evidence(
        evidence_id="ev1",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=10, timestamp_seconds=1.5),
        assessment_id="ass1"
    )
    assert ev1.model_dump() == ev2.model_dump()
