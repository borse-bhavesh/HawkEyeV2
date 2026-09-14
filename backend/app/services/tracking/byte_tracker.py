import torch
import numpy as np
from typing import Mapping
from types import SimpleNamespace
from ultralytics.trackers.byte_tracker import BYTETracker
from ultralytics.engine.results import Boxes

from app.services.tracking.tracker import Tracker
from app.services.tracking.models import TrackedObject
from app.services.detection.models import Detection, BoundingBox
from app.services.tracking.config import TrackingConfig


class ByteTrackTracker(Tracker):
    """
    Adapter bridging our application-specific Tracker abstraction with
    the external Ultralytics BYTETracker implementation.
    
    This tracker is stateful and must be reused across frames.
    """
    def __init__(
        self,
        config: TrackingConfig,
        class_names: Mapping[int, str] | None = None
    ):
        self.config = config
        self.class_names = class_names if class_names is not None else {}
        
        # Translate the Pydantic config into the SimpleNamespace required by Ultralytics
        args = SimpleNamespace(
            track_high_thresh=config.track_high_thresh,
            track_low_thresh=config.track_low_thresh,
            new_track_thresh=config.new_track_thresh,
            track_buffer=config.track_buffer,
            match_thresh=config.match_thresh,
            gmc_method="sparseOptFlow",  # default internal mechanism
            fuse_score=config.fuse_score
        )
        # Instantiate stateful tracker exactly once per adapter
        self._tracker = BYTETracker(args)

    def update(self, detections: list[Detection]) -> list[TrackedObject]:
        """
        Processes normalized Detections, updates stateful ByteTrack,
        and returns normalized TrackedObjects.
        """
        # 1. Convert Input: Detection -> Ultralytics Boxes
        if not detections:
            boxes = Boxes(torch.empty((0, 6)), orig_shape=(1000, 1000))
        else:
            data = []
            for det in detections:
                data.append([
                    det.bounding_box.x1,
                    det.bounding_box.y1,
                    det.bounding_box.x2,
                    det.bounding_box.y2,
                    det.confidence,
                    det.class_id
                ])
            # orig_shape prevents scaling issues internally inside Boxes if used for plotting, 
            # but tracking math simply consumes the tensor correctly.
            boxes = Boxes(torch.tensor(data), orig_shape=(1000, 1000))
            
        # 2. Execute tracking math
        tracks = self._tracker.update(boxes)
        
        # 3. Convert Output: numpy array -> list[TrackedObject]
        tracked_objects = []
        if len(tracks) == 0:
            return tracked_objects
            
        # Ensure it behaves reliably as a 2D array if there's exactly 1 track
        if len(tracks.shape) == 1:
            tracks = np.expand_dims(tracks, axis=0)
            
        for row in tracks:
            # BYTETracker outputs: [x1, y1, x2, y2, track_id, score, cls, idx]
            x1, y1, x2, y2, track_id, score, cls_id, _ = row
            cls_id_int = int(cls_id)
            
            # Use deterministic fallback for missing mappings
            class_name = self.class_names.get(cls_id_int, f"class_{cls_id_int}")
            
            tracked_objects.append(
                TrackedObject(
                    track_id=int(track_id),
                    class_id=cls_id_int,
                    class_name=class_name,
                    confidence=float(score),
                    bounding_box=BoundingBox(
                        x1=float(x1),
                        y1=float(y1),
                        x2=float(x2),
                        y2=float(y2)
                    )
                )
            )
            
        return tracked_objects
