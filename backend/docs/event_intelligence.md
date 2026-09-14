# Event Intelligence Design

## 1. Purpose
Event Intelligence acts as the semantic layer above the core tracking infrastructure. Its primary responsibility is to convert sequential observations of physical bounding boxes and object identifiers (`TrackedObject`) into explicit, structured, and explainable **Events**.

## 2. Inputs
The Event Intelligence system receives the following data sequentially over time:
- `frame_number`: The video frame sequence number.
- `timestamp_seconds`: The temporal observation point.
- `tracked_objects`: A list of `TrackedObject` models containing:
  - `track_id`
  - Bounding box coordinates
  - Object class identification
  - Confidence metrics

## 3. Outputs
The system emits explicit `Event` objects. Each `Event` contains:
- Standard metadata (`event_id`, `event_type`, `frame_number`, `timestamp_seconds`)
- `track_id` for track-specific events
- Human-readable `description`
- Highly structured `evidence` answering *what observable facts* triggered the event.

## 4. Candidate Event Taxonomy
**PLANNED — NOT IMPLEMENTED**

- `TRACK_STARTED`: A previously unseen track becomes active.
- `TRACK_ENDED`: A previously active track is no longer observed for the configured lifecycle condition.
- `ZONE_ENTRY`: A tracked object enters a configured surveillance zone.
- `ZONE_EXIT`: A tracked object leaves a configured surveillance zone.
- `LOITERING`: A tracked object remains within a defined area for longer than a configured duration.
- `RAPID_MOVEMENT`: A tracked object's observed position changes faster than a configured threshold.
- `DIRECTION_CHANGE`: A tracked object's movement direction changes significantly.
- `MULTIPLE_OBJECT_PROXIMITY`: Multiple tracked objects remain within a configured spatial distance.

## 5. Explainability Requirements
Every event must be inherently explainable using its `evidence` payload.
For example, if a `LOITERING` event is generated, its evidence dictionary must contain the exact `track_id`, the specific zone identifier, the calculated duration, and the start/end timestamps that crossed the threshold. This provides an audit trail rooted in observable physics.

## 6. Temporal-State Requirements
Many events (e.g., `LOITERING`, `RAPID_MOVEMENT`) require knowledge of the past. Event Intelligence will be **STATEFUL**.
- State must be bound to a unique key (e.g., `track_id`).
- History length should be aggressively bounded to only what is needed to verify temporal thresholds.

## 7. Configuration Philosophy
Event Intelligence relies heavily on deterministic thresholds (e.g., `loitering_duration_seconds=30.0`). These values are defined in a highly structured, strongly typed Pydantic configuration (`EventIntelligenceConfig`). They are completely isolated from global application settings during this initial phase to preserve modularity.

## 8. Separation from Detection/Tracking
The `EventEngine` acts as an agnostic consumer of `TrackedObject`. It does **not** contain any YOLO/ByteTrack logic, and it operates entirely unaware of how the tracking observations were generated. The architecture enforces dependency inversion.

## 9. Separation from Risk Scoring
Events describe **observable behavior, not intent.**
Event Intelligence determines *that* an object loitered for 45 seconds. It does **not** assign a "risk score" to this behavior, nor does it deduce if the behavior is dangerous. Priority, alert generation, and risk calculation belong strictly to Step 6 and downstream services.

## 10. Track History / Temporal State
Track History is a dedicated component (`TrackHistory`) responsible for storing bounded, deterministic, chronological sequences of `TrackObservation` data keyed by `track_id`.

**Key Principles:**
- **Observation Only**: Track History stores observations; it does not interpret behavior, calculate risk, or decide when a track is dead.
- **Bounded Retention**: To prevent unbounded memory growth, each track maintains a maximum number of observations (`max_observations_per_track`), implemented via a high-performance `deque`.
- **Chronological Strictness**: Observations are guaranteed to be in temporal order. Supplying out-of-order temporal data (regression in frame number or timestamp) is actively rejected.
- **Immutability & Isolation**: Defensive copying prevents callers from mutating internal state or accidentally modifying shared tracking payloads. Histories of different tracks are completely isolated.
- **Future Integration**: The `EventEngine` will query `TrackHistory` to run sliding-window calculations (like measuring how long an object has stayed within a bounding area for `LOITERING`).

