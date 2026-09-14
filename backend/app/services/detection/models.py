from pydantic import BaseModel, Field, model_validator


class BoundingBox(BaseModel):
    """
    Represents the spatial coordinates of a detected object.
    """

    x1: float = Field(ge=0)
    y1: float = Field(ge=0)
    x2: float = Field(ge=0)
    y2: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_coordinates(self) -> "BoundingBox":
        """
        Ensure the bottom-right corner is below and to the right
        of the top-left corner.
        """

        if self.x2 <= self.x1:
            raise ValueError("x2 must be greater than x1.")

        if self.y2 <= self.y1:
            raise ValueError("y2 must be greater than y1.")

        return self


class Detection(BaseModel):
    """
    Represents a single object detected in a video frame.
    """

    class_id: int = Field(ge=0)
    class_name: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: BoundingBox