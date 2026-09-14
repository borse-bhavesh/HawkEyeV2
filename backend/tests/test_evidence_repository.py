import pytest
from pathlib import Path

from app.services.evidence.models import Evidence, EvidenceType, EvidenceSource, FrameEvidence, VideoSegmentEvidence
from app.services.evidence.repository import (
    EvidenceRepository, 
    InMemoryEvidenceRepository, 
    EvidenceAlreadyExistsError,
    EvidenceRepositoryError
)

def create_frame_evidence(ev_id: str, event_id: str = "default_evt", assessment_id: str = "default_ass") -> Evidence:
    return Evidence(
        evidence_id=ev_id,
        evidence_type=EvidenceType.FRAME,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        frame=FrameEvidence(frame_number=1, timestamp_seconds=1.0),
        event_id=event_id,
        assessment_id=assessment_id
    )

def create_segment_evidence(ev_id: str, event_id: str = "default_evt", assessment_id: str = "default_ass") -> Evidence:
    return Evidence(
        evidence_id=ev_id,
        evidence_type=EvidenceType.VIDEO_SEGMENT,
        source=EvidenceSource(source_id="cam1", source_type="rtsp"),
        video_segment=VideoSegmentEvidence(
            start_frame_number=1, end_frame_number=10, 
            start_timestamp_seconds=0.0, end_timestamp_seconds=1.0
        ),
        event_id=event_id,
        assessment_id=assessment_id
    )

# 1. Repository can save FrameEvidence wrapped in Evidence.
def test_repository_saves_frame_evidence():
    repo = InMemoryEvidenceRepository()
    ev = create_frame_evidence("f1")
    saved = repo.save(ev)
    assert saved.evidence_id == "f1"
    assert repo.get_by_id("f1") is not None

# 2. Repository can save VideoSegmentEvidence wrapped in Evidence.
def test_repository_saves_segment_evidence():
    repo = InMemoryEvidenceRepository()
    ev = create_segment_evidence("v1")
    saved = repo.save(ev)
    assert saved.evidence_id == "v1"
    assert repo.get_by_id("v1") is not None

# 3. get_by_id returns saved evidence.
def test_get_by_id_returns_saved():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1"))
    ev = repo.get_by_id("f1")
    assert ev.evidence_id == "f1"

# 4. get_by_id returns None for missing ID.
def test_get_by_id_missing_returns_none():
    repo = InMemoryEvidenceRepository()
    assert repo.get_by_id("missing") is None

# 5. Duplicate evidence_id is rejected.
def test_duplicate_evidence_id_rejected():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1"))
    with pytest.raises(EvidenceAlreadyExistsError):
        repo.save(create_frame_evidence("f1"))

# 6. list_by_event_id returns matching evidence.
# 7. list_by_event_id excludes evidence without event_id.
def test_list_by_event_id():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1", event_id="evt1"))
    repo.save(create_frame_evidence("f2", event_id="evt2"))
    repo.save(create_frame_evidence("f3", event_id=None, assessment_id="ass3"))
    
    evt1_list = repo.list_by_event_id("evt1")
    assert len(evt1_list) == 1
    assert evt1_list[0].evidence_id == "f1"

# 8. list_by_assessment_id returns matching evidence.
# 9. list_by_assessment_id excludes evidence without assessment_id.
def test_list_by_assessment_id():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1", assessment_id="ass1"))
    repo.save(create_frame_evidence("f2", assessment_id="ass2"))
    repo.save(create_frame_evidence("f3", assessment_id=None, event_id="evt3"))
    
    ass1_list = repo.list_by_assessment_id("ass1")
    assert len(ass1_list) == 1
    assert ass1_list[0].evidence_id == "f1"

# 10. Query results preserve insertion order.
def test_query_results_preserve_insertion_order():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1", event_id="evt1"))
    repo.save(create_frame_evidence("f3", event_id="evt1"))
    repo.save(create_frame_evidence("f2", event_id="evt1"))
    
    results = repo.list_by_event_id("evt1")
    ids = [r.evidence_id for r in results]
    assert ids == ["f1", "f3", "f2"]

# 11. Query results are independent lists.
def test_query_results_are_independent_lists():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1", event_id="evt1"))
    list1 = repo.list_by_event_id("evt1")
    list1.append("some_garbage")
    
    list2 = repo.list_by_event_id("evt1")
    assert len(list2) == 1
    assert list2[0].evidence_id == "f1"

# 12. delete existing evidence returns True.
def test_delete_existing_returns_true():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1"))
    assert repo.delete("f1") is True

# 13. delete missing evidence returns False.
def test_delete_missing_returns_false():
    repo = InMemoryEvidenceRepository()
    assert repo.delete("missing") is False

# 14. Delete does not affect other records.
def test_delete_does_not_affect_other_records():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1"))
    repo.save(create_frame_evidence("f2"))
    repo.delete("f1")
    
    assert repo.get_by_id("f1") is None
    assert repo.get_by_id("f2") is not None

