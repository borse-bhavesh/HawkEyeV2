from typing import List, Optional
from pydantic import BaseModel

from app.repositories.domain import ProcessingSessionDomain, TrackDomain
from app.services.events.models import Event
from app.services.risk.models import RiskAssessment
from app.services.evidence.models import Evidence


class Point2DSchema(BaseModel):
    x: float
    y: float


class ZoneCreateRequest(BaseModel):
    zone_id: str = "zone_1"
    name: str = "Restricted Zone"
    polygon: List[Point2DSchema]


class HistoricalProcessingRunResponse(BaseModel):
    """
    API Response DTO for a historical processing run.
    Provides a clean, validated JSON representation.
    """
    session: ProcessingSessionDomain
    tracks: List[TrackDomain]
    events: List[Event]
    risk_assessments: List[RiskAssessment]
    evidence: List[Evidence]

