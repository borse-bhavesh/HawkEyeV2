from typing import List
from pydantic import BaseModel, Field, field_validator
import math
from app.services.tracking.models import BoundingBox, TrackedObject

class Point2D(BaseModel):
    """
    Represents an explicitly typed (x, y) coordinate in the image plane.
    x increases to the right, y increases downward.
    """
    x: float = Field(..., description="X coordinate in image space")
    y: float = Field(..., description="Y coordinate in image space")

    @field_validator('x', 'y')
    @classmethod
    def check_finite(cls, v):
        if not math.isfinite(v):
            raise ValueError("Coordinates must be finite numbers")
        return v

class Zone(BaseModel):
    """
    Represents a spatial region of interest in the image plane.
    Does not interpret events or contain event logic.
    """
    zone_id: str = Field(..., description="Unique identifier for the zone")
    name: str = Field(..., description="Human-readable name of the zone")
    polygon: List[Point2D] = Field(..., description="Ordered list of vertices defining the zone polygon")

    @field_validator('polygon')
    @classmethod
    def check_polygon_validity(cls, v: List[Point2D]):
        if len(v) < 3:
            raise ValueError("A zone polygon must have at least 3 points")
        return v

def get_reference_point(bounding_box: BoundingBox) -> Point2D:
    """
    Calculates the representative point of a bounding box for spatial membership.
    
    Convention: BOTTOM_CENTER. 
    This approximates the ground-contact point in an image plane.
    """
    x_center = (bounding_box.x1 + bounding_box.x2) / 2.0
    y_bottom = float(bounding_box.y2)
    return Point2D(x=x_center, y=y_bottom)

def _is_point_on_segment(p: Point2D, a: Point2D, b: Point2D) -> bool:
    """
    Helper function to check if point p lies exactly on the line segment a-b.
    Uses cross product and bounding box checks.
    """
    # Check bounding box first
    if (min(a.x, b.x) <= p.x <= max(a.x, b.x)) and (min(a.y, b.y) <= p.y <= max(a.y, b.y)):
        # Cross product to check collinearity
        cross_product = (p.y - a.y) * (b.x - a.x) - (p.x - a.x) * (b.y - a.y)
        if abs(cross_product) < 1e-9:  # Float tolerance
            return True
    return False

def is_point_inside_zone(point: Point2D, zone: Zone) -> bool:
    """
    Determines if a point lies within the zone polygon using the Ray-Casting algorithm.
    
    Boundary Policy: INCLUSIVE. 
    A point lying exactly on the polygon boundary is considered INSIDE the zone.
    """
    poly = zone.polygon
    n = len(poly)
    
    # Check boundaries first
    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        if _is_point_on_segment(point, p1, p2):
            return True
            
    # Standard even-odd rule via Ray-Casting
    inside = False
    p1 = poly[0]
    for i in range(1, n + 1):
        p2 = poly[i % n]
        if point.y > min(p1.y, p2.y):
            if point.y <= max(p1.y, p2.y):
                if point.x <= max(p1.x, p2.x):
                    if p1.y != p2.y:
                        xinters = (point.y - p1.y) * (p2.x - p1.x) / (p2.y - p1.y) + p1.x
                        if p1.x == p2.x or point.x <= xinters:
                            inside = not inside
        p1 = p2

    return inside

def get_object_zone_membership(tracked_object: TrackedObject, zone: Zone) -> bool:
    """
    Calculates if a TrackedObject is currently inside a Zone.
    This relies purely on the bounding box reference point.
    """
    ref_point = get_reference_point(tracked_object.bounding_box)
    return is_point_inside_zone(ref_point, zone)
