from typing import List, Optional

from app.services.evidence.models import Evidence
from app.services.evidence.lifecycle import EvidenceLifecycleService
from app.repositories.interfaces import IEvidenceRepository


class EvidencePersistenceService:
    """
    Coordinates persistence operations for Evidence metadata.
    Does not manage transaction boundaries (commits/rollbacks) itself.
    Ensures evidence is validated before persistence.
    """

    def __init__(
        self,
        evidence_repo: IEvidenceRepository,
        lifecycle_service: EvidenceLifecycleService
    ):
        self.evidence_repo = evidence_repo
        self.lifecycle_service = lifecycle_service

    def save_evidence(self, evidence: Evidence, session_id: Optional[str] = None) -> None:
        """
        Validates and persists the structured evidence metadata.
        Does NOT store raw image/video media.
        """
        self.lifecycle_service.validate(evidence)
        self.evidence_repo.save(evidence, session_id)

    def get_evidence(self, evidence_id: str) -> Optional[Evidence]:
        return self.evidence_repo.get_by_id(evidence_id)

    def get_session_evidence(self, session_id: str) -> List[Evidence]:
        return self.evidence_repo.get_by_session_id(session_id)

    def get_event_evidence(self, event_id: str) -> List[Evidence]:
        return self.evidence_repo.get_by_event_id(event_id)

    def get_assessment_evidence(self, assessment_id: str) -> List[Evidence]:
        return self.evidence_repo.get_by_assessment_id(assessment_id)
