import os
import tempfile
import uuid
import logging
from pathlib import Path
from functools import lru_cache

import cv2
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.database import get_db, SessionLocal

from app.services.video_processing_service import VideoProcessingService
from app.services.video_source import LocalVideoSource
from app.services.video_stream import VideoStream, VideoStreamError
from app.services.video_processing_response import VideoProcessingResponse, AsyncVideoProcessingResponse
from app.services.video_processing_status import VideoProcessingStatus
from app.core.config import get_detection_config, settings
from app.services.detection.yolo_detector import YOLODetector
from app.services.tracking.config import TrackingConfig
from app.services.events.config import EventIntelligenceConfig
from app.services.risk.config import RiskConfig
from app.services.persistence.orchestrator import ProcessingPersistenceOrchestrator

logger = logging.getLogger(__name__)

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"}

@lru_cache
def get_yolo_detector() -> YOLODetector:
    config = get_detection_config()
    return YOLODetector(config=config)


router = APIRouter(
    prefix="/video",
    tags=["Video"],
)


@router.get("/metadata")
def get_video_metadata(source: str) -> dict:
    """
    Return metadata for a local video source.
    """

    video_source = LocalVideoSource(source)
    video_path = Path(video_source.get_source())

    if not video_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Video source not found.",
        )

    stream = VideoStream(video_source)

    try:
        stream.open()
        metadata = stream.get_metadata()

        return metadata.model_dump()

    except VideoStreamError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    finally:
        stream.close()


def _run_processing_pipeline(
    video_source: LocalVideoSource,
    source_type: str,
    db: Session,
    detector: YOLODetector,
    max_frames: int | None = None,
    frame_skip: int | None = None,
    response_source_name: str | None = None,
) -> VideoProcessingResponse:
    
    if max_frames is not None and max_frames < 1:
        raise HTTPException(
            status_code=400,
            detail="max_frames must be greater than 0.",
        )

    if frame_skip is not None and frame_skip < 0:
        raise HTTPException(
            status_code=400,
            detail="frame_skip must be greater than or equal to 0.",
        )

    tracking_config = TrackingConfig()
    event_config = EventIntelligenceConfig()
    risk_config = RiskConfig()
    
    from app.api.routes.sessions import get_core_service, get_evidence_service
    core_service = get_core_service(db)
    evidence_service = get_evidence_service(db)
    orchestrator = ProcessingPersistenceOrchestrator(core_service, evidence_service)

    service = VideoProcessingService(
        detector=detector,
        tracking_config=tracking_config,
        event_config=event_config,
        risk_config=risk_config,
        generate_evidence=True,
        persistence_orchestrator=orchestrator
    )

    session_id = str(uuid.uuid4())
    session = orchestrator.start_session(session_id, video_source.get_source(), source_type)
    db.commit()
    
    try:
        result = service.process(
            video_source,
            session=session,
            max_frames=max_frames,
            frame_skip=frame_skip,
        )
        db.commit()
        
        final_source_name = response_source_name if response_source_name else result.source

        return VideoProcessingResponse(
            source=final_source_name,
            frames_processed=result.processing.frames_processed,
            first_frame_number=result.processing.first_frame_number,
            last_frame_number=result.processing.last_frame_number,
            total_frames_read=result.processing.total_frames_read,
            frames_skipped=result.processing.frames_skipped,
            inference_frames_skipped=result.processing.inference_frames_skipped,
            status=result.status,
        )

    except Exception as exc:
        # Always rollback the transaction first to clear any broken state from complete_session
        db.rollback()
        
        # Always mark the session as FAILED on any error.
        try:
            orchestrator.fail_session(session)
            db.commit()
        except Exception:
            logger.exception(f"Failed to mark session {session_id} as FAILED")
            
        if isinstance(exc, VideoStreamError):
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc
        raise HTTPException(status_code=500, detail="Internal server error during video processing.") from exc


def _run_async_processing_pipeline(
    session_id: str,
    temp_path: str,
    original_filename: str,
    detector: YOLODetector,
    max_frames: int | None = None,
    frame_skip: int | None = None,
    zone_data: dict | None = None
) -> None:
    success = False
    db = SessionLocal()
    try:
        from app.api.routes.sessions import get_core_service, get_evidence_service
        core_service = get_core_service(db)
        evidence_service = get_evidence_service(db)
        orchestrator = ProcessingPersistenceOrchestrator(core_service, evidence_service)

        session = orchestrator.core.get_processing_session(session_id)
        if not session:
            logger.error(f"Session {session_id} not found in background task.")
            return

        tracking_config = TrackingConfig()
        event_config = EventIntelligenceConfig()
        risk_config = RiskConfig()

        zones = []
        if zone_data:
            from app.services.events.zones import Zone
            zones = [Zone(**zone_data)]

        service = VideoProcessingService(
            detector=detector,
            tracking_config=tracking_config,
            event_config=event_config,
            zones=zones,
            risk_config=risk_config,
            generate_evidence=True,
            persistence_orchestrator=orchestrator
        )

        video_source = LocalVideoSource(temp_path)

        logger.info(f"BACKGROUND_PROCESSING_START | session={session_id}")
        try:
            service.process(
                video_source,
                session=session,
                max_frames=max_frames,
                frame_skip=frame_skip,
            )
            db.commit()
            success = True
            logger.info(f"BACKGROUND_PROCESSING_COMPLETE | session={session_id}")
        except Exception as exc:
            db.rollback()
            # Always mark the session as FAILED regardless of where the error occurred.
            # The previous logic skipped fail_session when processing_completed was True
            # (i.e., YOLO finished but persistence failed), leaving the session stuck as STARTED.
            try:
                orchestrator.fail_session(session)
                db.commit()
            except Exception:
                logger.exception(f"Failed to mark session {session_id} as FAILED")
            logger.exception(f"Background processing failed for session {session_id}")
    finally:
        db.close()
        if not success:
            if temp_path and os.path.exists(temp_path):
                try:
                    import shutil
                    shutil.rmtree(os.path.dirname(temp_path), ignore_errors=True)
                except Exception:
                    pass



