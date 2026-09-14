from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class EvidenceType(str, Enum):
    FRAME = "FRAME"
    VIDEO_SEGMENT = "VIDEO_SEGMENT"


class EvidenceSource(BaseModel):
    source_id: str = Field(..., min_length=1)
    source_type: str = Field(..., min_length=1)


class FrameEvidence(BaseModel):
    frame_number: int = Field(..., ge=0)
    timestamp_seconds: float = Field(..., ge=0.0)


class VideoSegmentEvidence(BaseModel):
    start_frame_number: int = Field(..., ge=0)
    end_frame_number: int = Field(..., ge=0)
    start_timestamp_seconds: float = Field(..., ge=0.0)
    end_timestamp_seconds: float = Field(..., ge=0.0)

    @model_validator(mode='after')
    def validate_segment_bounds(self):
        if self.end_frame_number < self.start_frame_number:
            raise ValueError("end_frame_number must be >= start_frame_number")
        if self.end_timestamp_seconds < self.start_timestamp_seconds:
            raise ValueError("end_timestamp_seconds must be >= start_timestamp_seconds")
        return self


class Evidence(BaseModel):
    evidence_id: str = Field(..., min_length=1)
    evidence_type: EvidenceType
    source: EvidenceSource
    frame: Optional[FrameEvidence] = None
    video_segment: Optional[VideoSegmentEvidence] = None
    event_id: Optional[str] = None
    assessment_id: Optional[str] = None

    @model_validator(mode='after')
    def validate_references(self):
        if not self.event_id and not self.assessment_id:
            raise ValueError("At least one of event_id or assessment_id must be provided")

        if self.evidence_type == EvidenceType.FRAME:
            if self.frame is None:
                raise ValueError("FRAME evidence requires a frame reference")
            if self.video_segment is not None:
                raise ValueError("FRAME evidence cannot contain a video_segment")

        if self.evidence_type == EvidenceType.VIDEO_SEGMENT:
            if self.video_segment is None:
                raise ValueError("VIDEO_SEGMENT evidence requires a video_segment reference")
            if self.frame is not None:
                raise ValueError("VIDEO_SEGMENT evidence cannot contain a frame")

        return self
