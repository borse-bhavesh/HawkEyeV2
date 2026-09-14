import pytest
from pydantic import ValidationError
from app.services.events.models import Event, EventType

def test_valid_event_creation():
    event = Event(
        event_id="evt_123",
        event_type=EventType.TRACK_STARTED,
        frame_number=10,
        timestamp_seconds=1.5,
        description="Track 5 appeared",
        track_id=5,
        evidence={"track_id": 5, "start_time": 1.5}
    )
    assert event.event_id == "evt_123"
    assert event.event_type == EventType.TRACK_STARTED
    assert event.frame_number == 10
    assert event.timestamp_seconds == 1.5
    assert event.description == "Track 5 appeared"
    assert event.track_id == 5
    assert event.evidence["start_time"] == 1.5

def test_event_without_optional_fields():
    event = Event(
        event_id="evt_456",
        event_type=EventType.MULTIPLE_OBJECT_PROXIMITY,
        frame_number=20,
        timestamp_seconds=3.0,
        description="Objects are close"
    )
    assert event.track_id is None
    assert event.evidence == {}

def test_invalid_event_type_rejected():
    with pytest.raises(ValidationError):
        Event(
            event_id="evt_789",
            event_type="INVALID_TYPE",
            frame_number=30,
            timestamp_seconds=4.5,
            description="Invalid"
        )

def test_missing_required_fields_rejected():
    with pytest.raises(ValidationError):
        Event(
            event_id="evt_999",
            event_type=EventType.LOITERING
            # Missing frame_number, timestamp_seconds, description
        )
