import pytest
from pydantic import ValidationError
from app.services.events.zones import (
    Point2D, Zone, get_reference_point, is_point_inside_zone, get_object_zone_membership
)
from app.services.tracking.models import BoundingBox, TrackedObject

def test_valid_point_construction():
    pt = Point2D(x=10.5, y=20.0)
    assert pt.x == 10.5
    assert pt.y == 20.0

def test_invalid_finite_point_rejected():
    with pytest.raises(ValidationError):
        Point2D(x=float('inf'), y=0.0)
    with pytest.raises(ValidationError):
        Point2D(x=0.0, y=float('nan'))

def test_valid_triangular_zone():
    zone = Zone(
        zone_id="zone_1",
        name="Triangle",
        polygon=[Point2D(x=0, y=0), Point2D(x=10, y=0), Point2D(x=5, y=10)]
    )
    assert len(zone.polygon) == 3

def test_valid_polygon_zone():
    zone = Zone(
        zone_id="zone_2",
        name="Square",
        polygon=[
            Point2D(x=0, y=0),
            Point2D(x=10, y=0),
            Point2D(x=10, y=10),
            Point2D(x=0, y=10)
        ]
    )
    assert len(zone.polygon) == 4

def test_invalid_polygon_rejected():
    with pytest.raises(ValidationError):
        Zone(
            zone_id="zone_invalid",
            name="Line",
            polygon=[Point2D(x=0, y=0), Point2D(x=10, y=10)]
        )

def test_reference_point_bottom_center():
    bb = BoundingBox(x1=100, y1=100, x2=200, y2=300)
    ref = get_reference_point(bb)
    assert ref.x == 150.0
    assert ref.y == 300.0

@pytest.fixture
def square_zone():
    return Zone(
        zone_id="sq",
        name="Square",
        polygon=[
            Point2D(x=0, y=0),
            Point2D(x=10, y=0),
            Point2D(x=10, y=10),
            Point2D(x=0, y=10)
        ]
    )

def test_point_clearly_inside(square_zone):
    assert is_point_inside_zone(Point2D(x=5, y=5), square_zone) is True

def test_point_clearly_outside(square_zone):
    assert is_point_inside_zone(Point2D(x=15, y=5), square_zone) is False
    assert is_point_inside_zone(Point2D(x=5, y=15), square_zone) is False
    assert is_point_inside_zone(Point2D(x=-5, y=5), square_zone) is False

def test_point_on_boundary(square_zone):
    # Boundary policy is INCLUSIVE
    assert is_point_inside_zone(Point2D(x=5, y=0), square_zone) is True  # Top edge
    assert is_point_inside_zone(Point2D(x=10, y=5), square_zone) is True # Right edge
    assert is_point_inside_zone(Point2D(x=5, y=10), square_zone) is True # Bottom edge
    assert is_point_inside_zone(Point2D(x=0, y=5), square_zone) is True  # Left edge

def test_point_on_vertex(square_zone):
    # Vertices must also be INCLUSIVE
    assert is_point_inside_zone(Point2D(x=0, y=0), square_zone) is True
    assert is_point_inside_zone(Point2D(x=10, y=10), square_zone) is True

def test_multiple_zones_independent():
    zone_a = Zone(
        zone_id="a", name="A",
        polygon=[Point2D(x=0, y=0), Point2D(x=10, y=0), Point2D(x=10, y=10), Point2D(x=0, y=10)]
    )
    zone_b = Zone(
        zone_id="b", name="B",
        polygon=[Point2D(x=20, y=20), Point2D(x=30, y=20), Point2D(x=30, y=30), Point2D(x=20, y=30)]
    )
    
    pt = Point2D(x=5, y=5)
    
    assert is_point_inside_zone(pt, zone_a) is True
    assert is_point_inside_zone(pt, zone_b) is False

def test_membership_determinism(square_zone):
    pt = Point2D(x=5, y=5)
    # Must yield same result multiple times
    assert is_point_inside_zone(pt, square_zone) is True
    assert is_point_inside_zone(pt, square_zone) is True

def test_object_zone_membership(square_zone):
    # x center = 5, y bottom = 5. Inside square.
    obj_inside = TrackedObject(
        track_id=1,
        bounding_box=BoundingBox(x1=0, y1=0, x2=10, y2=5),
        class_id=0, class_name="person", confidence=0.9
    )
    assert get_object_zone_membership(obj_inside, square_zone) is True
    
    # x center = 15, y bottom = 15. Outside square.
    obj_outside = TrackedObject(
        track_id=2,
        bounding_box=BoundingBox(x1=10, y1=10, x2=20, y2=15),
        class_id=0, class_name="person", confidence=0.9
    )
    assert get_object_zone_membership(obj_outside, square_zone) is False
