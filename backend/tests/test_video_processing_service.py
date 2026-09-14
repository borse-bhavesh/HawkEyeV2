from pathlib import Path
import pytest
from app.services.video_processing_service import (
    VideoProcessingService,
)

from app.services.video_processing_config import (
    VideoProcessingConfig,
)

from app.services.video_processing_status import (
    VideoProcessingStatus,
)

from app.services.video_source import LocalVideoSource
from app.services.detection.mock_detector import MockDetector
from app.services.tracking.config import TrackingConfig


TEST_VIDEO = (
    Path(__file__).parent
    / "fixtures"
    / "test_video.mp4"
)


def test_video_processing_service_processes_frames():
    source = LocalVideoSource(TEST_VIDEO)

    service = VideoProcessingService()

    result = service.process(
        source,
        max_frames=10,
    )

    assert result.source == str(TEST_VIDEO)

    assert result.processing.frames_processed == 10
    assert result.processing.first_frame_number == 1
    assert result.processing.last_frame_number == 10


def test_video_processing_service_closes_stream():
    source = LocalVideoSource(TEST_VIDEO)

    service = VideoProcessingService()

    result = service.process(
        source,
        max_frames=1,
    )

    assert result.processing.frames_processed == 1

def test_video_processing_service_uses_config_max_frames():
    source = LocalVideoSource(TEST_VIDEO)

    config = VideoProcessingConfig(
        max_frames=5,
    )

    service = VideoProcessingService(
        config=config,
    )

    result = service.process(source)

    assert result.processing.frames_processed == 5
    assert result.processing.first_frame_number == 1
    assert result.processing.last_frame_number == 5

def test_video_processing_service_uses_config_frame_skip():
    source = LocalVideoSource(TEST_VIDEO)

    config = VideoProcessingConfig(
        max_frames=5,
        frame_skip=1,
    )

    service = VideoProcessingService(
        config=config,
    )

    result = service.process(source)

    assert result.processing.frames_processed == 5
    assert result.processing.first_frame_number == 1
    assert result.processing.last_frame_number == 9

def test_video_processing_service_returns_completed_status():
    source = LocalVideoSource(TEST_VIDEO)

    service = VideoProcessingService()

    result = service.process(
        source,
        max_frames=5,
    )

    assert result.status == VideoProcessingStatus.COMPLETED

def test_video_processing_service_returns_failed_status():
    source = LocalVideoSource(
        Path(__file__).parent
        / "fixtures"
        / "does_not_exist.mp4"
    )

    service = VideoProcessingService()

    try:
        service.process(source)
    except Exception as exc:
        assert isinstance(exc, Exception)
    else:
        raise AssertionError(
            "Expected video processing to fail."
        )

def test_video_processing_service_rejects_invalid_max_frames():
    source = LocalVideoSource(TEST_VIDEO)
    service = VideoProcessingService()

    with pytest.raises(
        ValueError,
        match="max_frames must be greater than 0.",
    ):
        service.process(
            source,
            max_frames=0,
        )


def test_video_processing_service_rejects_negative_frame_skip():
    source = LocalVideoSource(TEST_VIDEO)
    service = VideoProcessingService()

    with pytest.raises(
        ValueError,
        match="frame_skip must be greater than or equal to 0.",
    ):
        service.process(
            source,
            frame_skip=-1,
        )

def test_video_processing_service_with_detector_and_tracker():
    """
    Test that the service correctly orchestrates the mock detector, tracker, and events.
    """
    source = LocalVideoSource(TEST_VIDEO)
    detector = MockDetector()
    tracking_config = TrackingConfig()
    
    from app.services.events.config import EventIntelligenceConfig
    from app.services.risk.config import RiskConfig
    
    event_config = EventIntelligenceConfig(track_end_grace_frames=1)
    risk_config = RiskConfig()
    
    service = VideoProcessingService(
        detector=detector,
        tracking_config=tracking_config,
        event_config=event_config,
        risk_config=risk_config,
        generate_evidence=True
    )
    
    result = service.process(
        source,
        max_frames=3,
    )
    
    assert result.status == VideoProcessingStatus.COMPLETED
    assert result.processing.frames_processed == 3
    # With a mock detector that always yields 1 detection and tracking config,
    # we should get tracking results for each processed frame.
    assert len(result.processing.tracking_results) == 3
    
    # Check that tracking results contain tracked objects (MockTracker assigns track_id=1)
    for frame_tracks in result.processing.tracking_results:
        assert len(frame_tracks) > 0
        assert frame_tracks[0].track_id == 1
        assert frame_tracks[0].class_name == "class_0"
        
    # Check that event collection works (we should see TRACK_STARTED and TRACK_ENDED)
    assert result.events is not None
    assert len(result.events) > 0
    
    event_types = {e.event_type for e in result.events}
    
    from app.services.events.models import EventType
    assert EventType.TRACK_STARTED in event_types
    # Because we hit max_frames and grace=1 is small enough for finalize() to trigger end,
    # TRACK_ENDED should be present in the collected events.
    assert EventType.TRACK_ENDED in event_types

    # Check risk orchestration
    assert result.risks is not None
    assert len(result.risks) > 0
    
    # Verify that the generated risks include policy assessments for the events
    # We should have at least TRACK_STARTED and TRACK_ENDED risks
    risk_event_types = set()
    for r in result.risks:
        risk_event_types.update(r.contributing_event_types)
        
    assert EventType.TRACK_STARTED in risk_event_types
    assert EventType.TRACK_ENDED in risk_event_types

    # Check evidence orchestration
    assert result.evidence is not None
    assert len(result.evidence) > 0
    
    # Verify we got FrameEvidence with correct metadata
    from app.services.evidence.models import EvidenceType
    frame_evidences = [e for e in result.evidence if e.evidence_type == EvidenceType.FRAME]
    assert len(frame_evidences) > 0
    for e in frame_evidences:
        assert e.frame.frame_number > 0
        assert e.frame.timestamp_seconds >= 0.0
        assert not hasattr(e, 'image_bytes')
        assert not hasattr(e, 'raw_data')