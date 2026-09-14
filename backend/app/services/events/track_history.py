from collections import deque
from typing import Dict, List, Tuple
from app.services.events.models import TrackObservation
from app.services.events.config import EventIntelligenceConfig

class TrackHistory:
    """
    Maintains a deterministic, bounded, chronological history of tracking observations.
    
    This component manages temporal state for Event Intelligence.
    It does not interpret behavior, calculate risk, or emit events.
    """
    
    def __init__(self, config: EventIntelligenceConfig):
        """
        Initializes the track history with the specified configuration.
        """
        self._max_observations = config.max_observations_per_track
        # Keys are track_id, values are bounded deques of TrackObservation
        self._history: Dict[int, deque] = {}
        
    def add_observation(self, observation: TrackObservation) -> None:
        """
        Appends a new observation to the track's history.
        
        Args:
            observation: The tracked object observation containing temporal and spatial data.
            
        Raises:
            ValueError: If the observation is out of chronological order (strictly earlier timestamp or frame number).
        """
        track_id = observation.track_id
        
        if track_id not in self._history:
            self._history[track_id] = deque(maxlen=self._max_observations)
        else:
            # Enforce deterministic temporal ordering
            last_obs = self._history[track_id][-1]
            if observation.frame_number < last_obs.frame_number or observation.timestamp_seconds < last_obs.timestamp_seconds:
                raise ValueError(
                    f"Out-of-order observation for track {track_id}. "
                    f"Last: frame={last_obs.frame_number}, time={last_obs.timestamp_seconds}. "
                    f"New: frame={observation.frame_number}, time={observation.timestamp_seconds}."
                )
                
        # We store a defensive copy to prevent callers from mutating the stored data via shared reference
        self._history[track_id].append(observation.model_copy(deep=True))
        
    def get_track_history(self, track_id: int) -> Tuple[TrackObservation, ...]:
        """
        Retrieves the complete retained chronological history for a given track ID.
        
        Returns a tuple to ensure immutability by the caller.
        Returns an empty tuple if the track_id has no history.
        """
        if track_id not in self._history:
            return ()
        return tuple(self._history[track_id])
        
    def get_recent_observations(self, track_id: int, count: int) -> Tuple[TrackObservation, ...]:
        """
        Retrieves up to `count` of the most recent observations for a track ID.
        
        Returns a tuple to ensure immutability by the caller.
        """
        if count <= 0:
            return ()
        history = self.get_track_history(track_id)
        return history[-count:]
        
    def get_active_track_ids(self) -> Tuple[int, ...]:
        """
        Returns a tuple of all track IDs currently being tracked.
        The order is arbitrary but deterministic (insertion order of the underlying dict in Python 3.7+).
        """
        return tuple(self._history.keys())
        
    def remove_track(self, track_id: int) -> None:
        """
        Removes all history for a specific track ID.
        """
        self._history.pop(track_id, None)
        
    def clear(self) -> None:
        """
        Clears all history for all tracks.
        """
        self._history.clear()
