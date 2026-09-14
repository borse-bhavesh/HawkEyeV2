import pytest
from pydantic import ValidationError

from app.services.tracking.models import TrackedObject
from app.services.detection.models import Detection, BoundingBox

def create_valid_bbox() -> BoundingBox:
    return BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0)

def test_valid_tracked_object():
    obj = TrackedObject(
        track_id=1,
        class_id=0,
        class_name="person",
        confidence=0.9,
        bounding_box=create_valid_bbox()
    )
    assert obj.track_id == 1
    assert obj.class_id == 0
    assert obj.class_name == "person"
    assert obj.confidence == 0.9

def test_track_id_zero_accepted():
    obj = TrackedObject(
        track_id=0,
        class_id=0,
        class_name="person",
        confidence=0.9,
        bounding_box=create_valid_bbox()
    )
    assert obj.track_id == 0

def test_positive_track_id_accepted():
    obj = TrackedObject(
        track_id=100,
        class_id=0,
        class_name="person",
        confidence=0.9,
        bounding_box=create_valid_bbox()
    )
    assert obj.track_id == 100

def test_negative_track_id_rejected():
    with pytest.raises(ValidationError):
        TrackedObject(
            track_id=-1,
            class_id=0,
            class_name="person",
            confidence=0.9,
            bounding_box=create_valid_bbox()
        )

def test_negative_class_id_rejected():
    with pytest.raises(ValidationError):
        TrackedObject(
            track_id=1,
            class_id=-1,
            class_name="person",
            confidence=0.9,
            bounding_box=create_valid_bbox()
        )

def test_empty_class_name_rejected():
    with pytest.raises(ValidationError):
        TrackedObject(
            track_id=1,
            class_id=0,
            class_name="",
            confidence=0.9,
            bounding_box=create_valid_bbox()
        )



def test_confidence_zero_accepted():
    obj = TrackedObject(
        track_id=1,
        class_id=0,
        class_name="person",
        confidence=0.0,
        bounding_box=create_valid_bbox()
    )
    assert obj.confidence == 0.0

def test_confidence_one_accepted():
    obj = TrackedObject(
        track_id=1,
        class_id=0,
        class_name="person",
        confidence=1.0,
        bounding_box=create_valid_bbox()
    )
    assert obj.confidence == 1.0

def test_confidence_below_zero_rejected():
    with pytest.raises(ValidationError):
        TrackedObject(
            track_id=1,
            class_id=0,
            class_name="person",
            confidence=-0.1,
            bounding_box=create_valid_bbox()
        )

def test_confidence_above_one_rejected():
    with pytest.raises(ValidationError):
        TrackedObject(
            track_id=1,
            class_id=0,
            class_name="person",
            confidence=1.1,
            bounding_box=create_valid_bbox()
        )

def test_invalid_bounding_box_rejected():
    with pytest.raises(ValidationError):
        TrackedObject(
            track_id=1,
            class_id=0,
            class_name="person",
            confidence=0.9,
            bounding_box=BoundingBox(x1=10.0, y1=0.0, x2=0.0, y2=10.0) # Invalid: x2 < x1
        )

def test_valid_bounding_box_preserved():
    bbox = create_valid_bbox()
    obj = TrackedObject(
        track_id=1,
        class_id=0,
        class_name="person",
        confidence=0.9,
        bounding_box=bbox
    )
    assert obj.bounding_box.x1 == 0.0
    assert obj.bounding_box.y1 == 0.0
    assert obj.bounding_box.x2 == 10.0
    assert obj.bounding_box.y2 == 10.0

def test_model_contains_expected_fields():
    fields = TrackedObject.model_fields.keys()
    assert "track_id" in fields
    assert "class_id" in fields
    assert "class_name" in fields
    assert "confidence" in fields
    assert "bounding_box" in fields

def test_tracked_object_independent_from_detection():
    # Explicitly verify Detection does NOT contain track_id
    assert "track_id" not in Detection.model_fields.keys()
    # Explicitly verify TrackedObject DOES contain track_id
    assert "track_id" in TrackedObject.model_fields.keys()

def test_whitespace_class_name_consistency():
    # Whitespace-only class name is rejected if consistent with the existing detection validation approach.
    # We will test Detection. If Detection accepts it, TrackedObject accepts it. 
    # If Detection rejects it, TrackedObject rejects it.
    bbox = create_valid_bbox()
    detection_accepts_whitespace = True
    try:
        Detection(class_id=0, class_name="   ", confidence=0.9, bounding_box=bbox)
    except ValidationError:
        detection_accepts_whitespace = False

    if detection_accepts_whitespace:
        obj = TrackedObject(
            track_id=1,
            class_id=0,
            class_name="   ",
            confidence=0.9,
            bounding_box=bbox
        )
        assert obj.class_name == "   "
    else:
        with pytest.raises(ValidationError):
            TrackedObject(
                track_id=1,
                class_id=0,
                class_name="   ",
                confidence=0.9,
                bounding_box=bbox
            )
