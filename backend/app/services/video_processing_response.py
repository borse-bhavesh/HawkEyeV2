from pydantic import BaseModel, Field

from app.services.video_processing_status import VideoProcessingStatus


class VideoProcessingResponse(BaseModel):
    """
    API-safe response model for a video-processing operation.
    """

    source: str = Field(min_length=1)

    frames_processed: int = Field(ge=0)

    first_frame_number: int | None = Field(default=None, ge=1)

    last_frame_number: int | None = Field(default=None, ge=1)

    total_frames_read: int = Field(ge=0)
    
    frames_skipped: int = Field(ge=0)

    inference_frames_skipped: int = Field(ge=0, default=0)

    status: VideoProcessingStatus


class AsyncVideoProcessingResponse(BaseModel):
    """
    API-safe response model for an asynchronous video-processing operation.
    """
    session_id: str
    status: VideoProcessingStatus