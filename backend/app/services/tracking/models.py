from pydantic import BaseModel, Field

from app.services.detection.models import BoundingBox


class TrackedObject(BaseModel):
    """
    Represents the temporal identity of an observed object across multiple frames.
    """

    track_id: int = Field(ge=0)
    class_id: int = Field(ge=0)
    class_name: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: BoundingBox
