from typing import List, Optional

from app.services.events.models import Event, EventType
from app.services.events.config import EventIntelligenceConfig
from app.services.events.zones import Zone
from app.services.events.lifecycle_engine import LifecycleEngine
from app.services.events.zone_engine import ZoneEngine
from app.services.events.loitering_engine import LoiteringEngine
from app.services.events.rapid_movement_engine import RapidMovementEngine
from app.services.events.direction_change_engine import DirectionChangeEngine
from app.services.events.proximity_engine import ProximityEngine
from app.services.tracking.models import TrackedObject


class EventOrchestrator:
    """
    Coordinates the execution of all event intelligence engines.
    Maintains engine state for exactly one video processing run.
    """

    def __init__(
        self,
        config: EventIntelligenceConfig,
        zones: Optional[List[Zone]] = None,
    ):
        self.config = config
        self.zones = zones or []

        # Initialize engines in deterministic order
        self.lifecycle_engine = LifecycleEngine(config)
        self.zone_engine = ZoneEngine(self.zones)
        self.loitering_engine = LoiteringEngine(config, self.zones)
        self.rapid_movement_engine = RapidMovementEngine(config)
        self.direction_change_engine = DirectionChangeEngine(config)
        self.proximity_engine = ProximityEngine(config)

        self.engines = [
            self.lifecycle_engine,
            self.zone_engine,
            self.loitering_engine,
            self.rapid_movement_engine,
            self.direction_change_engine,
            self.proximity_engine,
        ]

    def process_frame(
        self,
        frame_number: int,
        timestamp_seconds: float,
        tracked_objects: List[TrackedObject],
    ) -> List[Event]:
        """
        Process a single frame through all intelligence engines in deterministic order.
        """
        events: List[Event] = []

        # 1. Run Lifecycle Engine first
        lifecycle_events = self.lifecycle_engine.process(
            frame_number, timestamp_seconds, tracked_objects
        )
        events.extend(lifecycle_events)

        # Inspect for TRACK_ENDED to notify other engines
        ended_track_ids = [
            e.track_id
            for e in lifecycle_events
            if e.event_type == EventType.TRACK_ENDED and e.track_id is not None
        ]

        # 2. Run remaining engines
        for engine in self.engines[1:]:
            engine_events = engine.process(
                frame_number, timestamp_seconds, tracked_objects
            )
            events.extend(engine_events)

        # 3. Clean up ended tracks from other engines
        for track_id in ended_track_ids:
            for engine in self.engines[1:]:
                if hasattr(engine, "remove_track"):
                    engine.remove_track(track_id)

        return events

    def finalize(self) -> List[Event]:
        """
        Explicitly finalize the lifecycle of all active tracks.
        """
        events: List[Event] = []
        
        # Finalize the lifecycle engine to get TRACK_ENDED events
        lifecycle_events = self.lifecycle_engine.finalize()
        events.extend(lifecycle_events)

        # Inspect for TRACK_ENDED to notify other engines
        ended_track_ids = [
            e.track_id
            for e in lifecycle_events
            if e.event_type == EventType.TRACK_ENDED and e.track_id is not None
        ]

        # Clean up downstream engines (for correctness, though state is about to be discarded)
        for track_id in ended_track_ids:
            for engine in self.engines[1:]:
                if hasattr(engine, "remove_track"):
                    engine.remove_track(track_id)

        return events
