from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.db.models import Event, RiskAssessment, Evidence, risk_assessment_events, ProcessingSession, EventType
from app.services.events.zones import Zone, Point2D
from app.services.events.zone_engine import ZoneEngine
from app.services.risk.orchestrator import RiskOrchestrator
from app.services.evidence.orchestrator import EvidenceOrchestrator
from app.repositories.sql_repo import SQLTrackRepository, SQLEventRepository, SQLRiskAssessmentRepository, SQLEvidenceRepository
from app.services.events.config import EventIntelligenceConfig
from app.services.risk.config import RiskConfig
from app.services.tracking.models import TrackedObject, BoundingBox
from app.services.events.models import Event as DomainEvent

class ZoneRecalculator:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.track_repo = SQLTrackRepository(db_session)
        self.event_repo = SQLEventRepository(db_session)
        self.risk_repo = SQLRiskAssessmentRepository(db_session)
        self.evidence_repo = SQLEvidenceRepository(db_session)
        
    def _clear_zone_events(self, session_id: str):
        # 1. Identify ZONE_ENTRY and ZONE_EXIT events
        zone_events = self.db_session.query(Event).filter(
            Event.processing_session_id == session_id,
            Event.event_type.in_([EventType.ZONE_ENTRY.value, EventType.ZONE_EXIT.value])
        ).all()
        
        event_ids = [e.event_id for e in zone_events]
        
        if not event_ids:
            return
            
        # 2. Identify associated RiskAssessments
        risk_assessments = self.db_session.query(RiskAssessment).join(
            risk_assessment_events
        ).filter(
            risk_assessment_events.c.event_id.in_(event_ids)
        ).all()
        
        assessment_ids = [r.assessment_id for r in risk_assessments]
        
        # 3. Delete associated Evidence
        if assessment_ids:
            self.db_session.query(Evidence).filter(
                Evidence.processing_session_id == session_id,
                (Evidence.event_id.in_(event_ids)) | (Evidence.assessment_id.in_(assessment_ids))
            ).delete(synchronize_session=False)
        else:
            self.db_session.query(Evidence).filter(
                Evidence.processing_session_id == session_id,
                Evidence.event_id.in_(event_ids)
            ).delete(synchronize_session=False)
            
        # 4. Delete RiskAssessments and mapping table rows
        if assessment_ids:
            self.db_session.execute(
                risk_assessment_events.delete().where(
                    risk_assessment_events.c.assessment_id.in_(assessment_ids)
                )
            )
            self.db_session.query(RiskAssessment).filter(
                RiskAssessment.assessment_id.in_(assessment_ids)
            ).delete(synchronize_session=False)
            
        # 5. Delete Events
        self.db_session.query(Event).filter(
            Event.event_id.in_(event_ids)
        ).delete(synchronize_session=False)
        
        self.db_session.commit()

    def recalculate(self, session_id: str, zone_data: Optional[Dict[str, Any]]):
        """
        Clears existing zone events and, if a zone is provided, re-runs the ZoneEngine
        against the session's TrackObservations, passing new events to Risk and Evidence engines.
        """
        # First, delete existing zone events to ensure no duplication
        self._clear_zone_events(session_id)
        
        if not zone_data:
            return # If zone is cleared, we just stop here
            
        # Parse the zone
        polygon = [Point2D(**pt) for pt in zone_data.get('polygon', [])]
        zone = Zone(
            zone_id=zone_data.get('zone_id', 'zone_1'),
            name=zone_data.get('name', 'Restricted Zone'),
            polygon=polygon
        )
        
        # Load TrackObservations
        observations = self.track_repo.get_observations_by_session_id(session_id)
        if not observations:
            return
            
        # Group observations by frame
        frames = {}
        for obs in observations:
            if obs.frame_number not in frames:
                frames[obs.frame_number] = {
                    'timestamp_seconds': obs.timestamp_seconds,
                    'objects': []
                }
            # Track ID format could be UUID-track-123 or just 123
            try:
                track_id_int = int(obs.track_id.split("-track-")[-1]) if "-track-" in obs.track_id else int(obs.track_id)
            except ValueError:
                # Fallback if track_id is UUID only
                track_id_int = hash(obs.track_id) % 1000000

            frames[obs.frame_number]['objects'].append(
                TrackedObject(
                    track_id=track_id_int,
                    class_id=0,
                    class_name=obs.class_name or "unknown",
                    confidence=obs.confidence or 1.0,
                    bounding_box=BoundingBox(
                        x1=obs.bbox_x1, y1=obs.bbox_y1, x2=obs.bbox_x2, y2=obs.bbox_y2
                    )
                )
            )
            
        # Run engines
        zone_engine = ZoneEngine(zones=[zone])
        risk_orchestrator = RiskOrchestrator(config=RiskConfig())
        evidence_orchestrator = EvidenceOrchestrator()
        
        # Load Session Source Info for evidence
        session_obj = self.db_session.query(ProcessingSession).filter_by(session_id=session_id).first()
        if not session_obj:
            return
            
        all_new_events = []
        all_new_risks = []
        all_new_evidence = []
        
        for frame_number in sorted(frames.keys()):
            frame_data = frames[frame_number]
            timestamp_seconds = frame_data['timestamp_seconds']
            tracked_objects = frame_data['objects']
            
            # 1. Zone Engine
            events = zone_engine.process(frame_number, timestamp_seconds, tracked_objects)
            if not events:
                continue
                
            all_new_events.extend(events)
            
            # 2. Risk Engine
            risks = risk_orchestrator.evaluate(events, [])
            all_new_risks.extend(risks)
            
            # 3. Evidence Engine
            evidence_batch = evidence_orchestrator.generate_evidence(
                session_id=session_id,
                source_id=session_obj.source_id,
                source_type=session_obj.source_type,
                frame_number=frame_number,
                timestamp_seconds=timestamp_seconds,
                events=events,
                risk_assessments=risks
            )
            all_new_evidence.extend(evidence_batch)
            
        # Persist everything
        for ev in all_new_events:
            self.event_repo.save(ev, session_id)
            
        for risk in all_new_risks:
            self.risk_repo.save(risk, session_id)
            
        if all_new_evidence:
            self.evidence_repo.save_batch(all_new_evidence)
            
        self.db_session.commit()
