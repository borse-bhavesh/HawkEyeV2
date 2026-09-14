import logging
from pathlib import Path
from typing import Iterator

import cv2

from app.services.video_metadata import VideoMetadata
from app.services.video_frame import VideoFrame
from app.services.video_source import VideoSource

logger = logging.getLogger(__name__)


class VideoStreamError(Exception):
    """Raised when a video stream cannot be opened or read."""


class VideoStream:
    """
    Video ingestion service for recorded/local video sources.

    The class is intentionally independent of FastAPI so it can later
    support RTSP cameras and webcams without changing the API layer.
    """

    def __init__(self, source: str | Path | VideoSource):
        if isinstance(source, VideoSource):
            self.source = source.get_source()
        else:
            self.source = str(source)
        self.capture: cv2.VideoCapture | None = None
        self.frame_number: int = 0

    def open(self) -> None:
        """
        Open the configured video source.
        """

        if not self.source:
            raise VideoStreamError("Video source cannot be empty.")

        self.frame_number = 0
        self.capture = cv2.VideoCapture(self.source)

        if not self.capture.isOpened():
            self.capture.release()
            self.capture = None

            raise VideoStreamError(
                f"Unable to open video source: {self.source}"
            )

        logger.info(
            "VIDEO_STREAM_OPENED | source=%s",
            self.source,
        )

    def read_frame(self) -> VideoFrame | None:
        """
        Read the next frame and attach frame metadata.

        Returns:
             A VideoFrame object, or None when the video ends.
        """

        if self.capture is None:
            raise VideoStreamError(
                "Video stream is not open. Call open() first."
            )

        success, frame = self.capture.read()

        if not success:
            return None

        self.frame_number += 1

        fps = self.capture.get(cv2.CAP_PROP_FPS)

        timestamp_seconds = (
            (self.frame_number - 1) / fps
            if fps > 0
            else 0.0
        )

        return VideoFrame(
            frame_number=self.frame_number,
            timestamp_seconds=timestamp_seconds,
            image=frame,
        )

    def get_metadata(self) -> VideoMetadata:
        """
        Return basic metadata about the opened video.
        """

        if self.capture is None:
            raise VideoStreamError(
                "Video stream is not open. Call open() first."
            )

        fps = self.capture.get(cv2.CAP_PROP_FPS)
        frame_count = self.capture.get(cv2.CAP_PROP_FRAME_COUNT)
        width = self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)

        duration = (
            frame_count / fps
            if fps > 0
            else 0.0
        )

        return VideoMetadata(
            source=self.source,
            fps=fps,
            frame_count=int(frame_count),
            width=int(width),
            height=int(height),
            duration_seconds=duration,
        )

    def frames(self) -> Iterator[VideoFrame]:
        """
        Yield video frames sequentially.
        """

        if self.capture is None:
            raise VideoStreamError(
                "Video stream is not open. Call open() first."
            )

        while True:
            frame = self.read_frame()

            if frame is None:
                break

            yield frame

    def close(self) -> None:
        """
        Release the video source.
        """

        if self.capture is not None:
            self.capture.release()
            self.capture = None

            logger.info(
                "VIDEO_STREAM_CLOSED | source=%s",
                self.source,
            )

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()