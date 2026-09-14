from pydantic import BaseModel, Field


class VideoProcessingConfig(BaseModel):
    """
    Configuration controlling video frame processing behavior.
    """

    max_frames: int | None = Field(
        default=None,
        ge=1,
    )

    frame_skip: int = Field(
        default=0,
        ge=0,
    )