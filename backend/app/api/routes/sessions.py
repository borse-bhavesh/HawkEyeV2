from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.repositories.sql_repo import (
    SQLProcessingSessionRepository,
    SQLTrackRepository,
    SQLEventRepository,
    SQLRiskAssessmentRepository,
    SQLEvidenceRepository
)
from app.services.persistence.core import CorePersistenceService
from app.services.persistence.evidence import EvidencePersistenceService
from app.services.persistence.history import HistoryService
from app.db.models import ProcessingSession, TrackObservation
from sqlalchemy import delete
import shutil


from app.repositories.domain import ProcessingSessionDomain, TrackDomain, TrackObservationDomain
from app.services.events.models import Event
from app.services.risk.models import RiskAssessment
from app.services.evidence.models import Evidence
from app.api.schemas.sessions import HistoricalProcessingRunResponse, ZoneCreateRequest
from app.services.events.zone_recalculator import ZoneRecalculator


router = APIRouter(tags=["Sessions"])


def get_core_service(db: Session = Depends(get_db)) -> CorePersistenceService:
    return CorePersistenceService(
        session_repo=SQLProcessingSessionRepository(db),
        track_repo=SQLTrackRepository(db),
        event_repo=SQLEventRepository(db),
        risk_repo=SQLRiskAssessmentRepository(db)
    )

from app.services.evidence.lifecycle import EvidenceLifecycleService

def get_evidence_service(db: Session = Depends(get_db)) -> EvidencePersistenceService:
    return EvidencePersistenceService(
        evidence_repo=SQLEvidenceRepository(db),
        lifecycle_service=EvidenceLifecycleService()
    )

def get_history_service(
    core_service: CorePersistenceService = Depends(get_core_service),
    evidence_service: EvidencePersistenceService = Depends(get_evidence_service)
) -> HistoryService:
    return HistoryService(core_persistence=core_service, evidence_persistence=evidence_service)


@router.get("/sessions", response_model=List[ProcessingSessionDomain])
def list_sessions(
    core_service: CorePersistenceService = Depends(get_core_service)
):
    """
    Retrieve all persisted processing sessions.
    """
    return core_service.get_processing_sessions()


@router.get("/sessions/{session_id}", response_model=ProcessingSessionDomain)
def get_session(
    session_id: str,
    core_service: CorePersistenceService = Depends(get_core_service)
):
    """
    Retrieve a specific processing session by ID.
    """
    session = core_service.get_processing_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Processing session not found.")
    return session


@router.get("/sessions/{session_id}/history", response_model=HistoricalProcessingRunResponse)
def get_session_history(
    session_id: str,
    history_service: HistoryService = Depends(get_history_service)
):
    """
    Retrieve the full historical intelligence representation of a session.
    """
    try:
        run = history_service.get_historical_run(session_id)
        return HistoricalProcessingRunResponse(
            session=run.session,
            tracks=run.tracks,
            events=run.events,
            risk_assessments=run.risk_assessments,
            evidence=run.evidence
        )
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}/tracks", response_model=List[TrackDomain])
def get_session_tracks(
    session_id: str,
    core_service: CorePersistenceService = Depends(get_core_service)
):
    """
    Retrieve tracks associated with a specific session.
    """
    session = core_service.get_processing_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Processing session not found.")
    return core_service.get_session_tracks(session_id)


@router.get("/sessions/{session_id}/events", response_model=List[Event])
def get_session_events(
    session_id: str,
    after_frame: int = -1,
    core_service: CorePersistenceService = Depends(get_core_service)
):
    """
    Retrieve events associated with a specific session.
    """
    session = core_service.get_processing_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Processing session not found.")
    events = core_service.get_session_events(session_id)
    if after_frame >= 0:
        events = [e for e in events if e.frame_number > after_frame]
    return events