## 11. Track Lifecycle Events
The `LifecycleEngine` implements the `EventEngine` interface specifically to generate `TRACK_STARTED` and `TRACK_ENDED` events. 
It processes sequential tracking frames to determine the active lifecycle of objects.

**Key Behaviors:**
- **TRACK_STARTED**: Emitted deterministically the very first time a `track_id` is observed by the engine. It contains the exact temporal context of the initial discovery.
- **Absence vs. Ended**: A track "disappearing" from a single frame is common due to occlusion or detection dropout. Therefore, a track does not immediately end when absent. 
- **Grace Period Policy**: The lifecycle state employs a `track_end_grace_frames` policy. An active track is only marked as ended if it remains continuously absent for a number of frames exceeding this grace configuration.
- **TRACK_ENDED**: Emitted exactly once when the grace period is violated. It contains structured evidence detailing the exact frame it was last seen.
- **Reappearance**: If an object disappears but reappears *before* the grace period expires, its active lifecycle is simply preserved. No new events are emitted. If it reappears *after* `TRACK_ENDED` was emitted, it is considered a brand new lifecycle and a new `TRACK_STARTED` event is emitted.
- **Event Ordering**: Events are processed and emitted in ascending `track_id` order to ensure deterministic behavior across identical inputs.
- **Resetting Boundaries**: The engine provides a `reset()` method to clear internal state. This is critical for session boundaries (e.g., when switching to a completely new video feed).

## 12. Spatial Zones
The `zones` module provides the foundational spatial model for calculating area-based behaviors. Zone geometry determines spatial membership. It does **not** generate events.

**Key Principles:**
- **Image-Space Coordinate System**: Zones are defined using coordinates mapped directly to the video frame (origin at top-left, x increases to the right, y increases downward). These are *not* geographic/GPS coordinates.
- **`Zone` and `Point2D`**: Regions are represented by the `Zone` model, containing a validated polygon (minimum 3 points). Vertices are typed `Point2D`.
- **Reference-Point Convention**: Bounding boxes are not evaluated as entire areas. The engine calculates a deterministic representative point using the `BOTTOM_CENTER` rule: `x = (x1 + x2) / 2, y = y2`. This effectively approximates the physical point where the object touches the ground.
- **Point-in-Polygon Algorithm**: Uses a deterministic Ray-Casting algorithm. It does not introduce heavy external geometry libraries.
- **Boundary Policy**: INCLUSIVE. A reference point lying exactly on a polygon boundary segment or vertex is strictly considered inside the zone.
- **Event Separation**: The zones module evaluates `is_point_inside_zone() -> bool`. It is completely stateless and unaware of temporal trends. A future EventEngine component will compare membership boolean values across frames to deduce state changes like `ZONE_ENTRY`.

## 13. Zone Transition Events
The `ZoneEngine` tracks objects over time to identify definitive spatial transitions, specifically `ZONE_ENTRY` and `ZONE_EXIT`.

**Key Behaviors:**
- **Initial Membership Policy**: The very first time a track is observed relative to a zone, its membership is recorded but **no event is emitted**. This prevents the system from falsely emitting a `ZONE_ENTRY` event for an object that simply appeared natively inside a zone (e.g. tracking just started).
- **ZONE_ENTRY**: Emitted deterministically when a track transitions strictly from `OUTSIDE` to `INSIDE`. This means the system actually observed a boundary crossing.
- **ZONE_EXIT**: Emitted deterministically when a track transitions strictly from `INSIDE` to `OUTSIDE`.
- **Multiple Tracks & Zones**: State is keyed by `(track_id, zone_id)`. Tracks and zones operate entirely independently. A track can enter Zone A without affecting its status in Zone B.
- **Temporary Disappearance**: A track disappearing from the camera feed does not trigger a `ZONE_EXIT`. The `ZoneEngine` strictly relies on observed bounding boxes. Lifecycle ends are managed elsewhere.
- **Boundary Behavior**: Follows the `zones` module inclusive boundary policy. Crossing exactly onto the geometric boundary line constitutes an `INSIDE` state.
- **Reset and State Lifecycle**: A `reset()` method completely clears the engine. A `remove_track(track_id)` method permits upstream lifecycle controllers to explicitly free memory when a track definitively ends.
- **Deterministic Ordering**: Event lists are sorted by `track_id` and then `zone_id` before emission, guaranteeing identical sequences for identical multi-track updates.

