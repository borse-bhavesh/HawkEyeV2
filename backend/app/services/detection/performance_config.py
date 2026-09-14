from typing import Literal, Optional
from pydantic import BaseModel, Field

class DetectionPerformanceConfig(BaseModel):
    device: Literal["auto", "cpu", "cuda"] = "auto"
    image_size: int = Field(default=640, gt=0)
    half_precision: bool = False
    max_inference_fps: Optional[float] = Field(default=None, gt=0)
