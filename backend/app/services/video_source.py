from abc import ABC, abstractmethod
from pathlib import Path


class VideoSource(ABC):
    """
    Abstract base class for HAWKEYE video sources.
    """

    @abstractmethod
    def get_source(self) -> str:
        """
        Return the source understood by the video ingestion layer.
        """
        raise NotImplementedError


class LocalVideoSource(VideoSource):
    """
    Video source representing a local recorded video file.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def get_source(self) -> str:
        """
        Return the local video path as a string.
        """
        return str(self.path)