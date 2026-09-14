from typing import List, Optional
from abc import ABC, abstractmethod

from app.repositories.domain import ProcessingSessionDomain, TrackDomain
from app.services.events.models import Event
from app.services.risk.models import RiskAssessment
from app.services.evidence.models import Evidence


class IProcessingSessionRepository(ABC):
    @abstractmethod
    def save(self, session: ProcessingSessionDomain) -> None:
        pass

    @abstractmethod
    def get_by_id(self, session_id: str) -> Optional[ProcessingSessionDomain]:
        pass

    @abstractmethod
    def get_all(self) -> List[ProcessingSessionDomain]:
        pass

    @abstractmethod
    def update(self, session: ProcessingSessionDomain) -> None:
        pass


class ITrackRepository(ABC):
    @abstractmethod
    def save(self, track: TrackDomain) -> None:
        pass

    @abstractmethod
    def get_by_id(self, track_id: str) -> Optional[TrackDomain]:
        pass

    @abstractmethod
    def get_by_session_id(self, session_id: str) -> List[TrackDomain]:
        pass

    @abstractmethod
    def save_observations(self, observations: List['TrackObservationDomain']) -> None:
        pass

    @abstractmethod
    def get_observations_by_session_id(self, session_id: str) -> List['TrackObservationDomain']:
        pass


class IEventRepository(ABC):
    @abstractmethod
    def save(self, event: Event, session_id: str) -> None:
        pass

    @abstractmethod
    def get_by_id(self, event_id: str) -> Optional[Event]:
        pass

    @abstractmethod
    def get_by_session_id(self, session_id: str) -> List[Event]:
        pass

    @abstractmethod
    def get_by_track_id(self, track_id: str) -> List[Event]:
        pass


class IRiskAssessmentRepository(ABC):
    @abstractmethod
    def save(self, assessment: RiskAssessment, session_id: str) -> None:
        pass

    @abstractmethod
    def get_by_id(self, assessment_id: str) -> Optional[RiskAssessment]:
        pass

    @abstractmethod
    def get_by_session_id(self, session_id: str) -> List[RiskAssessment]:
        pass


class IEvidenceRepository(ABC):
    @abstractmethod
    def save(self, evidence: Evidence, session_id: Optional[str] = None) -> None:
        pass

    @abstractmethod
    def get_by_id(self, evidence_id: str) -> Optional[Evidence]:
        pass

    @abstractmethod
    def get_by_session_id(self, session_id: str) -> List[Evidence]:
        pass

    @abstractmethod
    def get_by_event_id(self, event_id: str) -> List[Evidence]:
        pass

    @abstractmethod
    def get_by_assessment_id(self, assessment_id: str) -> List[Evidence]:
        pass
