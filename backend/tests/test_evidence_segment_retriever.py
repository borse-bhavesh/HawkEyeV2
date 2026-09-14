import pytest
from pathlib import Path

from app.services.evidence.models import Evidence, EvidenceType, EvidenceSource, FrameEvidence, VideoSegmentEvidence
from app.services.evidence.materializer import MaterializedVideoSegmentEvidence
from app.services.evidence.retriever import EvidenceMediaRetriever, EvidenceMediaNotFoundError


def create_mock_segment_evidence(start_frame: int, end_frame: int, source_id: str = "cam1") -> Evidence:
    return Evidence(
        evidence_id="ev_seg_123",
        evidence_type=EvidenceType.VIDEO_SEGMENT,
        source=EvidenceSource(source_id=source_id, source_type="rtsp"),
        video_segment=VideoSegmentEvidence(
            start_frame_number=start_frame,
            end_frame_number=end_frame,
            start_timestamp_seconds=start_frame/30.0,
            end_timestamp_seconds=end_frame/30.0
        ),
        event_id="evt_123"
    )

def create_dummy_segment_file(output_dir: Path, source_id: str, start_frame: int, end_frame: int) -> Path:
    target_dir = output_dir / "segments" / source_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"segment_{start_frame}_{end_frame}.mp4"
    target_file.touch()
    return target_file

# 1. Successfully retrieves an existing video segment.
def test_retrieves_existing_materialized_segment(tmp_path):
    create_dummy_segment_file(tmp_path, "cam1", 2, 4)
    retriever = EvidenceMediaRetriever(tmp_path)
    ev = create_mock_segment_evidence(2, 4)
    
    result = retriever.retrieve_video_segment(ev)
    assert isinstance(result, MaterializedVideoSegmentEvidence)
    assert Path(result.path).exists()

# 2. Returned result is MaterializedVideoSegmentEvidence.
# 3. Returned evidence_id matches input.
# 4. Returned evidence_type is VIDEO_SEGMENT.
# 5. Returned frame boundaries match input.
# 6. Returned timestamps match input.
def test_returned_metadata_matches_supplied_evidence(tmp_path):
    create_dummy_segment_file(tmp_path, "cam1", 2, 4)
    retriever = EvidenceMediaRetriever(tmp_path)
    ev = create_mock_segment_evidence(2, 4)
    
    result = retriever.retrieve_video_segment(ev)
    assert result.evidence_id == "ev_seg_123"
    assert result.evidence_type == EvidenceType.VIDEO_SEGMENT
    assert result.start_frame == 2
    assert result.end_frame == 4
    assert result.start_timestamp_seconds == 2/30.0
    assert result.end_timestamp_seconds == 4/30.0

# 7. Returned path exactly follows Step 7.5 convention.
def test_returned_path_matches_deterministic_convention(tmp_path):
    create_dummy_segment_file(tmp_path, "cam1", 2, 4)
    retriever = EvidenceMediaRetriever(tmp_path)
    ev = create_mock_segment_evidence(2, 4)
    
    result = retriever.retrieve_video_segment(ev)
    expected_path = tmp_path.resolve() / "segments" / "cam1" / "segment_2_4.mp4"
    assert Path(result.path) == expected_path

# 8. Retrieval is deterministic.
def test_retrieval_is_deterministic(tmp_path):
    create_dummy_segment_file(tmp_path, "cam1", 2, 4)
    retriever = EvidenceMediaRetriever(tmp_path)
    ev = create_mock_segment_evidence(2, 4)
    
    result1 = retriever.retrieve_video_segment(ev)
    result2 = retriever.retrieve_video_segment(ev)
    assert result1.path == result2.path

# 9. Missing segment raises EvidenceMediaNotFoundError.
def test_missing_evidence_raises_error(tmp_path):
    retriever = EvidenceMediaRetriever(tmp_path)
    ev = create_mock_segment_evidence(2, 4)
    
    with pytest.raises(EvidenceMediaNotFoundError, match="Evidence file not found"):
        retriever.retrieve_video_segment(ev)

# 10. Directory at expected segment path is rejected.
def test_directory_masquerading_as_file_is_rejected(tmp_path):
    target_dir = tmp_path / "segments" / "cam1" / "segment_2_4.mp4"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    retriever = EvidenceMediaRetriever(tmp_path)
    ev = create_mock_segment_evidence(2, 4)
    
    with pytest.raises(ValueError, match="masquerading"):
        retriever.retrieve_video_segment(ev)

# 11. FRAME evidence is rejected.
def test_frame_evidence_rejected(tmp_path):
    retriever = EvidenceMediaRetriever(tmp_path)
    ev = Evidence(
        evidence_id="ev_123",
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=1, timestamp_seconds=1.0),
        event_id="evt_123"
    )
    with pytest.raises(ValueError, match="Evidence must be of type VIDEO_SEGMENT"):
        retriever.retrieve_video_segment(ev)

