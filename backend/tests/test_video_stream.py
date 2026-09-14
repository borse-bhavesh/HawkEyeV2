from pathlib import Path

import pytest

from app.services.video_stream import VideoStream, VideoStreamError
from app.services.video_source import LocalVideoSource


TEST_VIDEO = (
    Path(__file__).parent
    / "fixtures"
    / "test_video.mp4"
)


def test_video_stream_opens():
    stream = VideoStream(TEST_VIDEO)

    stream.open()

    assert stream.capture is not None
    assert stream.capture.isOpened()

    stream.close()


def test_video_metadata():
    stream = VideoStream(TEST_VIDEO)

    stream.open()

    metadata = stream.get_metadata()

    assert metadata.source == str(TEST_VIDEO)
    assert metadata.fps > 0
    assert metadata.frame_count > 0
    assert metadata.width > 0
    assert metadata.height > 0
    assert metadata.duration_seconds > 0

    stream.close()


def test_video_reads_frames():
    stream = VideoStream(TEST_VIDEO)

    stream.open()

    frame = stream.read_frame()

    assert frame is not None
    assert frame.frame_number == 1
    assert frame.timestamp_seconds >= 0
    assert frame.image is not None
    assert frame.image.size > 0
    assert frame.image.shape[0] > 0
    assert frame.image.shape[1] > 0

    stream.close()

def test_video_frame_iterator():
    stream = VideoStream(TEST_VIDEO)

    stream.open()

    frames = []

    for frame in stream.frames():
        frames.append(frame)

        if len(frames) >= 10:
            break

    stream.close()

    assert len(frames) == 10

    for index, frame in enumerate(frames, start=1):
        assert frame.frame_number == index
        assert frame.timestamp_seconds >= 0
        assert frame.image is not None
        assert frame.image.size > 0


def test_invalid_video_source():
    invalid_source = (
        Path(__file__).parent
        / "fixtures"
        / "does_not_exist.mp4"
    )

    stream = VideoStream(invalid_source)

    with pytest.raises(VideoStreamError):
        stream.open()


def test_stream_context_manager():
    with VideoStream(TEST_VIDEO) as stream:
        assert stream.capture is not None
        assert stream.capture.isOpened()

        frame = stream.read_frame()

        assert frame is not None
        assert frame.frame_number == 1
        assert frame.image is not None
        assert frame.image.size > 0

    assert stream.capture is None

def test_video_stream_accepts_video_source():
    source = LocalVideoSource(TEST_VIDEO)

    stream = VideoStream(source)

    stream.open()

    assert stream.capture is not None
    assert stream.capture.isOpened()

    frame = stream.read_frame()

    assert frame is not None
    assert frame.frame_number == 1
    assert frame.image is not None
    assert frame.image.size > 0

    stream.close()