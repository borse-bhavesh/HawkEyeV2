# ByteTrack Integration Design

## 1. Current Tracking Architecture

The existing HAWKEYE V2 architecture safely isolates object detection and tracking through abstracted pipelines:

    Detection
        ↓
    Tracker
        ↓
    TrackedObject

This architecture completely decouples tracking identities from spatial coordinate extraction, keeping YOLO entirely unaware of temporal logic.

## 2. Selected ByteTrack Approach

We will integrate the **Ultralytics native `BYTETracker`** (`ultralytics.trackers.byte_tracker.BYTETracker`).

## 3. Why It Was Selected

- **Compatibility & Dependencies:** The project already depends on `ultralytics` for YOLOv11. Ultralytics natively implements and ships BoT-SORT and ByteTrack internally. Using their existing ByteTrack class introduces absolutely **zero** new architectural frameworks or third-party tracking packages to `requirements.txt`.
- **Reliability:** The Ultralytics implementation is highly stable, maintained alongside the core YOLO framework, and auto-resolves its own math-binding dependencies (like `lap`).
- **Python 3.12 Compatibility:** Fully supported natively through the existing `ultralytics` ecosystem.
- **CPU/GPU agnostic:** ByteTrack relies on spatial coordinates and Kalman filtering, easily executing efficiently on CPU via NumPy regardless of whether YOLO inference ran on CUDA.
- **Maintainability:** Avoids pulling in parallel overlapping ecosystems like `supervision` or `deep-sort-realtime` merely to provide a mathematical tracker, eliminating conflicting library version constraints.

## 4. Alternatives Considered

- **Supervision (`sv.ByteTrack`)**: Highly elegant and explicitly designed as an agnostic tracking bridge. However, it requires adding another major library dependency (`supervision`) when Ultralytics already contains the required mathematical models.
- **DeepSORT**: Computationally heavier because it requires Re-ID feature embeddings. ByteTrack operates purely on bounding box geometry and confidence scores, which is faster and sufficient for this project phase.
- **BoxMot / Norfair**: Adds significant dependency weight and maintenance overhead compared to utilizing our existing Ultralytics installation.

## 5. Adapter Boundary

To maintain complete dependency inversion, the rest of the application will not interact with Ultralytics outside of the detection or tracking boundary edges. We will build a thin adapter:

    FrameProcessor
          ↓
       Tracker (abstract interface)
          ↓
    ByteTrackTracker (adapter implementation)
          ↓
    ultralytics.trackers.byte_tracker.BYTETracker

## 6. Data Conversion

The `ByteTrackTracker` adapter will silently translate the standard models:

- **Input (`Detection` → ByteTrack input):** The adapter will iterate over `list[Detection]` and pack them into the structural format required by Ultralytics (typically an `(N, 6)` NumPy array/tensor mapped to an `args` namespace or a mocked `Results` container exposing `.boxes`).
- **Output (ByteTrack output → `TrackedObject`):** The tracker's output (usually `STrack` objects containing `[x, y, w, h]`, `track_id`, `score`, and `cls`) will be decoded. The adapter constructs our application-native `TrackedObject` sequence mapping properties like `class_name` back efficiently, ensuring the rest of the app never sees an `STrack`.

## 7. State Management

Unlike `MockTracker` which just increments positionally, the `BYTETracker` is **stateful**. 
- The `ByteTrackTracker` instance will initialize `ultralytics...BYTETracker` exactly once in its constructor.
- The `Tracker` instance will persist in memory for the lifetime of the `FrameProcessor`.
- State will not be reset between frames. The internal Kalman filters and track buffers will persist mathematical momentum automatically.

## 8. Empty Detection Handling

When `detector.detect(frame)` finds zero objects, `tracker.update([])` **must** still be invoked. 
Calling `update([])` is mathematically critical for the tracker to advance its internal clock (`frame_id`), age out stale tracks, increment lost-track counters, and correctly delete objects that have permanently left the frame buffer.

## 9. Configuration

ByteTrack requires tuning parameters that are distinctly different from YOLO confidence thresholds. We will propose a separate Pydantic configuration model:

```python
class TrackingConfig(BaseModel):
    tracker_type: Literal["bytetrack"] = "bytetrack"
    track_high_thresh: float = 0.5
    track_low_thresh: float = 0.1
    new_track_thresh: float = 0.6
    track_buffer: int = 30
    match_thresh: float = 0.8
```
This configuration remains decoupled from `DetectionConfig` and maps perfectly to the `args` namespace expected by `BYTETracker`.

## 10. Future Implementation Plan

Step 4.6B will physically implement the `TrackingConfig`, `ByteTrackTracker` adapter, and associated runtime lifecycle based entirely on this document. No implementation has occurred yet.
