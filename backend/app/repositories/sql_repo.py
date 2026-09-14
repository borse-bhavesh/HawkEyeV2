from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import insert, select

from app.db.models import (
    ProcessingSession, Track, Event, RiskAssessment, Evidence,
    risk_assessment_events, TrackObservation
)
from app.repositories.domain import ProcessingSessionDomain, TrackDomain, TrackObservationDomain
from app.services.events.models import Event as DomainEvent
from app.services.risk.models import RiskAssessment as DomainRiskAssessment
from app.services.evidence.models import Evidence as DomainEvidence, EvidenceSource, FrameEvidence, VideoSegmentEvidence
from app.repositories.interfaces import (
    IProcessingSessionRepository, ITrackRepository, IEventRepository,
    IRiskAssessmentRepository, IEvidenceRepository
)
from app.repositories.exceptions import RecordNotFoundError, DuplicateRecordError


class SQLProcessingSessionRepository(IProcessingSessionRepository):
    def __init__(self, session: Session):
        self.session = session

    def save(self, session_domain: ProcessingSessionDomain) -> None:
        db_obj = ProcessingSession(
            session_id=session_domain.session_id,
            source_id=session_domain.source_id,
            source_type=session_domain.source_type,
            status=session_domain.status,
            created_at=session_domain.created_at,
            started_at=session_domain.started_at,
            completed_at=session_domain.completed_at,
            restricted_zone=session_domain.restricted_zone,
            processed_until_frame=getattr(session_domain, 'processed_until_frame', None),
            processed_until_timestamp=getattr(session_domain, 'processed_until_timestamp', None)
        )
        try:
            self.session.add(db_obj)
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            raise DuplicateRecordError(f"ProcessingSession {session_domain.session_id} already exists.")

    def get_by_id(self, session_id: str) -> Optional[ProcessingSessionDomain]:
        db_obj = self.session.query(ProcessingSession).filter_by(session_id=session_id).first()
        if not db_obj:
            return None
        return ProcessingSessionDomain(
            session_id=db_obj.session_id,
            source_id=db_obj.source_id,
            source_type=db_obj.source_type,
            status=db_obj.status,
            created_at=db_obj.created_at,
            started_at=db_obj.started_at,
            completed_at=db_obj.completed_at,
            restricted_zone=db_obj.restricted_zone,
            processed_until_frame=db_obj.processed_until_frame,
            processed_until_timestamp=db_obj.processed_until_timestamp
        )

    def get_all(self) -> List[ProcessingSessionDomain]:
        db_objs = self.session.query(ProcessingSession).order_by(ProcessingSession.created_at.desc()).all()
        return [
            ProcessingSessionDomain(
                session_id=obj.session_id,
                source_id=obj.source_id,
                source_type=obj.source_type,
                status=obj.status,
                created_at=obj.created_at,
                started_at=obj.started_at,
                completed_at=obj.completed_at,
                restricted_zone=obj.restricted_zone,
                processed_until_frame=obj.processed_until_frame,
                processed_until_timestamp=obj.processed_until_timestamp
            ) for obj in db_objs
        ]

    def update(self, session_domain: ProcessingSessionDomain) -> None:
        db_obj = self.session.query(ProcessingSession).filter_by(session_id=session_domain.session_id).first()
        if not db_obj:
            raise RecordNotFoundError(f"ProcessingSession {session_domain.session_id} not found.")
        
        db_obj.source_id = session_domain.source_id
        db_obj.source_type = session_domain.source_type
        db_obj.status = session_domain.status
        db_obj.created_at = session_domain.created_at
        db_obj.started_at = session_domain.started_at
        db_obj.completed_at = session_domain.completed_at
        db_obj.restricted_zone = session_domain.restricted_zone
        db_obj.processed_until_frame = getattr(session_domain, 'processed_until_frame', None)
        db_obj.processed_until_timestamp = getattr(session_domain, 'processed_until_timestamp', None)
        self.session.flush()


