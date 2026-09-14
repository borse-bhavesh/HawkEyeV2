from pydantic import ValidationError
import pytest

from app.services.video_processing_response import (
    VideoProcessingResponse,
)
from app.services.video_processing_status import (
    VideoProcessingStatus,
)


def test_video_processing_response():
    response = VideoProcessingResponse(
        source="test_video.mp4",
        frames_processed=10,
        first_frame_number=1,
        last_frame_number=19,
        total_frames_read=19,
        frames_skipped=9,
        status=VideoProcessingStatus.COMPLETED,
    )

    assert response.source == "test_video.mp4"
    assert response.frames_processed == 10
    assert response.first_frame_number == 1
    assert response.last_frame_number == 19
    assert response.total_frames_read == 19
    assert response.frames_skipped == 9
    assert response.status == VideoProcessingStatus.COMPLETED


def test_video_processing_response_allows_empty_processing_result():
    response = VideoProcessingResponse(
        source="test_video.mp4",
        frames_processed=0,
        first_frame_number=None,
        last_frame_number=None,
        total_frames_read=0,
        frames_skipped=0,
        status=VideoProcessingStatus.COMPLETED,
    )

    assert response.frames_processed == 0
    assert response.first_frame_number is None
    assert response.last_frame_number is None
    assert response.total_frames_read == 0
    assert response.frames_skipped == 0


def test_video_processing_response_rejects_negative_frames():
    with pytest.raises(ValidationError):
        VideoProcessingResponse(
            source="test_video.mp4",
            frames_processed=-1,
            total_frames_read=0,
            frames_skipped=0,
            status=VideoProcessingStatus.COMPLETED,
        )