## 14. Loitering Detection
The `LoiteringEngine` tracks the continuous spatial presence of an object inside a zone.

**Key Behaviors:**
- **Definition**: LOITERING represents observed continuous presence in a configured area for at least the configured duration. It does not imply intent or suspicious behavior.
- **Timestamp-Based Duration**: Duration is calculated using `current_timestamp - first_inside_timestamp`. It is immune to variable frame rates or frame dropping.
- **First-Observation Policy**: If an object is already inside a zone when the engine starts observing it, the timer begins at that exact moment. The engine does not assume the object was there prior to observation.
- **Threshold Behavior**: A `LOITERING` event is emitted on the exact frame where `observed_duration >= configured_threshold`.
- **Duplicate Suppression**: Only one event is emitted per continuous presence interval. Staying in the zone after the event is emitted does not generate spam.
- **Leaving/Re-entry Behavior**: An explicit observation of an object transitioning to `OUTSIDE` definitively ends the continuous presence interval and resets the timer. If it re-enters, a new timer begins.
- **Temporary Disappearance**: Handled gracefully. If an object temporarily disappears due to occlusion, the timer is NOT reset. The engine relies purely on explicitly observed geometry or definitive lifecycle ends.
- **Multiple Tracks & Zones**: Track and zone states are completely isolated using a `(track_id, zone_id)` tuple.
- **Event Evidence**: Contains factual metrics: `presence_start_timestamp`, `current_timestamp`, `observed_duration_seconds`, and `configured_threshold_seconds`.
- **State Cleanup**: A `reset()` method clears all tracking state, while `remove_track(track_id)` cleanly handles memory garbage collection when tracks reach end-of-life upstream.

## 15. Rapid Movement Detection
The `RapidMovementEngine` identifies objects moving through the image plane at speeds equal to or exceeding a configured threshold.

**Key Behaviors:**
- **Definition**: `RAPID_MOVEMENT` represents an observed image-plane movement rate at or above the configured threshold. It is NOT a physical velocity measurement (meters/second) and does not imply intent or suspicious behavior.
- **Reference Point**: Movement is calculated exclusively using the `BOTTOM_CENTER` image coordinate of the bounding box.
- **Speed Calculation**: Observed speed is calculated using Euclidean distance divided by elapsed time (`distance / delta_t`).
- **Timestamp-Based**: Because speed relies strictly on timestamp deltas rather than frame counts, the calculation remains robust and mathematically accurate even if frames are aggressively skipped.
- **First-Observation Policy**: The first observation of an object merely establishes its baseline coordinate. A speed cannot be calculated without a previous point, so no event is generated.
- **Duplicate Suppression**: A continuous interval of high-speed movement yields exactly one `RAPID_MOVEMENT` event. Duplicate events are strictly suppressed while the state remains rapid.
- **Rapid → Slow Reset**: The rapid state is cleared immediately when an observed speed drops below the threshold. If the object accelerates again, a new event is emitted.
- **Temporary Disappearance**: The state survives temporary absence. When the object reappears, its speed is calculated against its last valid coordinate and the full elapsed time interval.
- **State Cleanup**: A `reset()` method clears all tracking state, and `remove_track(track_id)` cleanly handles upstream lifecycle ends.
- **Deterministic Ordering**: Event lists are sorted by `track_id` before emission, guaranteeing identical sequences for identical multi-track updates.

## 16. Direction Change Detection
The `DirectionChangeEngine` identifies when an object's image-plane movement direction changes by an angle equal to or exceeding a configured threshold.

