import uuid
from typing import Dict, List, Optional
from pydantic import BaseModel
from app.services.events.event_engine import EventEngine
from app.services.events.models import Event, EventType
from app.services.events.config import EventIntelligenceConfig
from app.services.tracking.models import TrackedObject

class TrackLifecycleState(BaseModel):
    """
    Maintains minimal internal state for a tracked object's lifecycle.
    """
    track_id: int
    first_observed_frame: int
    first_observed_timestamp: float
    last_observed_frame: int
    last_observed_timestamp: float
    consecutive_absence_count: int = 0
    ended: bool = False

class LifecycleEngine(EventEngine):
    """
    Concrete event engine that identifies TRACK_STARTED and TRACK_ENDED
    lifecycle events based on tracking observations and grace-period policies.
    """
    
    def __init__(self, config: EventIntelligenceConfig):
        self._grace_frames = config.track_end_grace_frames
        # Internal state tracking active tracks
        self._state: Dict[int, TrackLifecycleState] = {}
        
    def process(self, frame_number: int, timestamp_seconds: float, tracked_objects: List[TrackedObject]) -> List[Event]:
        """
        Process incoming tracked objects for a frame and emit lifecycle events.
        """
        events: List[Event] = []
        
        # Track IDs present in the current update
        current_track_ids = set()
        
        # Sort tracked objects for deterministic event ordering (by track_id ascending)
        sorted_objects = sorted(tracked_objects, key=lambda obj: obj.track_id)
        
        for obj in sorted_objects:
            track_id = obj.track_id
            current_track_ids.add(track_id)
            
            if track_id not in self._state:
                # This is a newly observed track (or a previously ended track re-appearing)
                self._state[track_id] = TrackLifecycleState(
                    track_id=track_id,
                    first_observed_frame=frame_number,
                    first_observed_timestamp=timestamp_seconds,
                    last_observed_frame=frame_number,
                    last_observed_timestamp=timestamp_seconds,
                    consecutive_absence_count=0
                )
                
                # Emit TRACK_STARTED
                events.append(
                    Event(
                        event_id=str(uuid.uuid4()),
                        event_type=EventType.TRACK_STARTED,
                        frame_number=frame_number,
                        timestamp_seconds=timestamp_seconds,
                        description=f"Track {track_id} started.",
                        track_id=track_id,
                        evidence={
                            "lifecycle_state": "STARTED",
                            "first_observation_frame": frame_number,
                            "first_observation_timestamp": timestamp_seconds
                        }
                    )
                )
            else:
                state = self._state[track_id]
                if state.ended:
                    # The track was previously ended, but has re-appeared.
                    # This represents a new lifecycle for the same ID.
                    state.first_observed_frame = frame_number
                    state.first_observed_timestamp = timestamp_seconds
                    state.last_observed_frame = frame_number
                    state.last_observed_timestamp = timestamp_seconds
                    state.consecutive_absence_count = 0
                    state.ended = False
                    
                    # Emit TRACK_STARTED
                    events.append(
                        Event(
                            event_id=str(uuid.uuid4()),
                            event_type=EventType.TRACK_STARTED,
                            frame_number=frame_number,
                            timestamp_seconds=timestamp_seconds,
                            description=f"Track {track_id} started.",
                            track_id=track_id,
                            evidence={
                                "lifecycle_state": "STARTED",
                                "first_observation_frame": frame_number,
                                "first_observation_timestamp": timestamp_seconds
                            }
                        )
                    )
                else:
                    # Track is currently active and still observed
                    state.last_observed_frame = frame_number
                    state.last_observed_timestamp = timestamp_seconds
                    state.consecutive_absence_count = 0
                
        # Now process tracks that are absent in this frame
        # Sort keys to ensure deterministic ordering of TRACK_ENDED events
        for track_id in sorted(self._state.keys()):
            if track_id not in current_track_ids:
                state = self._state[track_id]
                
                # If it's already ended, we don't care
                if not state.ended:
                    state.consecutive_absence_count += 1
                    
                    # Check if absence exceeds the grace period
                    if state.consecutive_absence_count > self._grace_frames:
                        state.ended = True
                        
                        # Emit TRACK_ENDED
                        events.append(
                            Event(
                                event_id=str(uuid.uuid4()),
                                event_type=EventType.TRACK_ENDED,
                                frame_number=frame_number,
                                timestamp_seconds=timestamp_seconds,
                                description=f"Track {track_id} ended due to absence.",
                                track_id=track_id,
                                evidence={
                                    "lifecycle_state": "ENDED",
                                    "last_observed_frame": state.last_observed_frame,
                                    "last_observed_timestamp": state.last_observed_timestamp,
                                    "consecutive_absence_count": state.consecutive_absence_count,
                                    "grace_frames_policy": self._grace_frames
                                }
                            )
                        )
                        
        return events
        
    def finalize(self) -> List[Event]:
        """
        Explicitly finalize all active tracks, emitting TRACK_ENDED events.
        """
        events: List[Event] = []
        for track_id in sorted(self._state.keys()):
            state = self._state[track_id]
            if not state.ended:
                state.ended = True
                events.append(
                    Event(
                        event_id=str(uuid.uuid4()),
                        event_type=EventType.TRACK_ENDED,
                        frame_number=state.last_observed_frame,
                        timestamp_seconds=state.last_observed_timestamp,
                        description=f"Track {track_id} ended due to end of stream.",
                        track_id=track_id,
                        evidence={
                            "lifecycle_state": "ENDED",
                            "last_observed_frame": state.last_observed_frame,
                            "last_observed_timestamp": state.last_observed_timestamp,
                            "consecutive_absence_count": state.consecutive_absence_count,
                            "grace_frames_policy": self._grace_frames,
                            "end_of_stream": True
                        }
                    )
                )
        return events
        
    def reset(self) -> None:
        """
        Clears all internal lifecycle state.
        Allows for deterministic session boundaries.
        """
        self._state.clear()
