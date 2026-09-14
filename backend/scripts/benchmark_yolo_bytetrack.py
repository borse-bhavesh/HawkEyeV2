import sys
import time
import os
import platform
import statistics
import numpy as np

# Add the backend dir to sys.path so we can import from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import torch
import ultralytics
from app.services.video_stream import VideoStream
from app.services.video_source import LocalVideoSource
from app.services.frame_processor import FrameProcessor
from app.services.detection.yolo_detector import YOLODetector
from app.services.detection.config import DetectionConfig
from app.services.detection.performance_config import DetectionPerformanceConfig
from app.services.tracking.byte_tracker import ByteTrackTracker
from app.services.tracking.config import TrackingConfig
from app.services.video_frame import VideoFrame

def run_benchmark(num_runs=3, max_frames=60, image_size=None, max_inference_fps=None):
    print("==================================================")
    print("HAWKEYE V2 — YOLO + ByteTrack Benchmark")
    print("==================================================")
    
    # Machine Info
    device = "CUDA" if torch.cuda.is_available() else "CPU"
    print(f"Python: {platform.python_version()}")
    print(f"PyTorch: {torch.__version__}")
    print(f"Ultralytics: {ultralytics.__version__}")
    print(f"Model: yolo11n.pt")
    print(f"Device: {device}")
    print(f"Image Size: {image_size if image_size else 'Native'}")
    print(f"Max Inference FPS: {max_inference_fps if max_inference_fps else 'None (Uncapped)'}")
    
    video_path = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "test_video.mp4")
    if not os.path.exists(video_path):
        print(f"[ERROR] Test video not found at {video_path}")
        sys.exit(1)
        
    print(f"\nFrames requested: {max_frames} (per run)")
    print(f"Iterations: {num_runs}\n")

    # WARM UP
    print("--- WARM UP ---")
    warmup_start = time.perf_counter()
    perf_config = DetectionPerformanceConfig(image_size=image_size, max_inference_fps=max_inference_fps)
    detector = YOLODetector(DetectionConfig(model_name="yolo11n.pt"), performance_config=perf_config)
    tracker = ByteTrackTracker(TrackingConfig())
    processor = FrameProcessor(detector=detector, tracker=tracker, performance_config=perf_config, clock=time.perf_counter)
    
    # Run a dummy frame to trigger PyTorch/YOLO/CUDA initializations
    dummy_image = np.zeros((720, 1280, 3), dtype=np.uint8)
    dummy_frame = VideoFrame(frame_number=0, image=dummy_image, timestamp_seconds=0.0)
    detector.detect(dummy_frame)
    warmup_time = time.perf_counter() - warmup_start
    print(f"Warm-up / Initialization Time: {warmup_time:.4f} s\n")

    # BENCHMARK RUNS
    fps_results = []
    time_results = []
    
    final_stats = {}

    for i in range(1, num_runs + 1):
        print(f"--- RUN {i} ---")
        
        # Reset tracking state for a fresh run
        tracker = ByteTrackTracker(TrackingConfig())
        processor = FrameProcessor(detector=detector, tracker=tracker, performance_config=perf_config, clock=time.perf_counter)
        
        run_start = time.perf_counter()
        
        # We must collect exactly how many detections happened.
        # Since FrameProcessor doesn't return raw detection counts, we wrap the detector for stats if needed,
        # OR we just rely on tracker objects? The requirements say:
        # "Count actual Detection objects returned by YOLODetector... Do NOT infer detection counts from tracking output."
        # We can quickly patch the detector instance to count for this run, since FrameProcessor doesn't expose it.
        
        original_detect = detector.detect
        det_count = 0
        frames_with_det = 0
        
        def counting_detect(frame):
            nonlocal det_count, frames_with_det
            dets = original_detect(frame)
            if dets:
                frames_with_det += 1
                det_count += len(dets)
            return dets
            
        detector.detect = counting_detect
        
        stream = VideoStream(LocalVideoSource(video_path))
        with stream:
            result = processor.process(stream, max_frames=max_frames)
            
        run_end = time.perf_counter()
        detector.detect = original_detect  # Restore
        
        run_time = run_end - run_start
        frames_processed = result.frames_processed
        
        frames_skipped = result.frames_skipped
        inference_frames_skipped = result.inference_frames_skipped
        # FPS limit skip is not tracked separately in FrameProcessingResult yet, we infer from total skipping if applicable.
        # Right now we use default FrameProcessor which sets frame_skip=0 and no FPS limit.
        
        effective_fps = frames_processed / run_time if run_time > 0 else 0.0
        fps_results.append(effective_fps)
        time_results.append(run_time)
        
        # Tracking metrics
        tracks_count = 0
        frames_with_tracks = 0
        for frame_tracks in result.tracking_results:
            if frame_tracks:
                frames_with_tracks += 1
                tracks_count += len(frame_tracks)
                
        print(f"Time: {run_time:.4f} s, FPS: {effective_fps:.2f}")
        
        # Keep stats from last run for the report
        if i == num_runs:
            final_stats = {
                "frames_processed": frames_processed,
                "frames_skipped": frames_skipped,
                "det_count": det_count,
                "frames_with_det": frames_with_det,
                "tracks_count": tracks_count,
                "frames_with_tracks": frames_with_tracks,
                "inference_frames_skipped": inference_frames_skipped,
                "tracking_results": result.tracking_results
            }

    print("\n==================================================")
    print("FINAL BENCHMARK REPORT")
    print("==================================================")
    print(f"Model: yolo11n.pt")
    print(f"Ultralytics: {ultralytics.__version__}")
    print(f"PyTorch: {torch.__version__}")
    print(f"Device: {device}")
    print(f"Image Size: {image_size if image_size else 'Native'}")
    print(f"Max Inference FPS: {max_inference_fps if max_inference_fps else 'None (Uncapped)'}")
    
    print(f"\nFrames requested: {max_frames}")
    print(f"Frames processed: {final_stats['frames_processed']}")
    print(f"Frame-skip skipped: {final_stats['frames_skipped']}")
    print(f"FPS-limit skipped: {final_stats['inference_frames_skipped']}")
    
    print(f"\nFrames with detections: {final_stats['frames_with_det']}")
    print(f"Total detections: {final_stats['det_count']}")
    
    print(f"\nFrames with tracks: {final_stats['frames_with_tracks']}")
    print(f"Total tracked observations: {final_stats['tracks_count']}")
    
    avg_fps = statistics.mean(fps_results)
    median_fps = statistics.median(fps_results)
    avg_time = statistics.mean(time_results)
    avg_per_frame_ms = (avg_time / max_frames) * 1000 if max_frames > 0 else 0
    
    print(f"\nWarm-up Time: {warmup_time:.4f} s")
    print(f"Average Processing Time: {avg_time:.4f} s")
    print(f"Average Effective FPS: {avg_fps:.2f} FPS")
    print(f"Median Effective FPS: {median_fps:.2f} FPS")
    print(f"Average frame processing time: {avg_per_frame_ms:.2f} ms")
    
    print("\nPer-run FPS measurements:")
    for idx, fps in enumerate(fps_results):
        print(f"  Run {idx+1}: {fps:.2f} FPS")
        
    print("\n--- TRACKING STABILITY ANALYSIS ---")
    tracking_results = final_stats.get("tracking_results", [])
    num_inference_frames = len(tracking_results)
    print(f"Inference Frames: {num_inference_frames}")
    
    if num_inference_frames > 0:
        track_appearances = {}  # track_id -> list of inference_frame_indices
        
        for frame_idx, frame_tracks in enumerate(tracking_results):
            for t in frame_tracks:
                if t.track_id not in track_appearances:
                    track_appearances[t.track_id] = []
                track_appearances[t.track_id].append(frame_idx)
                
        unique_track_ids = len(track_appearances)
        print(f"Unique Track IDs: {unique_track_ids}")
        
        if unique_track_ids > 0:
            lifetimes = []
            persisted_across_consecutive = 0
            disappeared_reappeared = 0
            
            for tid, frames_seen in track_appearances.items():
                first_seen = frames_seen[0]
                last_seen = frames_seen[-1]
                lifetime = (last_seen - first_seen) + 1
                lifetimes.append(lifetime)
                
                # Check continuity
                is_continuous = True
                for i in range(1, len(frames_seen)):
                    if frames_seen[i] == frames_seen[i-1] + 1:
                        persisted_across_consecutive += 1
                    else:
                        is_continuous = False
                        
                if not is_continuous:
                    disappeared_reappeared += 1

            max_lifetime = max(lifetimes)
            avg_lifetime = sum(lifetimes) / len(lifetimes)
            
            print(f"Max Track Lifetime (inference frames): {max_lifetime}")
            print(f"Avg Track Lifetime (inference frames): {avg_lifetime:.2f}")
            print(f"Continuity (Persisted across consecutive inference frames): {persisted_across_consecutive}")
            print(f"Disappeared and Reappeared: {disappeared_reappeared}")
    
    print("==================================================")

if __name__ == "__main__":
    # You can supply max_frames as a CLI arg for flexibility
    frames = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    imgsz = int(sys.argv[2]) if len(sys.argv) > 2 else None
    inf_fps = float(sys.argv[3]) if len(sys.argv) > 3 else None
    run_benchmark(num_runs=3, max_frames=frames, image_size=imgsz, max_inference_fps=inf_fps)
