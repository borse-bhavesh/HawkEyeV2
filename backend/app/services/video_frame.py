from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class VideoFrame:
    """
    Represents a single frame extracted from a video source.
    """

    frame_number: int
    timestamp_seconds: float
    image: np.ndarray