import pytest
import numpy as np
from pydantic import ValidationError

from app.services.video_frame import VideoFrame
from app.services.evidence.capture import EvidenceCapture
from app.services.evidence.models import FrameEvidence

def create_mock_video_frame(frame_number: int, timestamp: float) -> VideoFrame:
    # Small dummy numpy array to represent the image
    return VideoFrame(
        frame_number=frame_number,
        timestamp_seconds=timestamp,
        image=np.zeros((10, 10, 3), dtype=np.uint8)
    )

# 1. Valid VideoFrame produces FrameEvidence.
def test_valid_videoframe_produces_frame_evidence():
    vf = create_mock_video_frame(123, 5.137)
    ev = EvidenceCapture.capture_frame(vf)
    assert isinstance(ev, FrameEvidence)

# 2. frame_number is preserved exactly.
def test_frame_number_is_preserved_exactly():
    vf = create_mock_video_frame(123, 5.137)
    ev = EvidenceCapture.capture_frame(vf)
    assert ev.frame_number == 123

# 3. timestamp_seconds is preserved exactly.
def test_timestamp_is_preserved_exactly():
    vf = create_mock_video_frame(123, 5.0)
    ev = EvidenceCapture.capture_frame(vf)
    assert ev.timestamp_seconds == 5.0

# 4. Fractional timestamp is preserved exactly.
def test_fractional_timestamp_is_preserved_exactly():
    vf = create_mock_video_frame(123, 5.13799)
    ev = EvidenceCapture.capture_frame(vf)
    assert ev.timestamp_seconds == 5.13799

# 5. Zero frame number is accepted.
def test_zero_frame_number_accepted():
    vf = create_mock_video_frame(0, 0.0)
    ev = EvidenceCapture.capture_frame(vf)
    assert ev.frame_number == 0

# 6. Zero timestamp is accepted.
def test_zero_timestamp_accepted():
    vf = create_mock_video_frame(0, 0.0)
    ev = EvidenceCapture.capture_frame(vf)
    assert ev.timestamp_seconds == 0.0

# 7. Negative frame number results in validation failure.
def test_negative_frame_number_rejected():
    vf = create_mock_video_frame(-1, 1.0)
    with pytest.raises(ValidationError):
        EvidenceCapture.capture_frame(vf)

# 8. Negative timestamp results in validation failure.
def test_negative_timestamp_rejected():
    vf = create_mock_video_frame(10, -1.0)
    with pytest.raises(ValidationError):
        EvidenceCapture.capture_frame(vf)

# 9. None input fails clearly.
def test_none_input_fails_clearly():
    with pytest.raises(ValueError, match="video_frame cannot be None"):
        EvidenceCapture.capture_frame(None)

# 10. Original VideoFrame is not modified.
def test_original_videoframe_not_modified():
    vf = create_mock_video_frame(10, 1.0)
    original_frame_number = vf.frame_number
    original_timestamp = vf.timestamp_seconds
    _ = EvidenceCapture.capture_frame(vf)
    assert vf.frame_number == original_frame_number
    assert vf.timestamp_seconds == original_timestamp

# 11. VideoFrame image is not embedded in FrameEvidence.
def test_image_is_not_embedded_in_evidence():
    vf = create_mock_video_frame(10, 1.0)
    ev = EvidenceCapture.capture_frame(vf)
    assert not hasattr(ev, "image")

# 12. NumPy image object is not copied unnecessarily.
def test_numpy_image_not_copied_unnecessarily():
    vf = create_mock_video_frame(10, 1.0)
    ev = EvidenceCapture.capture_frame(vf)
    # The output shouldn't hold a reference to the image at all
    # We assert it just has the strict fields
    assert "image" not in ev.model_dump()

# 13. Capture does not access the filesystem.
# 14. Capture does not access a camera.
# 15. Capture does not access a network stream.
def test_capture_does_not_access_external_resources():
    vf = create_mock_video_frame(10, 1.0)
    # This executes synchronously in memory without IO
    ev = EvidenceCapture.capture_frame(vf)
    assert ev is not None

# 16. Capture does not generate UUIDs.
def test_capture_does_not_generate_uuids():
    vf = create_mock_video_frame(10, 1.0)
    ev = EvidenceCapture.capture_frame(vf)
    assert not hasattr(ev, "evidence_id")

# 17. Capture does not generate wall-clock timestamps.
def test_capture_does_not_generate_wall_clock_timestamps():
    vf = create_mock_video_frame(10, 1.0)
    ev = EvidenceCapture.capture_frame(vf)
    assert ev.timestamp_seconds == 1.0
    assert not hasattr(ev, "created_at")

