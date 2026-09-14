from pydantic import BaseModel, Field


class VideoMetadata(BaseModel):
    """
    Metadata describing an opened video source.
    """

    source: str = Field(min_length=1)

    fps: float = Field(ge=0)

    frame_count: int = Field(ge=0)

    width: int = Field(ge=0)

    height: int = Field(ge=0)

    duration_seconds: float = Field(ge=0)