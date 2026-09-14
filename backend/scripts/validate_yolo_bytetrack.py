import sys
import time
import os
from collections import defaultdict
import torch

# Add the backend dir to sys.path so we can import from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import ultralytics
from app.services.video_stream import VideoStream
from app.services.video_source import LocalVideoSource
from app.services.frame_processor import FrameProcessor
from app.services.detection.yolo_detector import YOLODetector
from app.services.detection.config import DetectionConfig
from app.services.tracking.byte_tracker import ByteTrackTracker
from app.services.tracking.config import TrackingConfig

def run_validation():
    print("==================================================")
    print("HAWKEYE V2 - YOLO to ByteTrack End-to-End Validation")
    print("==================================================")

    # Detect Device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[ENV] Ultralytics version: {ultralytics.__version__}")
    print(f"[ENV] PyTorch Device: {device}")
    
    # 1. Paths
    video_path = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "test_video.mp4")
    if not os.path.exists(video_path):
        print(f"[ERROR] Test video not found at {video_path}")
        sys.exit(1)
    
    print(f"[ENV] Video Fixture: {video_path}")
    print(f"[ENV] YOLO Model: yolo11n.pt")

    # 2. Components
    detector = YOLODetector(DetectionConfig(model_name="yolo11n.pt"))
    tracker = ByteTrackTracker(TrackingConfig())
    processor = FrameProcessor(detector=detector, tracker=tracker)
    stream = VideoStream(LocalVideoSource(video_path))

    max_frames_to_process = 60
    print(f"[RUN] Starting processing up to {max_frames_to_process} frames...")

    start_time = time.perf_counter()

    try:
        with stream:
            result = processor.process(stream, max_frames=max_frames_to_process)
    except Exception as e:
        print(f"[ERROR] Pipeline crashed: {e}")
        sys.exit(1)

    end_time = time.perf_counter()
    processing_time = end_time - start_time

    # 3. Validation Metrics
    frames_processed = result.frames_processed
    tracking_results = result.tracking_results
    
    frames_with_detections = 0 # Not explicitly logged by frame processor, but we can derive from tracked objects
    frames_with_tracks = 0
    total_tracked_objects_observed = 0
    unique_track_ids = set()
    
    track_id_history = defaultdict(list)
    empty_detection_frames_reached_tracker = 0
    
    for frame_idx, tracks in enumerate(tracking_results):
        if len(tracks) > 0:
            frames_with_tracks += 1
            total_tracked_objects_observed += len(tracks)
            # Detections existed if we had tracks (ByteTrack handles internal missing tracks if buffer is used, but typically 
            # objects are actively matched)
            frames_with_detections += 1
            
            for t in tracks:
                unique_track_ids.add(t.track_id)
                track_id_history[t.track_id].append(frame_idx)
        else:
            empty_detection_frames_reached_tracker += 1

    # Analysis of persistence
    max_persistence = 0
    persistent_tracks = 0
    for tid, frames in track_id_history.items():
        if len(frames) > 1:
            persistent_tracks += 1
            # Check sequential persistence
            run_length = 1
            for i in range(1, len(frames)):
                if frames[i] == frames[i-1] + 1:
                    run_length += 1
                else:
                    if run_length > max_persistence:
                        max_persistence = run_length
                    run_length = 1
            if run_length > max_persistence:
                max_persistence = run_length

    effective_fps = frames_processed / processing_time if processing_time > 0 else 0.0

    print("==================================================")
    print("RESULTS")
    print("==================================================")
    print(f"Frames Processed                 : {frames_processed}")
    print(f"Frames with Tracks Output        : {frames_with_tracks}")
    print(f"Empty Track Output Frames        : {empty_detection_frames_reached_tracker}")
    print(f"Total Tracked Objects Emitted    : {total_tracked_objects_observed}")
    print(f"Unique Track IDs Observed        : {len(unique_track_ids)}")
    print(f"Tracking Results Array Alignment : {len(tracking_results)} == {frames_processed} -> {len(tracking_results) == frames_processed}")
    print(f"Valid TrackedObjects produced?   : {'Yes' if total_tracked_objects_observed > 0 else 'N/A'}")
    print(f"Multiple objects tracked?        : {'Yes' if len(unique_track_ids) > 1 else 'No'}")
    print(f"Temporal Persistence?            : {'Yes' if persistent_tracks > 0 else 'No'} (Max consecutive frames: {max_persistence})")
    print(f"Total Time                       : {processing_time:.2f} seconds")
    print(f"Effective Pipeline FPS           : {effective_fps:.2f} FPS")
    print("==================================================")

    # Validate strict conditions
    if len(tracking_results) != frames_processed:
        print("[FAIL] Tracking results array does not align with processed frames!")
        sys.exit(1)

    if not isinstance(result.tracking_results, list):
        print("[FAIL] Output is not a clean list!")
        sys.exit(1)
        
    for frame_tracks in result.tracking_results:
        for t in frame_tracks:
            from app.services.tracking.models import TrackedObject
            if not isinstance(t, TrackedObject):
                print(f"[FAIL] Pipeline leaked non-native object: {type(t)}")
                sys.exit(1)
            # verify structural data
            if t.track_id < 0 or t.confidence < 0 or t.confidence > 1.0 or not t.class_name:
                print(f"[FAIL] Invalid structural properties on TrackedObject: {t}")
                sys.exit(1)

    print("[SUCCESS] Pipeline is structurally valid and leakage-free.")
    sys.exit(0)

if __name__ == "__main__":
    run_validation()