**Key Behaviors:**
- **Definition**: `DIRECTION_CHANGE` represents an observed change in image-plane movement direction by at least the configured angular threshold. This is an image-plane directional measurement and does not represent intent or physical navigation behavior.
- **Reference Point**: Movement is calculated exclusively using the `BOTTOM_CENTER` image coordinate of the bounding box.
- **Movement Vector**: Calculated as the difference between consecutive valid reference points (`dx`, `dy`).
- **Angle Calculation**: Direction is calculated using `atan2(dy, dx)`, converted to degrees, and normalized to the range `[0°, 360°)`. Note that because the image y-axis increases downward, this angle is strictly an image-plane coordinate system value.
- **Smallest Angular Difference**: Comparisons between previous and current directions strictly evaluate the absolute shortest angular distance `[0°, 180°]` (e.g., `10°` to `350°` yields `20°`).
- **Threshold Behavior**: An event is emitted if the absolute angular difference is `>=` the configured threshold.
- **First-Observation Policy**: The first observation simply establishes an initial point. The second observation establishes the first directional vector. Therefore, a minimum of three observations are required to detect a direction transition (two consecutive movement vectors).
- **Stationary Observations**: A zero-displacement vector `(dx=0, dy=0)` cannot produce a mathematically sound direction angle. The engine securely updates the temporal/spatial marker to maintain continuous track history but bypasses directional calculations, avoiding math errors and fake headings.
- **Duplicate Suppression**: Events represent distinct transitions between consecutive directional vectors. Subsequent vectors must again exceed the threshold relative to their immediate predecessor to generate a new event.
- **Temporary Disappearance**: The engine safely preserves directional state when an object disappears, calculating the next vector accurately against its last known valid coordinate upon reappearance.
- **Timestamp Ordering**: Out-of-order timestamps are safely ignored to prevent invalid sequences.
- **State Cleanup**: `reset()` clears all internal tracking state, and `remove_track(track_id)` efficiently reclaims memory when upstream processes terminate tracks.
- **Deterministic Ordering**: Event lists are sorted by `track_id` before emission, guaranteeing identical event streams for identical inputs.

## 17. Multiple-Object Proximity Detection
The `ProximityEngine` detects when two simultaneously observed tracked objects transition to being within a configured spatial distance threshold.

**Key Behaviors:**
- **Definition**: `MULTIPLE_OBJECT_PROXIMITY` represents an observed spatial relationship in which two tracked objects are within the configured image-plane distance threshold. The event does not establish interaction, coordination, intent, or suspicious behavior.
- **Reference Point**: Distance is calculated exclusively using the Euclidean distance between the `BOTTOM_CENTER` image coordinates of the bounding boxes.
- **Pairwise Evaluation**: Operates pairwise. For $N$ objects, $N(N-1)/2$ unique canonical pairs are evaluated. Duplicate `(A,A)` and redundant `(B,A)` combinations are strictly forbidden.
- **Canonical Pair Ordering**: Assures lexicographically ordered pairs `(min_id, max_id)` to maintain absolute determinism across identical input sequences.
- **First-Observation Policy**: The very first time a pair is observed within the threshold, state is initialized silently without generating an event, establishing a chronological baseline and preventing immediate false-entry noise.
- **Proximity Transition**: Events exclusively model the transition from `OUTSIDE` to `INSIDE` threshold. Prolonged proximity does not emit subsequent duplicate events.
- **Separation/Re-entry**: Crossing strictly beyond the threshold `(distance > threshold)` resets the state cleanly without broadcasting an event. If the pair later returns `INSIDE`, a distinct new event is generated.
- **Temporary Disappearance**: The engine safely bypasses calculation if one pair member vanishes. The previously established proximity state correctly survives the temporal void until reappearance, preventing false resets.
- **Multiple Objects**: Strictly limited to pairing. If three objects cluster, three separate independent pair events `(A,B)`, `(B,C)`, `(A,C)` are generated. Clustering and group abstractions are explicitly rejected.
- **Memory Bounds**: Engineered at exactly $O(N_\text{pairs})$ maximum memory load, avoiding massive frame or trajectory caching loops.
- **Lifecycle Cleanup**: `remove_track(track_id)` accurately locates and purges all pairwise states involving that entity, preserving independent relationships.
- **Duplicate Track-ID Policy**: Any tracked frame containing two identically named `track_id` objects deterministically processes only the first occurrence, rejecting the duplicate iteration to safeguard logic loops.

## 18. Future Implementation Plan
1. Wire the `EventEngine` pipeline into the `FrameProcessor` so events can be passed out alongside standard tracking results.