class SQLTrackRepository(ITrackRepository):
    def __init__(self, session: Session):
        self.session = session

    def _to_domain(self, db_obj: Track) -> TrackDomain:
        return TrackDomain(
            id=db_obj.id,
            processing_session_id=db_obj.processing_session_id,
            session_track_id=db_obj.session_track_id,
            class_id=db_obj.class_id,
            class_name=db_obj.class_name,
            confidence=db_obj.confidence,
            latest_bbox=db_obj.latest_bbox
        )

    def save(self, track: TrackDomain) -> None:
        db_obj = self.session.query(Track).filter_by(id=track.id).first()
        if db_obj:
            db_obj.latest_bbox = track.latest_bbox
            db_obj.confidence = track.confidence
        else:
            db_obj = Track(
                id=track.id,
                processing_session_id=track.processing_session_id,
                session_track_id=track.session_track_id,
                class_id=track.class_id,
                class_name=track.class_name,
                confidence=track.confidence,
                latest_bbox=track.latest_bbox
            )
            self.session.add(db_obj)
        self.session.flush()

    def get_by_id(self, track_id: str) -> Optional[TrackDomain]:
        db_obj = self.session.query(Track).filter_by(id=track_id).first()
        if not db_obj:
            return None
        return self._to_domain(db_obj)

    def get_by_session_id(self, session_id: str) -> List[TrackDomain]:
        db_objs = self.session.query(Track).filter_by(processing_session_id=session_id).all()
        return [self._to_domain(obj) for obj in db_objs]

    def save_observations(self, observations: List[TrackObservationDomain]) -> None:
        if not observations:
            return
            
        # Bulk insert for efficiency
        db_objs = [
            TrackObservation(
                processing_session_id=obs.processing_session_id,
                track_id=obs.track_id,
                frame_number=obs.frame_number,
                timestamp_seconds=obs.timestamp_seconds,
                class_name=obs.class_name,
                confidence=obs.confidence,
                bbox_x1=obs.bbox_x1,
                bbox_y1=obs.bbox_y1,
                bbox_x2=obs.bbox_x2,
                bbox_y2=obs.bbox_y2
            ) for obs in observations
        ]
        try:
            self.session.add_all(db_objs)
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            raise DuplicateRecordError("Integrity error while saving track observations.")

    def get_observations_by_session_id(self, session_id: str) -> List[TrackObservationDomain]:
        db_objs = self.session.query(TrackObservation).filter_by(processing_session_id=session_id).all()
        return [
            TrackObservationDomain(
                processing_session_id=obj.processing_session_id,
                track_id=obj.track_id,
                frame_number=obj.frame_number,
                timestamp_seconds=obj.timestamp_seconds,
                class_name=obj.class_name,
                confidence=obj.confidence,
                bbox_x1=obj.bbox_x1,
                bbox_y1=obj.bbox_y1,
                bbox_x2=obj.bbox_x2,
                bbox_y2=obj.bbox_y2
            ) for obj in db_objs
        ]

class SQLEventRepository(IEventRepository):
    def __init__(self, session: Session):
        self.session = session

    def _to_domain(self, db_obj: Event) -> DomainEvent:
        track_session_id = None
        if db_obj.track:
            track_session_id = db_obj.track.session_track_id
            
        return DomainEvent(
            event_id=db_obj.event_id,
            event_type=db_obj.event_type.name,
            frame_number=db_obj.frame_number,
            timestamp_seconds=db_obj.timestamp_seconds,
            description=db_obj.description,
            track_id=track_session_id,
            evidence=db_obj.evidence_data or {}
        )

    def save(self, event: DomainEvent, session_id: str) -> None:
        actual_track_id = None
        if event.track_id is not None:
            # Domain track_id is the integer session_track_id. 
            # We must look up the database UUID (Track.id).
            track_record = self.session.query(Track).filter_by(
                processing_session_id=session_id, 
                session_track_id=event.track_id
            ).first()
            if track_record:
                actual_track_id = track_record.id
            else:
                # If we cannot resolve it, we could raise or store None, but 
                # since the user says "invalid event references fail predictably", 
                # we should let it fail or raise explicitly.
                raise DuplicateRecordError(f"Track reference {event.track_id} not found in session.")

        db_obj = Event(
            event_id=event.event_id,
            processing_session_id=session_id,
            event_type=event.event_type.name,
            frame_number=event.frame_number,
            timestamp_seconds=event.timestamp_seconds,
            description=event.description,
            track_id=actual_track_id,
            evidence_data=event.evidence
        )
        try:
            self.session.add(db_obj)
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            raise DuplicateRecordError(f"Event {event.event_id} already exists or invalid reference.")

    def get_by_id(self, event_id: str) -> Optional[DomainEvent]:
        db_obj = self.session.query(Event).filter_by(event_id=event_id).first()
        if not db_obj:
            return None
        return self._to_domain(db_obj)

    def get_by_session_id(self, session_id: str) -> List[DomainEvent]:
        db_objs = self.session.query(Event).filter_by(processing_session_id=session_id).all()
        return [self._to_domain(obj) for obj in db_objs]

    def get_by_track_id(self, track_id: str) -> List[DomainEvent]:
        db_objs = self.session.query(Event).filter_by(track_id=track_id).all()
        return [self._to_domain(obj) for obj in db_objs]

