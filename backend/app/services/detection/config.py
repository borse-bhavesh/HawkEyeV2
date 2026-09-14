from pydantic import BaseModel, Field, field_validator

class DetectionConfig(BaseModel):
    model_name: str = Field(..., description="Name of the YOLO model to load")
    confidence_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    
    @field_validator('model_name')
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("model_name must not be empty")
        return v
