from dataclasses import dataclass, field
import time
from typing import Callable, Optional

from app.services.video_frame import VideoFrame
from app.services.video_stream import VideoStream
from app.services.detection.detector import Detector
from app.services.detection.performance_config import DetectionPerformanceConfig
from app.services.tracking.tracker import Tracker
from app.services.tracking.models import TrackedObject


@dataclass(frozen=True)
class FrameProcessingResult:
    """
    Summary of a frame-processing run.
    """

    frames_processed: int
    first_frame_number: int | None
    last_frame_number: int | None
    total_frames_read: int
    frames_skipped: int
    inference_frames_skipped: int = 0
    tracking_results: list[list[TrackedObject]] = field(default_factory=list)
    processed_frame_numbers: list[int] = field(default_factory=list)
    processed_timestamps: list[float] = field(default_factory=list)


class FrameProcessor:
    """
    Consumes frames from a VideoStream.

    AI detection will be added to this processing layer later.
    """

    def __init__(
        self, 
        detector: Detector | None = None,
        tracker: Tracker | None = None,
        performance_config: Optional[DetectionPerformanceConfig] = None,
        clock: Callable[[], float] = time.monotonic
    ):
        if tracker is not None and detector is None:
            raise ValueError("A detector is required when a tracker is configured.")
            
        self.detector = detector
        self.tracker = tracker
        self.performance_config = performance_config
        self.clock = clock

    def process(
        self,
        stream: VideoStream,
        max_frames: int | None = None,
        frame_skip: int = 0,
        on_frame_processed: Callable[[int, float, list[TrackedObject]], None] | None = None,
    ) -> FrameProcessingResult:
        """
        Process frames from an opened video stream.

        Args:
            stream: Opened video stream.
            max_frames: Maximum number of frames to process.
            frame_skip: Number of frames to skip between processed frames.
            on_frame_processed: Optional callback fired after a frame is processed.
        """

        if frame_skip < 0:
            raise ValueError(
                "frame_skip must be greater than or equal to 0."
            )

        frames_processed = 0
        first_frame_number: int | None = None
        last_frame_number: int | None = None

        total_frames_read = 0
        frames_skipped = 0
        inference_frames_skipped = 0
        tracking_results: list[list[TrackedObject]] = []
        processed_frame_numbers: list[int] = []
        processed_timestamps: list[float] = []
        
        last_inference_time: float | None = None
        min_inference_interval: float | None = None
        
        if self.performance_config and self.performance_config.max_inference_fps is not None:
            min_inference_interval = 1.0 / self.performance_config.max_inference_fps

        for frame in stream.frames():
            total_frames_read += 1

            if not isinstance(frame, VideoFrame):
                raise TypeError(
                    "VideoStream must yield VideoFrame objects."
                )

            if (
                (frame.frame_number - 1) % (frame_skip + 1) != 0
            ):
                frames_skipped += 1
                continue

            if first_frame_number is None:
                first_frame_number = frame.frame_number

            last_frame_number = frame.frame_number
            frames_processed += 1

            if self.detector is not None:
                should_detect = True
                current_time = self.clock()
                
                if min_inference_interval is not None:
                    if last_inference_time is not None:
                        elapsed = current_time - last_inference_time
                        if elapsed < min_inference_interval:
                            should_detect = False
                
                if should_detect:
                    detections = self.detector.detect(frame)
                    last_inference_time = current_time
                    
                    if self.tracker is not None:
                        tracked_objects = self.tracker.update(detections)
                        tracking_results.append(tracked_objects)
                        processed_frame_numbers.append(frame.frame_number)
                        processed_timestamps.append(frame.timestamp_seconds)
                        
                        if on_frame_processed:
                            on_frame_processed(frame.frame_number, frame.timestamp_seconds, tracked_objects)
                else:
                    inference_frames_skipped += 1

            if (
                max_frames is not None
                and frames_processed >= max_frames
            ):
                break

        return FrameProcessingResult(
            frames_processed=frames_processed,
            first_frame_number=first_frame_number,
            last_frame_number=last_frame_number,
            total_frames_read=total_frames_read,
            frames_skipped=frames_skipped,
            inference_frames_skipped=inference_frames_skipped,
            tracking_results=tracking_results,
            processed_frame_numbers=processed_frame_numbers,
            processed_timestamps=processed_timestamps
        )