@router.get("/sessions/{session_id}/risks", response_model=List[RiskAssessment])
def get_session_risks(
    session_id: str,
    core_service: CorePersistenceService = Depends(get_core_service)
):
    """
    Retrieve risk assessments associated with a specific session.
    """
    session = core_service.get_processing_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Processing session not found.")
    return core_service.get_session_risk_assessments(session_id)


@router.get("/sessions/{session_id}/evidence", response_model=List[Evidence])
def get_session_evidence(
    session_id: str,
    core_service: CorePersistenceService = Depends(get_core_service),
    evidence_service: EvidencePersistenceService = Depends(get_evidence_service)
):
    """
    Retrieve evidence associated with a specific session.
    """
    session = core_service.get_processing_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Processing session not found.")
    return evidence_service.get_session_evidence(session_id)


import os
import re
from pathlib import Path
from fastapi.responses import FileResponse
from app.core.config import settings

@router.get("/sessions/{session_id}/video")
def get_session_video(
    session_id: str,
    core_service: CorePersistenceService = Depends(get_core_service)
):
    """
    Retrieve the uploaded video file for a specific session.
    """
    # Sanitize session_id to prevent path traversal
    if not re.match(r"^[0-9a-fA-F\-]{36}$", session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format.")

    session = core_service.get_processing_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Processing session not found.")
        
    media_dir = Path(settings.media_root).resolve() / "sessions" / session_id
    media_dir = media_dir.resolve()
    
    # Double check path traversal protection
    if not str(media_dir).startswith(str(Path(settings.media_root).resolve())):
        raise HTTPException(status_code=403, detail="Forbidden.")
        
    if not media_dir.exists() or not media_dir.is_dir():
        raise HTTPException(status_code=404, detail="Media directory not found for session.")
        
    # Find the video file
    video_files = list(media_dir.glob("source.*"))
    if not video_files:
        raise HTTPException(status_code=404, detail="Video source not found for session.")
        
    video_path = video_files[0]
    
    ext = video_path.suffix.lower()
    content_type = "video/mp4"
    if ext == ".webm":
        content_type = "video/webm"
    elif ext == ".mkv":
        content_type = "video/x-matroska"
    
    return FileResponse(
        path=str(video_path),
        filename=video_path.name,
        media_type=content_type,
        headers={"Accept-Ranges": "bytes"}
    )


@router.get("/sessions/{session_id}/observations", response_model=List[TrackObservationDomain])
def get_session_observations(
    session_id: str,
    after_frame: int = -1,
    core_service: CorePersistenceService = Depends(get_core_service)
):
    """
    Retrieves frame-by-frame tracking observations for a given session.
    """
    if not re.match(r"^[0-9a-fA-F\-]{36}$", session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format.")

    session = core_service.get_processing_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Processing session not found.")

    obs = core_service.get_session_observations(session_id)
    if after_frame >= 0:
        obs = [o for o in obs if o.frame_number > after_frame]
    return obs

@router.get("/sessions/{session_id}/zone", response_model=dict)
def get_session_zone(
    session_id: str,
    core_service: CorePersistenceService = Depends(get_core_service)
):
    session = core_service.get_processing_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Processing session not found.")
    return session.restricted_zone or {}

@router.put("/sessions/{session_id}/zone", response_model=dict)
def save_session_zone(
    session_id: str,
    zone_req: ZoneCreateRequest,
    db: Session = Depends(get_db),
    core_service: CorePersistenceService = Depends(get_core_service)
):
    session = core_service.get_processing_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Processing session not found.")
    
    zone_dict = zone_req.model_dump()
    session.restricted_zone = zone_dict
    core_service.update_processing_session(session)
    db.commit()
    
    recalculator = ZoneRecalculator(db)
    recalculator.recalculate(session_id, zone_dict)
    
    return zone_dict

@router.delete("/sessions/{session_id}/zone")
def delete_session_zone(
    session_id: str,
    db: Session = Depends(get_db),
    core_service: CorePersistenceService = Depends(get_core_service)
):
    session = core_service.get_processing_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Processing session not found.")
    
    session.restricted_zone = None
    core_service.update_processing_session(session)
    db.commit()
    
    recalculator = ZoneRecalculator(db)
    recalculator.recalculate(session_id, None)
    
    return {"message": "Zone cleared"}

from fastapi import BackgroundTasks
from app.api.schemas.sessions import ZoneCreateRequest

@router.post("/sessions/{session_id}/analyze")
def start_analysis(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    core_service: CorePersistenceService = Depends(get_core_service),
):
    from app.api.video import _run_async_processing_pipeline, get_yolo_detector
    detector = get_yolo_detector()
    session = core_service.get_processing_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Processing session not found.")
        
    if session.status != "UPLOADED":
        raise HTTPException(status_code=400, detail=f"Session is already {session.status}.")
        
    if not session.restricted_zone:
        raise HTTPException(status_code=400, detail="A restricted zone must be saved before starting analysis.")
        
    # Transition to STARTED
    session.status = "STARTED"
    core_service.update_processing_session(session)
    db.commit()
    
    # We must construct the path and filename 
    from app.core.config import settings
    media_dir = Path(settings.media_root) / "sessions" / session_id
    video_files = list(media_dir.glob("source.*"))
    if not video_files:
        raise HTTPException(status_code=404, detail="Video source not found.")
        
    video_path = str(video_files[0])
    original_filename = video_files[0].name
    
    background_tasks.add_task(
        _run_async_processing_pipeline,
        session_id=session_id,
        temp_path=video_path,
        original_filename=original_filename,
        detector=detector,
        zone_data=session.restricted_zone
    )
    
    return {"status": "STARTED"}

from fastapi import Response

@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    core_service: CorePersistenceService = Depends(get_core_service)
):
    """
    Permanently delete a processing session and its associated data and media.
    """
    # Sanitize session_id to prevent path traversal
    if not re.match(r"^[0-9a-fA-F\-]{36}$", session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format.")

    session_domain = core_service.get_processing_session(session_id)
    if not session_domain:
        raise HTTPException(status_code=404, detail="Processing session not found.")
        
    if session_domain.status in ("STARTED", "PROCESSING"):
        raise HTTPException(status_code=409, detail="Cannot delete a session while processing is active.")
        
    # Media quarantine strategy
    media_dir = Path(settings.media_root).resolve() / "sessions" / session_id
    quarantine_dir = Path(settings.media_root).resolve() / "sessions" / f"{session_id}.deleted"
    
    media_exists = media_dir.exists() and media_dir.is_dir()
    
    if media_exists:
        try:
            # First, clean up any existing old quarantine from a previous failure
            if quarantine_dir.exists():
                shutil.rmtree(quarantine_dir, ignore_errors=True)
            
            # Move media to quarantine
            media_dir.rename(quarantine_dir)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to quarantine session media: {str(e)}")

    try:
        # DB Deletion
        # 1. Explicitly delete track_observations (no cascade from session)
        db.execute(delete(TrackObservation).where(TrackObservation.processing_session_id == session_id))
        
        # 2. Delete ProcessingSession ORM object (cascades to tracks, events, risks, evidence)
        db_session = db.query(ProcessingSession).filter_by(session_id=session_id).first()
        if db_session:
            db.delete(db_session)
            
        db.commit()
    except Exception as e:
        db.rollback()
        # Restore media from quarantine on failure
        if media_exists and quarantine_dir.exists():
            try:
                quarantine_dir.rename(media_dir)
            except:
                pass # Best effort recovery
        raise HTTPException(status_code=500, detail=f"Database deletion failed: {str(e)}")
        
    # Transaction committed successfully, safely remove quarantined media
    if media_exists and quarantine_dir.exists():
        shutil.rmtree(quarantine_dir, ignore_errors=True)
        
    return Response(status_code=204)

