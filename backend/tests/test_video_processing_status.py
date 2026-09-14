from app.services.video_processing_status import (
    VideoProcessingStatus,
)


def test_video_processing_status_values():
    assert VideoProcessingStatus.PENDING.value == "pending"
    assert VideoProcessingStatus.RUNNING.value == "running"
    assert VideoProcessingStatus.COMPLETED.value == "completed"
    assert VideoProcessingStatus.FAILED.value == "failed"


def test_video_processing_status_is_string_enum():
    assert isinstance(VideoProcessingStatus.PENDING, str)