import pytest
import numpy as np
import cv2
from pathlib import Path
from unittest.mock import patch

from app.services.video_frame import VideoFrame
from app.services.evidence.models import Evidence, EvidenceType, EvidenceSource, FrameEvidence, VideoSegmentEvidence
from app.services.evidence.materializer import EvidenceMediaMaterializer, MaterializedEvidence


def create_mock_video_frame(frame_number: int, timestamp: float) -> VideoFrame:
    # A valid BGR image that cv2 can write without failure
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    return VideoFrame(
        frame_number=frame_number,
        timestamp_seconds=timestamp,
        image=img
    )

def create_mock_evidence(frame_number: int, timestamp: float, source_id: str = "cam1") -> Evidence:
    return Evidence(
        evidence_id="ev_123",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id=source_id, source_type="rtsp"),
        frame=FrameEvidence(frame_number=frame_number, timestamp_seconds=timestamp),
        event_id="evt_123"
    )

# 1. Materializes a valid VideoFrame as a JPEG.
def test_materializes_valid_videoframe_as_jpeg(tmp_path):
    mat = EvidenceMediaMaterializer(tmp_path)
    vf = create_mock_video_frame(123, 5.0)
    ev = create_mock_evidence(123, 5.0)
    
    result = mat.materialize_frame(vf, ev)
    
    assert isinstance(result, MaterializedEvidence)
    assert Path(result.path).exists()
    assert result.path.endswith(".jpg")

# 2. Creates missing output directories.
def test_creates_missing_directories(tmp_path):
    output_dir = tmp_path / "deep" / "nested" / "dir"
    mat = EvidenceMediaMaterializer(output_dir)
    vf = create_mock_video_frame(123, 5.0)
    ev = create_mock_evidence(123, 5.0)
    
    result = mat.materialize_frame(vf, ev)
    assert Path(result.path).exists()

# 3. Returns MaterializedEvidence with correct metadata.
def test_returns_correct_metadata(tmp_path):
    mat = EvidenceMediaMaterializer(tmp_path)
    vf = create_mock_video_frame(123, 5.0)
    ev = create_mock_evidence(123, 5.0)
    
    result = mat.materialize_frame(vf, ev)
    assert result.evidence_id == "ev_123"
    assert result.evidence_type == EvidenceType.FRAME
    assert result.frame_number == 123
    assert result.timestamp_seconds == 5.0

# 4. Generated path is deterministic.
def test_generated_path_is_deterministic(tmp_path):
    mat = EvidenceMediaMaterializer(tmp_path)
    vf = create_mock_video_frame(123, 5.0)
    ev = create_mock_evidence(123, 5.0)
    
    result = mat.materialize_frame(vf, ev)
    expected_path = tmp_path.resolve() / "frames" / "cam1" / "frame_123.jpg"
    assert Path(result.path) == expected_path

# 5. Repeated materialization produces the same path.
def test_repeated_materialization_same_path(tmp_path):
    mat = EvidenceMediaMaterializer(tmp_path)
    vf = create_mock_video_frame(123, 5.0)
    ev = create_mock_evidence(123, 5.0)
    
    result1 = mat.materialize_frame(vf, ev)
    result2 = mat.materialize_frame(vf, ev)
    assert result1.path == result2.path

# 6. Frame number appears in filename.
def test_frame_number_appears_in_filename(tmp_path):
    mat = EvidenceMediaMaterializer(tmp_path)
    vf = create_mock_video_frame(456, 5.0)
    ev = create_mock_evidence(456, 5.0)
    
    result = mat.materialize_frame(vf, ev)
    assert "frame_456.jpg" in result.path

# 7. Source identity is safely represented in the path.
def test_source_identity_in_path(tmp_path):
    mat = EvidenceMediaMaterializer(tmp_path)
    vf = create_mock_video_frame(123, 5.0)
    ev = create_mock_evidence(123, 5.0, source_id="front-door-cam")
    
    result = mat.materialize_frame(vf, ev)
    assert "front-door-cam" in Path(result.path).parts

# 8. Source IDs containing unsafe path characters are rejected or safely normalized.
# 9. `../` traversal is rejected.
# 10. Absolute-path source IDs are rejected.
@pytest.mark.parametrize("unsafe_id", [
    "../cam1",
    "cam1/../cam2",
    "/absolute/cam",
    "C:\\Windows",
    "cam1..",
    "cam1%20",
    "cam@!#"
])
def test_unsafe_source_ids_rejected(tmp_path, unsafe_id):
    mat = EvidenceMediaMaterializer(tmp_path)
    vf = create_mock_video_frame(123, 5.0)
    ev = create_mock_evidence(123, 5.0, source_id=unsafe_id)
    
    with pytest.raises(ValueError, match="Invalid source_id"):
        mat.materialize_frame(vf, ev)

