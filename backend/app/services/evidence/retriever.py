import re
from pathlib import Path

from app.services.evidence.models import Evidence, EvidenceType
from app.services.evidence.materializer import MaterializedEvidence, MaterializedVideoSegmentEvidence


class EvidenceMediaNotFoundError(Exception):
    """Exception raised when materialized evidence cannot be found on the filesystem."""
    pass


class EvidenceMediaRetriever:
    """
    Step 7.4 component responsible for safely locating a materialized
    frame evidence file on the local filesystem.
    """
    
    def __init__(self, output_directory: str | Path):
        if not output_directory:
            raise ValueError("Output directory cannot be empty")
        self.output_directory = Path(output_directory).resolve()
        
    def _validate_source_id(self, source_id: str) -> None:
        """Ensure source_id cannot perform path traversal."""
        if not source_id:
            raise ValueError("source_id cannot be empty")
        if not re.match(r'^[\w\-]+$', source_id):
            raise ValueError("Invalid source_id: contains invalid characters or traversal attempts")
        
    def retrieve_frame(self, evidence: Evidence) -> MaterializedEvidence:
        """
        Safely locate the local media file corresponding to this FrameEvidence.
        """
        if evidence is None:
            raise ValueError("evidence cannot be None")
            
        if evidence.evidence_type != EvidenceType.FRAME:
            raise ValueError("Evidence must be of type FRAME")
            
        if not evidence.frame:
            raise ValueError("Evidence does not contain a frame reference")
            
        if evidence.frame.frame_number < 0:
            raise ValueError("Invalid frame number")
            
        source_id = evidence.source.source_id
        self._validate_source_id(source_id)
            
        target_dir = self.output_directory / "frames" / source_id
        
        # Double check traversal
        try:
            target_dir.resolve().relative_to(self.output_directory)
        except ValueError:
            raise ValueError("Path traversal detected")
            
        filename = f"frame_{evidence.frame.frame_number}.jpg"
        target_path = target_dir / filename
        resolved_path = target_path.resolve()
        
        # Ensure the final resolved path (after any potential symlinks) remains in output_directory
        try:
            resolved_path.relative_to(self.output_directory)
        except ValueError:
            raise ValueError("Resolved path escapes the configured evidence root")
            
        if not resolved_path.exists():
            raise EvidenceMediaNotFoundError(f"Evidence file not found: {resolved_path}")
            
        if not resolved_path.is_file():
            raise ValueError(f"Evidence path is a directory masquerading as a file: {resolved_path}")
            
        return MaterializedEvidence(
            evidence_id=evidence.evidence_id,
            evidence_type=EvidenceType.FRAME,
            path=str(resolved_path),
            frame_number=evidence.frame.frame_number,
            timestamp_seconds=evidence.frame.timestamp_seconds
        )

    def retrieve_video_segment(self, evidence: Evidence) -> MaterializedVideoSegmentEvidence:
        """
        Safely locate the local media file corresponding to this VideoSegmentEvidence.
        """
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
            
        source_id = evidence.source.source_id
        self._validate_source_id(source_id)
            
        target_dir = self.output_directory / "segments" / source_id
        
        # Double check traversal
        try:
            target_dir.resolve().relative_to(self.output_directory)
        except ValueError:
            raise ValueError("Path traversal detected")
            
        filename = f"segment_{segment.start_frame_number}_{segment.end_frame_number}.mp4"
        target_path = target_dir / filename
        resolved_path = target_path.resolve()
        
        # Ensure the final resolved path (after any potential symlinks) remains in output_directory
        try:
            resolved_path.relative_to(self.output_directory)
        except ValueError:
            raise ValueError("Resolved path escapes the configured evidence root")
            
        if not resolved_path.exists():
            raise EvidenceMediaNotFoundError(f"Evidence file not found: {resolved_path}")
            
        if not resolved_path.is_file():
            raise ValueError(f"Evidence path is a directory masquerading as a file: {resolved_path}")
            
        return MaterializedVideoSegmentEvidence(
            evidence_id=evidence.evidence_id,
            evidence_type=EvidenceType.VIDEO_SEGMENT,
            path=str(resolved_path),
            start_frame=segment.start_frame_number,
            end_frame=segment.end_frame_number,
            start_timestamp_seconds=segment.start_timestamp_seconds,
            end_timestamp_seconds=segment.end_timestamp_seconds
        )
