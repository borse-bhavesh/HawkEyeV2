from pydantic import BaseModel, Field
from typing import Literal

class TrackingConfig(BaseModel):
    """
    Configuration for object tracking algorithms (e.g. ByteTrack).
    This controls track association and lifecycle, separate from YOLO detection.
    """
    tracker_type: Literal["bytetrack"] = "bytetrack"
    
    # High confidence threshold for initial track matching
    track_high_thresh: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Low confidence threshold for secondary track matching (ByteTrack's core feature)
    track_low_thresh: float = Field(default=0.1, ge=0.0, le=1.0)
    
    # Threshold to instantiate a brand new track
    new_track_thresh: float = Field(default=0.6, ge=0.0, le=1.0)
    
    # Maximum number of frames to retain a lost track in memory before removing it
    track_buffer: int = Field(default=30, ge=1)
    
    # IoU matching threshold
    match_thresh: float = Field(default=0.8, ge=0.0, le=1.0)
    
    # Whether to fuse detection confidence score into the association cost matrix
    fuse_score: bool = True