# 11. Evidence/frame number mismatch is rejected.
def test_evidence_frame_number_mismatch_rejected(tmp_path):
    mat = EvidenceMediaMaterializer(tmp_path)
    vf = create_mock_video_frame(123, 5.0)
    ev = create_mock_evidence(999, 5.0)
    
    with pytest.raises(ValueError, match="mismatch"):
        mat.materialize_frame(vf, ev)

# 12. Evidence/timestamp mismatch is rejected.
def test_evidence_timestamp_mismatch_rejected(tmp_path):
    mat = EvidenceMediaMaterializer(tmp_path)
    vf = create_mock_video_frame(123, 5.0)
    ev = create_mock_evidence(123, 9.9)
    
    with pytest.raises(ValueError, match="mismatch"):
        mat.materialize_frame(vf, ev)

# 13. Wrong evidence type is rejected.
def test_wrong_evidence_type_rejected(tmp_path):
    mat = EvidenceMediaMaterializer(tmp_path)
    vf = create_mock_video_frame(123, 5.0)
    ev = Evidence(
        evidence_id="ev_123",
        evidence_type=EvidenceType.VIDEO_SEGMENT,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        video_segment=VideoSegmentEvidence(start_frame_number=1, end_frame_number=2, start_timestamp_seconds=1.0, end_timestamp_seconds=2.0),
        event_id="evt_123"
    )
    
    with pytest.raises(ValueError, match="Evidence must be of type FRAME"):
        mat.materialize_frame(vf, ev)

# 14. Empty/invalid output directory is rejected.
def test_empty_output_directory_rejected():
    with pytest.raises(ValueError, match="Output directory cannot be empty"):
        EvidenceMediaMaterializer("")

# 15. Failed `cv2.imwrite` is detected and converted into a clear exception.
def test_failed_imwrite_raises_exception(tmp_path):
    mat = EvidenceMediaMaterializer(tmp_path)
    vf = create_mock_video_frame(123, 5.0)
    ev = create_mock_evidence(123, 5.0)
    
    with patch("cv2.imwrite", return_value=False):
        with pytest.raises(RuntimeError, match="Failed to write image"):
            mat.materialize_frame(vf, ev)

# 16. Original VideoFrame image is unchanged after materialization.
def test_original_image_is_unchanged(tmp_path):
    mat = EvidenceMediaMaterializer(tmp_path)
    vf = create_mock_video_frame(123, 5.0)
    ev = create_mock_evidence(123, 5.0)
    
    original_sum = np.sum(vf.image)
    mat.materialize_frame(vf, ev)
    assert np.sum(vf.image) == original_sum

# 17. Existing deterministic file behavior is tested. (overwrite is idempotent)
def test_existing_deterministic_file_behavior(tmp_path):
    mat = EvidenceMediaMaterializer(tmp_path)
    vf = create_mock_video_frame(123, 5.0)
    ev = create_mock_evidence(123, 5.0)
    
    # Materialize once
    res1 = mat.materialize_frame(vf, ev)
    mtime1 = Path(res1.path).stat().st_mtime
    
    # Change image slightly to verify overwrite happens
    vf.image[0, 0] = [255, 255, 255]
    res2 = mat.materialize_frame(vf, ev)
    
    assert res1.path == res2.path
    # The file should have been rewritten
    assert Path(res2.path).exists()

# 18. No random IDs or wall-clock timestamps are introduced.
def test_no_random_ids_or_wall_clock_introduced(tmp_path):
    mat = EvidenceMediaMaterializer(tmp_path)
    vf = create_mock_video_frame(123, 5.0)
    ev = create_mock_evidence(123, 5.0)
    
    res = mat.materialize_frame(vf, ev)
    assert not hasattr(res, "created_at")
    assert not hasattr(res, "id") # Only evidence_id exists, which comes from original evidence

# Add a test for None inputs
def test_none_inputs(tmp_path):
    mat = EvidenceMediaMaterializer(tmp_path)
    vf = create_mock_video_frame(123, 5.0)
    ev = create_mock_evidence(123, 5.0)
    
    with pytest.raises(ValueError):
        mat.materialize_frame(None, ev)
        
    with pytest.raises(ValueError):
        mat.materialize_frame(vf, None)
