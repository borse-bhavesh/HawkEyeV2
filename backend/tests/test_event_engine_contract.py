import pytest
from app.services.events.event_engine import EventEngine

def test_event_engine_is_abstract():
    with pytest.raises(TypeError) as excinfo:
        EventEngine()
    
    assert "Can't instantiate abstract class EventEngine" in str(excinfo.value)
