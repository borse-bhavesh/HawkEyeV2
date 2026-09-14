from typing import List, Optional

from app.repositories.domain import ProcessingSessionDomain, TrackDomain, TrackObservationDomain
from app.services.events.models import Event
from app.services.risk.models import RiskAssessment
from app.repositories.interfaces import (
    IProcessingSessionRepository,
    ITrackRepository,
    IEventRepository,
    IRiskAssessmentRepository
)


class CorePersistenceService:
    """
    Coordinates core persistence operations (sessions, tracks, events, risk assessments).
    Operates strictly on the repository layer using domain objects.
    Does not manage transaction boundaries (commits/rollbacks) itself.
    """

    def __init__(
        self,
        session_repo: IProcessingSessionRepository,
        track_repo: ITrackRepository,
        event_repo: IEventRepository,
        risk_repo: IRiskAssessmentRepository
    ):
        self.session_repo = session_repo
        self.track_repo = track_repo
        self.event_repo = event_repo
        self.risk_repo = risk_repo

    def save_processing_session(self, session: ProcessingSessionDomain) -> None:
        self.session_repo.save(session)

    def get_processing_session(self, session_id: str) -> Optional[ProcessingSessionDomain]:
        return self.session_repo.get_by_id(session_id)

    def get_processing_sessions(self) -> List[ProcessingSessionDomain]:
        return self.session_repo.get_all()

    def update_processing_session(self, session: ProcessingSessionDomain) -> None:
        self.session_repo.update(session)

    def commit(self) -> None:
        """Commits the current transaction if supported by the underlying repository."""
        if hasattr(self.session_repo, 'session'):
            self.session_repo.session.commit()
            
    def rollback(self) -> None:
        """Rolls back the current transaction if supported by the underlying repository."""
        if hasattr(self.session_repo, 'session'):
            self.session_repo.session.rollback()

    def save_track(self, track: TrackDomain) -> None:
        self.track_repo.save(track)

    def get_track(self, track_id: str) -> Optional[TrackDomain]:
        return self.track_repo.get_by_id(track_id)

    def get_session_tracks(self, session_id: str) -> List[TrackDomain]:
        return self.track_repo.get_by_session_id(session_id)

    def save_track_observations(self, observations: List[TrackObservationDomain]) -> None:
        self.track_repo.save_observations(observations)
        
    def get_session_observations(self, session_id: str) -> List[TrackObservationDomain]:
        return self.track_repo.get_observations_by_session_id(session_id)

    def save_event(self, event: Event, session_id: str) -> None:
        self.event_repo.save(event, session_id)

    def get_event(self, event_id: str) -> Optional[Event]:
        return self.event_repo.get_by_id(event_id)

    def get_session_events(self, session_id: str) -> List[Event]:
        return self.event_repo.get_by_session_id(session_id)

    def get_track_events(self, track_id: str) -> List[Event]:
        return self.event_repo.get_by_track_id(track_id)

    def save_risk_assessment(self, assessment: RiskAssessment, session_id: str) -> None:
        self.risk_repo.save(assessment, session_id)

    def get_risk_assessment(self, assessment_id: str) -> Optional[RiskAssessment]:
        return self.risk_repo.get_by_id(assessment_id)

    def get_session_risk_assessments(self, session_id: str) -> List[RiskAssessment]:
        return self.risk_repo.get_by_session_id(session_id)
