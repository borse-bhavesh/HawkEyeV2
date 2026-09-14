from app.services.video_frame import VideoFrame
from app.services.evidence.models import FrameEvidence

class EvidenceCapture:
    """
    Stateless component to capture Evidence metadata from a VideoFrame.
    This component purely translates processing representations to evidence references.
    It does NOT extract physical images, create JPEGs, or interact with storage.
    """
    
    @staticmethod
    def capture_frame(video_frame: VideoFrame) -> FrameEvidence:
        """
        Extract deterministic frame metadata from an existing VideoFrame.
        Does not copy or embed the actual image array.
        """
        if video_frame is None:
            raise ValueError("video_frame cannot be None")
            
        # We deliberately drop the .image array to satisfy the Evidence contract.
        return FrameEvidence(
            frame_number=video_frame.frame_number,
            timestamp_seconds=video_frame.timestamp_seconds
        )
