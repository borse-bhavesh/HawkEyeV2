from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel

class ProcessingSessionDomain(BaseModel):
    session_id: str
    source_id: str
    source_type: str
    status: str = "STARTED"
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    restricted_zone: Optional[Dict[str, Any]] = None
    processed_until_frame: Optional[int] = None
    processed_until_timestamp: Optional[float] = None

class TrackDomain(BaseModel):
    id: str
    processing_session_id: str
    session_track_id: int
    class_id: Optional[int] = None
    class_name: Optional[str] = None
    confidence: Optional[float] = None
    latest_bbox: Optional[Dict[str, Any]] = None

class TrackObservationDomain(BaseModel):
    processing_session_id: str
    track_id: str
    frame_number: int
    timestamp_seconds: float
    class_name: Optional[str] = None
    confidence: Optional[float] = None
    bbox_x1: float
    bbox_y1: float
    bbox_x2: float
    bbox_y2: float

