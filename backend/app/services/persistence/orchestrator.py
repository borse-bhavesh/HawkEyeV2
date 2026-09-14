from typing import List, Optional
from datetime import datetime, timezone

from app.repositories.domain import ProcessingSessionDomain, TrackDomain, TrackObservationDomain
from app.services.events.models import Event
from app.services.risk.models import RiskAssessment
from app.services.evidence.models import Evidence

from app.services.persistence.core import CorePersistenceService
from app.services.persistence.evidence import EvidencePersistenceService


class ProcessingPersistenceOrchestrator:
    """
    Coordinates the lifecycle of a processing run's persistence.
    Writes outputs in bulk to the repository layer.
    """

    def __init__(
        self,
        core_persistence: CorePersistenceService,
        evidence_persistence: EvidencePersistenceService
    ):
        self.core = core_persistence
        self.evidence = evidence_persistence

    def start_session(self, session_id: str, source_id: str, source_type: str, status: str = "STARTED") -> ProcessingSessionDomain:
        """
        Creates and persists the initial processing session state.
        """
        session = ProcessingSessionDomain(
            session_id=session_id,
            source_id=source_id,
            source_type=source_type,
            status=status,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc)
        )
        self.core.save_processing_session(session)
        return session

    def fail_session(self, session: ProcessingSessionDomain) -> None:
        """
        Marks a processing session as failed.
        """
        session.status = "FAILED"
        session.completed_at = datetime.now(timezone.utc)
        self.core.update_processing_session(session)

    def persist_incremental_batch(
        self,
        session: ProcessingSessionDomain,
        tracks: List[TrackDomain],
        observations: List[TrackObservationDomain],
        events: List[Event],
        last_frame: int,
        last_timestamp: float
    ) -> None:
        """
        Persists a batch of tracking and event outputs incrementally.
        Updates the session's processed_until cursors.
        """
        try:
            # Save tracks (upsert via merge)
            for track in tracks:
                self.core.save_track(track)
                
            # Save only new observations (assuming caller passes only unpersisted ones)
            if observations:
                self.core.save_track_observations(observations)
                
            # Save only new events (assuming caller passes only unpersisted ones)
            for event in events:
                self.core.save_event(event, session.session_id)
                
            # Update session cursors
            session.processed_until_frame = last_frame
            session.processed_until_timestamp = last_timestamp
            self.core.update_processing_session(session)
            
            # Commit the transaction boundary for this incremental batch
            self.core.commit()
            
        except Exception:
            self.core.rollback()
            raise

    def complete_session(
        self,
        session: ProcessingSessionDomain,
        tracks: List[TrackDomain],
        observations: List[TrackObservationDomain],
        events: List[Event],
        risk_assessments: List[RiskAssessment],
        evidence: List[Evidence]
    ) -> None:
        """
        Persists all processing outputs and marks the session completed.
        All writes are executed via the underlying services in the same transaction space.
        """
        # 1. Save tracks
        for track in tracks:
            self.core.save_track(track)
            
        # 1.5 Save observations
        self.core.save_track_observations(observations)
            
        # 2. Save events
        for event in events:
            self.core.save_event(event, session.session_id)
            
        # 3. Save risk assessments
        for assessment in risk_assessments:
            self.core.save_risk_assessment(assessment, session.session_id)
            
        # 4. Save evidence metadata
        for ev in evidence:
            self.evidence.save_evidence(ev, session.session_id)
            
        # 5. Finalize session state
        session.status = "COMPLETED"
        session.completed_at = datetime.now(timezone.utc)
        self.core.update_processing_session(session)