@router.get("/process", response_model=VideoProcessingResponse)
def process_video(
    source: str,
    max_frames: int | None = None,
    frame_skip: int | None = None,
    detector: YOLODetector = Depends(get_yolo_detector),
    db: Session = Depends(get_db)
) -> dict:
    """
    Process frames from a local video source.
    """
    video_source = LocalVideoSource(source)
    video_path = Path(video_source.get_source())

    if not video_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Video source not found.",
        )

    return _run_processing_pipeline(
        video_source=video_source,
        source_type="LOCAL_FILE",
        db=db,
        detector=detector,
        max_frames=max_frames,
        frame_skip=frame_skip
    )


@router.post("/upload", response_model=AsyncVideoProcessingResponse)
def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    max_frames: int | None = Query(None),
    frame_skip: int | None = Query(None),
    detector: YOLODetector = Depends(get_yolo_detector),
    db: Session = Depends(get_db)
) -> dict:
    """
    Upload a video file for future analysis.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing.")

    original_filename = Path(file.filename).name
    ext = Path(original_filename).suffix.lower()

    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file extension. Allowed: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}")

    max_size = settings.max_upload_size_bytes
    bytes_received = 0
    temp_path = None

    try:
        # Create session synchronously FIRST to get ID
        session_id = str(uuid.uuid4())
        
        # Create persistent session storage path
        media_dir = Path(settings.media_root) / "sessions" / session_id
        media_dir.mkdir(parents=True, exist_ok=True)
        temp_path = str(media_dir / f"source{ext}")

        with open(temp_path, "wb") as f:
            while chunk := file.file.read(65536):
                bytes_received += len(chunk)
                if bytes_received > max_size:
                    raise HTTPException(status_code=413, detail=f"File exceeds maximum upload size of {max_size} bytes.")
                f.write(chunk)
                
        if bytes_received == 0:
            raise HTTPException(status_code=400, detail="Empty upload.")

        # OpenCV readability check
        cap = cv2.VideoCapture(temp_path)
        try:
            if not cap.isOpened():
                raise HTTPException(status_code=422, detail="Invalid or unreadable video content.")
            success, _ = cap.read()
            if not success:
                raise HTTPException(status_code=422, detail="Invalid or unreadable video content.")
        finally:
            cap.release()

        from app.api.routes.sessions import get_core_service, get_evidence_service
        core_service = get_core_service(db)
        evidence_service = get_evidence_service(db)
        orchestrator = ProcessingPersistenceOrchestrator(core_service, evidence_service)
        
        # Create session as UPLOADED
        session = orchestrator.start_session(session_id, original_filename, "UPLOAD", status="UPLOADED")
        db.commit()

        # Do not schedule background tasks here.
        # temp_path must not be deleted because it is stored.
        temp_path = None

        return AsyncVideoProcessingResponse(
            session_id=session_id,
            status=VideoProcessingStatus.UPLOADED,
        )

    finally:
        # Cleanup only if an error occurred before scheduling the background task
        if temp_path and os.path.exists(temp_path):
            try:
                import shutil
                shutil.rmtree(os.path.dirname(temp_path), ignore_errors=True)
            except Exception:
                pass

@router.post("/demo")
def start_demo_camera(
    background_tasks: BackgroundTasks,
    detector: YOLODetector = Depends(get_yolo_detector),
    db: Session = Depends(get_db)
) -> dict:
    """
    Start a Demo Camera session using the test_video fixture.
    """
    fixture_path = Path("tests/fixtures/test_video.mp4").resolve()
    if not fixture_path.exists():
        # Try relative to backend root
        fixture_path = (Path(__file__).parent.parent.parent / "tests" / "fixtures" / "test_video.mp4").resolve()
        if not fixture_path.exists():
            raise HTTPException(status_code=404, detail="Demo video fixture not found.")

    session_id = str(uuid.uuid4())
    
    media_dir = Path(settings.media_root) / "sessions" / session_id
    media_dir.mkdir(parents=True, exist_ok=True)
    temp_path = str(media_dir / "source.mp4")

    import shutil
    shutil.copy2(fixture_path, temp_path)

    from app.api.routes.sessions import get_core_service, get_evidence_service
    core_service = get_core_service(db)
    evidence_service = get_evidence_service(db)
    orchestrator = ProcessingPersistenceOrchestrator(core_service, evidence_service)
    
    # Create session as STARTED directly
    session = orchestrator.start_session(session_id, "Demo Camera", "DEMO_CAMERA", status="STARTED")
    
    # Pre-configure a restricted zone that catches the people in test_video.mp4
    # test_video.mp4 is 1280x720. 
    # A central block from x=300 to x=900, y=200 to y=600 will definitely catch movement.
    zone_data = {
        "zone_id": "demo_zone",
        "name": "Demo Restricted Area",
        "polygon": [
            {"x": 300, "y": 200},
            {"x": 900, "y": 200},
            {"x": 900, "y": 600},
            {"x": 300, "y": 600}
        ]
    }
    session.restricted_zone = zone_data
    core_service.update_processing_session(session)
    db.commit()

    background_tasks.add_task(
        _run_async_processing_pipeline,
        session_id=session_id,
        temp_path=temp_path,
        original_filename="Demo Camera",
        detector=detector,
        zone_data=zone_data
    )

    return {
        "session_id": session_id,
        "status": "STARTED"
    }