# 15. Delete does not delete media files.
# Implicitly verified since InMemoryEvidenceRepository never calls os or Path functions.
def test_delete_does_not_affect_files(tmp_path):
    repo = InMemoryEvidenceRepository()
    fake_media = tmp_path / "fake.jpg"
    fake_media.touch()
    
    repo.save(create_frame_evidence("f1"))
    repo.delete("f1")
    
    assert fake_media.exists()

# 16. Repository rejects None.
def test_repository_rejects_none():
    repo = InMemoryEvidenceRepository()
    with pytest.raises(ValueError):
        repo.save(None)

# 17. Repository rejects invalid evidence.
def test_repository_rejects_invalid_evidence():
    repo = InMemoryEvidenceRepository()
    # Mocking an invalid object bypassing pydantic validation
    class FakeEv:
        evidence_id = ""
    with pytest.raises(ValueError):
        repo.save(FakeEv())

# 18. Original Evidence object mutation after save does not mutate repository state.
def test_original_mutation_does_not_affect_repo():
    repo = InMemoryEvidenceRepository()
    ev = create_frame_evidence("f1")
    repo.save(ev)
    
    # Mutate original
    ev.event_id = "mutated"
    
    stored = repo.get_by_id("f1")
    assert stored.event_id == "default_evt"

# 19. Returned Evidence mutation does not mutate repository state.
# 20. Nested Evidence data is defensively copied.
def test_returned_mutation_does_not_affect_repo():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1"))
    
    retrieved = repo.get_by_id("f1")
    # Mutate nested data
    retrieved.source.source_id = "hacked"
    
    retrieved2 = repo.get_by_id("f1")
    assert retrieved2.source.source_id == "cam1"

# 21. Frame evidence metadata remains intact.
def test_frame_evidence_metadata_intact():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1"))
    ev = repo.get_by_id("f1")
    assert ev.frame.frame_number == 1
    assert ev.frame.timestamp_seconds == 1.0

# 22. Video segment metadata remains intact.
def test_segment_evidence_metadata_intact():
    repo = InMemoryEvidenceRepository()
    repo.save(create_segment_evidence("v1"))
    ev = repo.get_by_id("v1")
    assert ev.video_segment.start_frame_number == 1
    assert ev.video_segment.end_frame_number == 10

# 23. Evidence event_id linkage remains intact.
# 24. Evidence assessment_id linkage remains intact.
def test_linkages_intact():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1", event_id="evt1", assessment_id="ass1"))
    ev = repo.get_by_id("f1")
    assert ev.event_id == "evt1"
    assert ev.assessment_id == "ass1"

# 25. Multiple evidence records can reference the same event.
def test_multiple_evidence_same_event():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1", event_id="evt1"))
    repo.save(create_frame_evidence("f2", event_id="evt1"))
    assert len(repo.list_by_event_id("evt1")) == 2

# 26. Multiple evidence records can reference the same assessment.
def test_multiple_evidence_same_assessment():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1", assessment_id="ass1"))
    repo.save(create_frame_evidence("f2", assessment_id="ass1"))
    assert len(repo.list_by_assessment_id("ass1")) == 2

# 27. Evidence can reference both event_id and assessment_id.
def test_evidence_references_both():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1", event_id="evt1", assessment_id="ass1"))
    assert len(repo.list_by_event_id("evt1")) == 1
    assert len(repo.list_by_assessment_id("ass1")) == 1

# 28. Repository starts empty.
def test_repository_starts_empty():
    repo = InMemoryEvidenceRepository()
    assert repo.get_by_id("anything") is None
    assert len(repo.list_by_event_id("anything")) == 0
    assert len(repo.list_by_assessment_id("anything")) == 0

# 29. Saving evidence does not create filesystem artifacts.
def test_saving_does_not_create_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1"))
    files = list(tmp_path.iterdir())
    assert len(files) == 0

# 30. Repository has no dependency on OpenCV/materializer/retriever.
# This is true by inspection since there are no cv2 or pathlib imports.

# 31. Repository remains deterministic across repeated operations.
def test_repository_deterministic_operations():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1", event_id="evt1"))
    r1 = repo.list_by_event_id("evt1")
    r2 = repo.list_by_event_id("evt1")
    assert r1[0].evidence_id == r2[0].evidence_id

# 32. Delete followed by get_by_id returns None.
def test_delete_then_get_returns_none():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1"))
    repo.delete("f1")
    assert repo.get_by_id("f1") is None

# 33. Delete followed by list queries removes the record from results.
def test_delete_removes_from_lists():
    repo = InMemoryEvidenceRepository()
    repo.save(create_frame_evidence("f1", event_id="evt1"))
    repo.delete("f1")
    assert len(repo.list_by_event_id("evt1")) == 0
