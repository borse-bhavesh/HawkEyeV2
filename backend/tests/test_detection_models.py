import pytest
from pydantic import ValidationError
from app.services.detection.models import BoundingBox, Detection

def test_valid_bounding_box():
    bbox = BoundingBox(x1=10.0, y1=20.0, x2=30.0, y2=40.0)
    assert bbox.x1 == 10.0
    assert bbox.y1 == 20.0
    assert bbox.x2 == 30.0
    assert bbox.y2 == 40.0

def test_valid_detection():
    bbox = BoundingBox(x1=10.0, y1=20.0, x2=30.0, y2=40.0)
    det = Detection(class_id=1, class_name="person", confidence=0.8, bounding_box=bbox)
    assert det.class_id == 1
    assert det.class_name == "person"
    assert det.confidence == 0.8
    assert det.bounding_box == bbox

def test_confidence_zero():
    bbox = BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0)
    det = Detection(class_id=1, class_name="car", confidence=0.0, bounding_box=bbox)
    assert det.confidence == 0.0

def test_confidence_one():
    bbox = BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0)
    det = Detection(class_id=1, class_name="car", confidence=1.0, bounding_box=bbox)
    assert det.confidence == 1.0

def test_invalid_negative_coordinates():
    with pytest.raises(ValidationError):
        BoundingBox(x1=-1.0, y1=10.0, x2=20.0, y2=30.0)
    with pytest.raises(ValidationError):
        BoundingBox(x1=1.0, y1=-10.0, x2=20.0, y2=30.0)
    with pytest.raises(ValidationError):
        BoundingBox(x1=1.0, y1=10.0, x2=-20.0, y2=30.0)
    with pytest.raises(ValidationError):
        BoundingBox(x1=1.0, y1=10.0, x2=20.0, y2=-30.0)

def test_invalid_x2_le_x1():
    with pytest.raises(ValidationError):
        BoundingBox(x1=20.0, y1=10.0, x2=10.0, y2=30.0)
    with pytest.raises(ValidationError):
        BoundingBox(x1=10.0, y1=10.0, x2=10.0, y2=30.0)

def test_invalid_y2_le_y1():
    with pytest.raises(ValidationError):
        BoundingBox(x1=10.0, y1=30.0, x2=20.0, y2=10.0)
    with pytest.raises(ValidationError):
        BoundingBox(x1=10.0, y1=10.0, x2=20.0, y2=10.0)

def test_invalid_confidence():
    bbox = BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0)
    with pytest.raises(ValidationError):
        Detection(class_id=1, class_name="dog", confidence=-0.1, bounding_box=bbox)
    with pytest.raises(ValidationError):
        Detection(class_id=1, class_name="dog", confidence=1.1, bounding_box=bbox)

def test_invalid_class_id():
    bbox = BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0)
    with pytest.raises(ValidationError):
        Detection(class_id=-1, class_name="cat", confidence=0.5, bounding_box=bbox)

def test_empty_class_name():
    bbox = BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0)
    with pytest.raises(ValidationError):
        Detection(class_id=1, class_name="", confidence=0.5, bounding_box=bbox)
