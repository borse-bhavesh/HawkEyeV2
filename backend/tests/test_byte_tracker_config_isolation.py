
import pytest
from app.services.tracking.config import TrackingConfig
from app.services.tracking.byte_tracker import ByteTrackTracker

# 6. Supplied configuration reaches BYTETracker.
# 7. Configuration values are mapped to the correct Ultralytics args.
# 8. fuse_score is mapped correctly.
# 9. ByteTrackTracker does not silently replace supplied configuration values with unrelated hard-coded values.
def test_configuration_reaches_underlying_tracker():
    config = TrackingConfig(
        track_high_thresh=0.7,
        track_low_thresh=0.2,
        new_track_thresh=0.8,
        track_buffer=45,
        match_thresh=0.9,
        fuse_score=False
    )
    tracker = ByteTrackTracker(config=config)
    
    internal_args = tracker._tracker.args
    assert internal_args.track_high_thresh == 0.7
    assert internal_args.track_low_thresh == 0.2
    assert internal_args.new_track_thresh == 0.8
    assert internal_args.track_buffer == 45
    assert internal_args.match_thresh == 0.9
    assert internal_args.fuse_score is False
    assert internal_args.gmc_method == "sparseOptFlow"

# 12. Two ByteTrackTracker instances can be created with different TrackingConfig values.
# 13. Configuration of one tracker does not mutate another tracker.
def test_tracker_configuration_isolation():
    config1 = TrackingConfig(track_buffer=20, fuse_score=True)
    tracker1 = ByteTrackTracker(config=config1)
    
    config2 = TrackingConfig(track_buffer=50, fuse_score=False)
    tracker2 = ByteTrackTracker(config=config2)
    
    # Verify different internal states
    assert tracker1._tracker.args.track_buffer == 20
    assert tracker1._tracker.args.fuse_score is True
    
    assert tracker2._tracker.args.track_buffer == 50
    assert tracker2._tracker.args.fuse_score is False
    
    # Verify modifying config instance does not leak backwards to mutate tracker args
    # (Because args are copied into a SimpleNamespace at initialization)
    config1.track_buffer = 99
    assert tracker1._tracker.args.track_buffer == 20

# 10. DetectionConfig remains independent.
# 11. DetectionPerformanceConfig remains independent.
def test_detection_config_independence():
    from app.services.detection.config import DetectionConfig
    from app.services.detection.performance_config import DetectionPerformanceConfig
    
    # Creating tracking config should not require detection imports or fields
    config = TrackingConfig()
    
    # Neither TrackingConfig nor its instantiated model should contain detection properties
    assert not hasattr(config, "model_name")
    assert not hasattr(config, "device")
    assert not hasattr(config, "max_inference_fps")
    
    # Creating detection config should not contain tracking properties
    det_config = DetectionConfig(model_name="yolov8n.pt")
    assert not hasattr(det_config, "track_buffer")
    assert not hasattr(det_config, "fuse_score")
    
    det_perf_config = DetectionPerformanceConfig()
    assert not hasattr(det_perf_config, "track_buffer")