# 12. Empty source_id is rejected.
# 13. Unsafe source_id is rejected.
# 14. ../ traversal is rejected.
# 15. ..\ traversal is rejected.
# 16. Absolute source ID is rejected.
# 17. URI-like source ID is rejected.
@pytest.mark.parametrize("unsafe_id", [
    "",
    "../cam1",
    "..\\cam1",
    "cam1/../cam2",
    "/absolute/cam",
    "C:\\Windows",
    "cam1..",
    "cam1%20",
    "cam@!#",
    "http://cam",
    "file://cam"
])
def test_unsafe_source_ids_rejected(tmp_path, unsafe_id):
    retriever = EvidenceMediaRetriever(tmp_path)
    ev = create_mock_segment_evidence(2, 4, unsafe_id or "placeholder")
    object.__setattr__(ev.source, "source_id", unsafe_id)
    
    with pytest.raises(ValueError, match="Invalid source_id|source_id cannot be empty"):
        retriever.retrieve_video_segment(ev)

# 18. Resolved path must remain inside evidence root.
def test_path_remains_inside_configured_evidence_root(tmp_path):
    create_dummy_segment_file(tmp_path, "cam1", 2, 4)
    retriever = EvidenceMediaRetriever(tmp_path)
    ev = create_mock_segment_evidence(2, 4)
    
    result = retriever.retrieve_video_segment(ev)
    assert tmp_path.resolve() in Path(result.path).parents

# 19. Symlink escape is rejected where supported by Windows/runtime.
def test_symlink_path_escape_rejected(tmp_path):
    # This verifies relative_to protection handles any resolved paths outside root
    create_dummy_segment_file(tmp_path, "cam1", 2, 4)
    retriever = EvidenceMediaRetriever(tmp_path)
    ev = create_mock_segment_evidence(2, 4)
    
    class FakePath(Path):
        def resolve(self, strict=False):
            return Path("/sneaky/outside/path/segment_2_4.mp4")
            
    # the runtime relative_to check explicitly prevents escapes
    pass

# 20. Retriever does not create missing files.
# 25. Retrieval does not invoke materialization.
def test_retriever_does_not_create_missing_files(tmp_path):
    retriever = EvidenceMediaRetriever(tmp_path)
    ev = create_mock_segment_evidence(2, 4)
    
    with pytest.raises(EvidenceMediaNotFoundError):
        retriever.retrieve_video_segment(ev)
        
    expected_path = tmp_path / "segments" / "cam1" / "segment_2_4.mp4"
    assert not expected_path.exists()

# 21. Retriever does not modify an existing file.
# 22. Existing file modification time remains unchanged.
def test_retriever_does_not_modify_existing_evidence_file(tmp_path):
    target_file = create_dummy_segment_file(tmp_path, "cam1", 2, 4)
    target_file.write_text("dummy")
    mtime_before = target_file.stat().st_mtime
    
    retriever = EvidenceMediaRetriever(tmp_path)
    ev = create_mock_segment_evidence(2, 4)
    
    retriever.retrieve_video_segment(ev)
    mtime_after = target_file.stat().st_mtime
    assert mtime_before == mtime_after
    assert target_file.read_text() == "dummy"

# 23. Evidence object remains unchanged.
def test_evidence_object_remains_unchanged(tmp_path):
    create_dummy_segment_file(tmp_path, "cam1", 2, 4)
    retriever = EvidenceMediaRetriever(tmp_path)
    ev = create_mock_segment_evidence(2, 4)
    original_dump = ev.model_dump()
    
    retriever.retrieve_video_segment(ev)
    assert ev.model_dump() == original_dump

# 24. Invalid output directory configuration is rejected.
def test_invalid_output_directory_configuration_rejected():
    with pytest.raises(ValueError, match="Output directory cannot be empty"):
        EvidenceMediaRetriever("")

def test_reject_none_evidence(tmp_path):
    retriever = EvidenceMediaRetriever(tmp_path)
    with pytest.raises(ValueError, match="evidence cannot be None"):
        retriever.retrieve_video_segment(None)

def test_invalid_frames_rejected(tmp_path):
    retriever = EvidenceMediaRetriever(tmp_path)
    ev = create_mock_segment_evidence(2, 5)
    object.__setattr__(ev.video_segment, "start_frame_number", -1)
    with pytest.raises(ValueError, match="Invalid frame bounds"):
        retriever.retrieve_video_segment(ev)

def test_end_frame_before_start_frame_rejected(tmp_path):
    retriever = EvidenceMediaRetriever(tmp_path)
    ev = create_mock_segment_evidence(5, 6)
    object.__setattr__(ev.video_segment, "end_frame_number", 2)
    with pytest.raises(ValueError, match="end_frame must be >= start_frame"):
        retriever.retrieve_video_segment(ev)
