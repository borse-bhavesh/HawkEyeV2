from pydantic import BaseModel, Field

class EventIntelligenceConfig(BaseModel):
    """
    Configuration for thresholds used by the Event Intelligence system.
    """
    # PLANNED: The minimum duration an object must remain in an area to trigger LOITERING
    loitering_duration_seconds: float = Field(
        default=30.0, 
        ge=0.0, 
        description="Threshold for loitering event generation in seconds"
    )
    
    # The speed threshold to trigger RAPID_MOVEMENT
    rapid_movement_speed_threshold: float = Field(
        default=100.0, 
        gt=0.0, 
        description="Speed threshold for rapid movement in pixels per second"
    )
    
    # The angular threshold to trigger DIRECTION_CHANGE
    direction_change_angle_threshold: float = Field(
        default=45.0,
        gt=0.0,
        le=180.0,
        description="Angular threshold for direction change in degrees"
    )
    
    # The distance within which objects trigger MULTIPLE_OBJECT_PROXIMITY
    proximity_distance_threshold: float = Field(
        default=100.0, 
        gt=0.0, 
        description="Distance threshold for proximity events in pixels"
    )
    
    # PLANNED: Global event certainty minimum
    minimum_event_confidence: float = Field(
        default=0.5, 
        ge=0.0, 
        le=1.0, 
        description="Minimum certainty required to raise an event"
    )
    
    # Track History bounded memory size
    max_observations_per_track: int = Field(
        default=300,
        gt=0,
        description="Maximum number of historical observations retained per track ID"
    )
    
    # Track Lifecycle policy
    track_end_grace_frames: int = Field(
        default=5,
        ge=0,
        description="Number of consecutive missing frames before an active track is considered ENDED"
    )
