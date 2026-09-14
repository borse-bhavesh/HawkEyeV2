import pytest
from pydantic import ValidationError

from app.services.video_processing_config import (
    VideoProcessingConfig,
)


def test_default_video_processing_config():
    config = VideoProcessingConfig()

    assert config.max_frames is None
    assert config.frame_skip == 0


def test_video_processing_config_custom_values():
    config = VideoProcessingConfig(
        max_frames=100,
        frame_skip=2,
    )

    assert config.max_frames == 100
    assert config.frame_skip == 2


def test_video_processing_config_rejects_invalid_max_frames():
    with pytest.raises(ValidationError):
        VideoProcessingConfig(max_frames=0)


def test_video_processing_config_rejects_negative_frame_skip():
    with pytest.raises(ValidationError):
        VideoProcessingConfig(frame_skip=-1)