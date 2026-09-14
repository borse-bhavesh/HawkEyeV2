from enum import Enum


class VideoProcessingStatus(str, Enum):
    """
    Lifecycle states for a video-processing operation.
    """

    PENDING = "pending"
    UPLOADED = "uploaded"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"