import re
from pathlib import Path
import cv2
from pydantic import BaseModel, Field

from app.services.video_frame import VideoFrame
from app.services.evidence.models import Evidence, EvidenceType

class EvidenceSourceVideoNotFoundError(Exception):
    pass

class EvidenceVideoOpenError(Exception):
    pass

class EvidenceVideoWriterError(Exception):
    pass

class EvidenceSegmentMaterializationError(Exception):
    pass

class MaterializedEvidence(BaseModel):
    """Metadata describing a materialized evidence media file."""
    evidence_id: str = Field(...)
    evidence_type: EvidenceType = Field(...)
    path: str = Field(...)
    frame_number: int = Field(...)
    timestamp_seconds: float = Field(...)

class MaterializedVideoSegmentEvidence(BaseModel):
    """Metadata describing a materialized video segment evidence file."""
    evidence_id: str = Field(...)
    evidence_type: EvidenceType = Field(...)
    path: str = Field(...)
    start_frame: int = Field(...)
    end_frame: int = Field(...)
    start_timestamp_seconds: float = Field(...)
    end_timestamp_seconds: float = Field(...)

class EvidenceMediaMaterializer:
    """
    Step 7.3 component responsible for materializing a FrameEvidence reference 
    into an actual local image file deterministically during development.
    """
    
    def __init__(self, output_directory: str | Path):
        if not output_directory:
            raise ValueError("Output directory cannot be empty")
        # .resolve() is used to ensure absolute path
        self.output_directory = Path(output_directory).resolve()
        
    def _validate_source_id(self, source_id: str) -> None:
        """Ensure source_id cannot perform path traversal."""
        if not re.match(r'^[\w\-]+$', source_id):
            raise ValueError("Invalid source_id: contains invalid characters or traversal attempts")
        
    def materialize_frame(self, video_frame: VideoFrame, evidence: Evidence) -> MaterializedEvidence:
        if video_frame is None:
            raise ValueError("video_frame cannot be None")
        if evidence is None:
            raise ValueError("evidence cannot be None")
            
        if evidence.evidence_type != EvidenceType.FRAME:
            raise ValueError("Evidence must be of type FRAME")
            
        if not evidence.frame:
            raise ValueError("Evidence does not contain a frame reference")
            
        if evidence.frame.frame_number != video_frame.frame_number:
            raise ValueError("Frame number mismatch between evidence and video frame")
            
        if evidence.frame.timestamp_seconds != video_frame.timestamp_seconds:
            raise ValueError("Timestamp mismatch between evidence and video frame")
            
        source_id = evidence.source.source_id
        self._validate_source_id(source_id)
            
        target_dir = self.output_directory / "frames" / source_id
        
        # Double check traversal
        try:
            target_dir.resolve().relative_to(self.output_directory)
        except ValueError:
            raise ValueError("Path traversal detected")
            
        target_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"frame_{video_frame.frame_number}.jpg"
        target_path = target_dir / filename
        
        success = cv2.imwrite(str(target_path), video_frame.image)
        if not success:
            raise RuntimeError("Failed to write image using cv2.imwrite")
            
        return MaterializedEvidence(
            evidence_id=evidence.evidence_id,
            evidence_type=EvidenceType.FRAME,
            path=str(target_path),
            frame_number=video_frame.frame_number,
            timestamp_seconds=video_frame.timestamp_seconds
        )

    def materialize_video_segment(
        self,
        video_source: Path | str,
        evidence: Evidence,
        source_id: str
    ) -> MaterializedVideoSegmentEvidence:
        if evidence is None:
            raise ValueError("evidence cannot be None")
        if evidence.evidence_type != EvidenceType.VIDEO_SEGMENT:
            raise ValueError("Evidence must be of type VIDEO_SEGMENT")
        if not evidence.video_segment:
            raise ValueError("Evidence does not contain a video segment reference")
            
        segment = evidence.video_segment
        if segment.start_frame_number < 0 or segment.end_frame_number < 0:
            raise ValueError("Invalid frame bounds")
        if segment.end_frame_number < segment.start_frame_number:
            raise ValueError("end_frame must be >= start_frame")
            
        self._validate_source_id(source_id)
        
        source_path = Path(video_source)
        if not source_path.exists():
            raise EvidenceSourceVideoNotFoundError(f"Source video not found: {source_path}")
        if not source_path.is_file():
            raise ValueError(f"Source video is not a file: {source_path}")
            
        target_dir = self.output_directory / "segments" / source_id
        
        try:
            target_dir.resolve().relative_to(self.output_directory)
        except ValueError:
            raise ValueError("Path traversal detected")
            
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = f"segment_{segment.start_frame_number}_{segment.end_frame_number}.mp4"
        target_path = target_dir / filename
        temp_target_path = target_path.with_suffix(".tmp.mp4")
        
        cap = cv2.VideoCapture(str(source_path))
        if not cap.isOpened():
            raise EvidenceVideoOpenError(f"OpenCV could not open source video: {source_path}")
            
        out = None
        success = False
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0 or not isinstance(fps, (int, float)):
                raise ValueError("Source video has invalid or missing FPS")
                
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, segment.start_frame_number)
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(temp_target_path), fourcc, fps, (width, height))
            
            if not out.isOpened():
                raise EvidenceVideoWriterError("OpenCV could not open VideoWriter")
                
            expected_frames = segment.end_frame_number - segment.start_frame_number + 1
            actual_written = 0
            
            for _ in range(expected_frames):
                ret, frame = cap.read()
                if not ret:
                    raise EvidenceSegmentMaterializationError("Failed to read required frame from source video")
                out.write(frame)
                actual_written += 1
                
            if actual_written != expected_frames:
                raise EvidenceSegmentMaterializationError("Mismatch between expected and written frames")
                
            success = True
        finally:
            cap.release()
            if out is not None:
                out.release()
                
            if not success and temp_target_path.exists():
                temp_target_path.unlink()
                
        if success:
            temp_target_path.replace(target_path)
            
        return MaterializedVideoSegmentEvidence(
            evidence_id=evidence.evidence_id,
            evidence_type=EvidenceType.VIDEO_SEGMENT,
            path=str(target_path),
            start_frame=segment.start_frame_number,
            end_frame=segment.end_frame_number,
            start_timestamp_seconds=segment.start_timestamp_seconds,
            end_timestamp_seconds=segment.end_timestamp_seconds
        )