class SQLRiskAssessmentRepository(IRiskAssessmentRepository):
    def __init__(self, session: Session):
        self.session = session

    def _to_domain(self, db_obj: RiskAssessment) -> DomainRiskAssessment:
        contributing_event_ids = [evt.event_id for evt in db_obj.contributing_events]
        contributing_event_types = [evt.event_type.name for evt in db_obj.contributing_events]

        return DomainRiskAssessment(
            event_id=db_obj.assessment_id,
            contributing_event_ids=contributing_event_ids,
            contributing_event_types=contributing_event_types,
            risk_level=db_obj.risk_level.name.lower(),
            priority=db_obj.priority.name.lower(),
            reason=db_obj.reason,
            status=db_obj.status.name.lower(),
            evidence=None
        )

    def save(self, assessment: DomainRiskAssessment, session_id: str) -> None:
        db_obj = RiskAssessment(
            assessment_id=assessment.event_id,
            processing_session_id=session_id,
            risk_level=assessment.risk_level.name,
            priority=assessment.priority.name,
            status=assessment.status.name,
            reason=assessment.reason
        )
        try:
            self.session.add(db_obj)
            self.session.flush()
            
            if assessment.contributing_event_ids:
                events_to_link = self.session.query(Event).filter(
                    Event.event_id.in_(assessment.contributing_event_ids)
                ).all()
                if len(events_to_link) != len(assessment.contributing_event_ids):
                    raise ValueError(f"One or more contributing events not found for assessment {assessment.event_id}")
                db_obj.contributing_events.extend(events_to_link)
                self.session.flush()
        except IntegrityError:
            self.session.rollback()
            raise DuplicateRecordError(f"RiskAssessment {assessment.event_id} already exists or invalid reference.")
        except ValueError as e:
            self.session.rollback()
            raise DuplicateRecordError(str(e))

    def get_by_id(self, assessment_id: str) -> Optional[DomainRiskAssessment]:
        db_obj = self.session.query(RiskAssessment).filter_by(assessment_id=assessment_id).first()
        if not db_obj:
            return None
        return self._to_domain(db_obj)

    def get_by_session_id(self, session_id: str) -> List[DomainRiskAssessment]:
        db_objs = self.session.query(RiskAssessment).filter_by(processing_session_id=session_id).all()
        return [self._to_domain(obj) for obj in db_objs]

class SQLEvidenceRepository(IEvidenceRepository):
    def __init__(self, session: Session):
        self.session = session

    def _to_domain(self, db_obj: Evidence) -> DomainEvidence:
        frame_ev = FrameEvidence(**db_obj.frame_metadata) if db_obj.frame_metadata else None
        seg_ev = VideoSegmentEvidence(**db_obj.segment_metadata) if db_obj.segment_metadata else None
        
        return DomainEvidence(
            evidence_id=db_obj.evidence_id,
            evidence_type=db_obj.evidence_type.name,
            source=EvidenceSource(source_id=db_obj.source_id, source_type=db_obj.source_type),
            frame=frame_ev,
            video_segment=seg_ev,
            event_id=db_obj.event_id,
            assessment_id=db_obj.assessment_id
        )

    def save(self, evidence: DomainEvidence, session_id: Optional[str] = None) -> None:
        db_obj = Evidence(
            evidence_id=evidence.evidence_id,
            processing_session_id=session_id,
            evidence_type=evidence.evidence_type.name,
            source_id=evidence.source.source_id,
            source_type=evidence.source.source_type,
            frame_metadata=evidence.frame.model_dump() if evidence.frame else None,
            segment_metadata=evidence.video_segment.model_dump() if evidence.video_segment else None,
            event_id=evidence.event_id,
            assessment_id=evidence.assessment_id
        )
        try:
            self.session.add(db_obj)
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            raise DuplicateRecordError(f"Evidence {evidence.evidence_id} already exists or invalid reference.")

    def get_by_id(self, evidence_id: str) -> Optional[DomainEvidence]:
        db_obj = self.session.query(Evidence).filter_by(evidence_id=evidence_id).first()
        if not db_obj:
            return None
        return self._to_domain(db_obj)

    def get_by_session_id(self, session_id: str) -> List[DomainEvidence]:
        db_objs = self.session.query(Evidence).filter_by(processing_session_id=session_id).all()
        return [self._to_domain(obj) for obj in db_objs]

    def get_by_event_id(self, event_id: str) -> List[DomainEvidence]:
        db_objs = self.session.query(Evidence).filter_by(event_id=event_id).all()
        return [self._to_domain(obj) for obj in db_objs]

    def get_by_assessment_id(self, assessment_id: str) -> List[DomainEvidence]:
        db_objs = self.session.query(Evidence).filter_by(assessment_id=assessment_id).all()
        return [self._to_domain(obj) for obj in db_objs]