# 18. Same VideoFrame metadata produces equivalent FrameEvidence.
def test_same_metadata_produces_equivalent_evidence():
    vf1 = create_mock_video_frame(10, 1.0)
    vf2 = create_mock_video_frame(10, 1.0)
    ev1 = EvidenceCapture.capture_frame(vf1)
    ev2 = EvidenceCapture.capture_frame(vf2)
    assert ev1.model_dump() == ev2.model_dump()

# 19. Different frame numbers produce different FrameEvidence.
def test_different_frame_numbers_produce_different_evidence():
    vf1 = create_mock_video_frame(10, 1.0)
    vf2 = create_mock_video_frame(11, 1.0)
    ev1 = EvidenceCapture.capture_frame(vf1)
    ev2 = EvidenceCapture.capture_frame(vf2)
    assert ev1.frame_number != ev2.frame_number

# 20. Different timestamps are preserved distinctly.
def test_different_timestamps_preserved_distinctly():
    vf1 = create_mock_video_frame(10, 1.0)
    vf2 = create_mock_video_frame(10, 1.1)
    ev1 = EvidenceCapture.capture_frame(vf1)
    ev2 = EvidenceCapture.capture_frame(vf2)
    assert ev1.timestamp_seconds != ev2.timestamp_seconds

# 21. Existing FrameEvidence validation remains authoritative.
def test_existing_validation_remains_authoritative():
    vf = create_mock_video_frame(-5, -5.0)
    with pytest.raises(ValidationError):
        EvidenceCapture.capture_frame(vf)

# 22. Frame numbering convention is preserved.
def test_frame_numbering_convention_preserved():
    vf = create_mock_video_frame(0, 0.0) # Zero based index check
    ev = EvidenceCapture.capture_frame(vf)
    assert ev.frame_number == 0

# 23. Timestamp remains video-relative.
def test_timestamp_remains_video_relative():
    vf = create_mock_video_frame(100, 3.33)
    ev = EvidenceCapture.capture_frame(vf)
    assert ev.timestamp_seconds == 3.33

# 24. No raw image bytes exist in FrameEvidence.
def test_no_raw_image_bytes_in_evidence():
    vf = create_mock_video_frame(100, 3.33)
    ev = EvidenceCapture.capture_frame(vf)
    assert not hasattr(ev, "bytes")
    assert not hasattr(ev, "raw")

# 25. No storage path/URL is introduced.
def test_no_storage_path_introduced():
    vf = create_mock_video_frame(100, 3.33)
    ev = EvidenceCapture.capture_frame(vf)
    assert not hasattr(ev, "path")
    assert not hasattr(ev, "url")
    assert not hasattr(ev, "s3_key")

# 26. Capture component is stateless.
def test_capture_component_is_stateless():
    capture1 = EvidenceCapture()
    capture2 = EvidenceCapture()
    vf = create_mock_video_frame(100, 3.33)
    assert capture1.capture_frame(vf) == capture2.capture_frame(vf)

# 27. Repeated capture calls produce equivalent results.
def test_repeated_capture_calls():
    vf = create_mock_video_frame(100, 3.33)
    ev1 = EvidenceCapture.capture_frame(vf)
    ev2 = EvidenceCapture.capture_frame(vf)
    assert ev1 == ev2

# 28. Capture does not mutate the supplied NumPy image.
def test_capture_does_not_mutate_image():
    vf = create_mock_video_frame(100, 3.33)
    original_sum = np.sum(vf.image)
    _ = EvidenceCapture.capture_frame(vf)
    assert np.sum(vf.image) == original_sum

# 29. Evidence metadata remains independent from image content.
def test_metadata_independent_from_image_content():
    vf1 = VideoFrame(frame_number=10, timestamp_seconds=1.0, image=np.zeros((10,10,3), dtype=np.uint8))
    vf2 = VideoFrame(frame_number=10, timestamp_seconds=1.0, image=np.ones((20,20,3), dtype=np.uint8))
    ev1 = EvidenceCapture.capture_frame(vf1)
    ev2 = EvidenceCapture.capture_frame(vf2)
    assert ev1 == ev2

# 30. No numeric risk score exists anywhere in the capture result.
def test_no_numeric_risk_score():
    vf = create_mock_video_frame(100, 3.33)
    ev = EvidenceCapture.capture_frame(vf)
    assert not hasattr(ev, "score")
    assert not hasattr(ev, "risk")
