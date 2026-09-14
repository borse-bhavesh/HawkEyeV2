from pathlib import Path

from app.services.video_source import LocalVideoSource, VideoSource


TEST_VIDEO = (
    Path(__file__).parent
    / "fixtures"
    / "test_video.mp4"
)


def test_local_video_source():
    source = LocalVideoSource(TEST_VIDEO)

    assert isinstance(source, VideoSource)
    assert source.get_source() == str(TEST_VIDEO)


def test_local_video_source_accepts_string_path():
    source = LocalVideoSource(str(TEST_VIDEO))

    assert source.get_source() == str(TEST_VIDEO)


def test_local_video_source_preserves_path():
    source = LocalVideoSource(TEST_VIDEO)

    assert source.path == TEST_VIDEO