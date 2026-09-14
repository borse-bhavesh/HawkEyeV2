from dataclasses import dataclass
from typing import List

from app.repositories.domain import ProcessingSessionDomain, TrackDomain
from app.services.events.models import Event
from app.services.risk.models import RiskAssessment
from app.services.evidence.models import Evidence

from app.services.persistence.core import CorePersistenceService
from app.services.persistence.evidence import EvidencePersistenceService

@dataclass
class HistoricalProcessingRun:
    """
    A DTO representing a full, persisted historical processing run.
    Contains purely domain/application abstractions.
    """
    session: ProcessingSessionDomain
    tracks: List[TrackDomain]
    events: List[Event]
    risk_assessments: List[RiskAssessment]
    evidence: List[Evidence]


class HistoryService:
    """
    Retrieves historical intelligence without modifying state.
    Exposes domain models rather than SQLAlchemy ORM objects.
    """

    def __init__(
        self,
        core_persistence: CorePersistenceService,
        evidence_persistence: EvidencePersistenceService
    ):
        self.core = core_persistence
        self.evidence = evidence_persistence

    def get_historical_run(self, session_id: str) -> HistoricalProcessingRun:
        """
        Retrieves a complete processing session and all associated intelligence.
        """
        session = self.core.get_processing_session(session_id)
        if not session:
            raise ValueError(f"Processing session {session_id} not found.")

        tracks = self.core.get_session_tracks(session_id)
        events = self.core.get_session_events(session_id)
        risk_assessments = self.core.get_session_risk_assessments(session_id)
        evidence = self.evidence.get_session_evidence(session_id)

        return HistoricalProcessingRun(
            session=session,
            tracks=tracks,
            events=events,
            risk_assessments=risk_assessments,
            evidence=evidence
        )
