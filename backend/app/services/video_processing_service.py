from dataclasses import dataclass, field
from typing import Optional

from app.services.frame_processor import (
    FrameProcessingResult,
    FrameProcessor,
)
from app.services.video_processing_config import (
    VideoProcessingConfig,
)
from app.services.video_processing_status import (
    VideoProcessingStatus,
)
from app.services.video_source import VideoSource
from app.services.video_stream import VideoStream
from app.services.detection.detector import Detector
from app.services.detection.performance_config import DetectionPerformanceConfig
from app.services.tracking.config import TrackingConfig
from app.services.tracking.byte_tracker import ByteTrackTracker
from app.services.events.config import EventIntelligenceConfig
from app.services.events.zones import Zone
from app.services.events.orchestrator import EventOrchestrator
from app.services.events.models import Event
from app.services.risk.config import RiskConfig
from app.services.risk.models import RiskAssessment
from app.services.risk.orchestrator import RiskOrchestrator
from app.services.evidence.models import Evidence
from app.services.evidence.orchestrator import EvidenceOrchestrator
from app.services.persistence.orchestrator import ProcessingPersistenceOrchestrator
from app.repositories.domain import ProcessingSessionDomain, TrackDomain, TrackObservationDomain


@dataclass(frozen=True)
class VideoProcessingResult:
    """
    Result returned after processing a video source.
    """

    source: str
    processing: FrameProcessingResult
    status: VideoProcessingStatus
    events: list[Event] = field(default_factory=list)
    risks: list[RiskAssessment] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


class VideoProcessingService:
    """
    Orchestrates video ingestion and frame processing.

    The service keeps workflow logic outside the API layer.
    """

    def __init__(
        self,
        processor: FrameProcessor | None = None,
        config: VideoProcessingConfig | None = None,
        detector: Detector | None = None,
        tracking_config: TrackingConfig | None = None,
        performance_config: DetectionPerformanceConfig | None = None,
        event_config: EventIntelligenceConfig | None = None,
        zones: list[Zone] | None = None,
        risk_config: RiskConfig | None = None,
        generate_evidence: bool = False,
        persistence_orchestrator: ProcessingPersistenceOrchestrator | None = None,
    ):
        self.provided_processor = processor
        self.config = config or VideoProcessingConfig()
        self.detector = detector
        self.tracking_config = tracking_config
        self.performance_config = performance_config
        self.event_config = event_config
        self.zones = zones or []
        self.risk_config = risk_config
        self.generate_evidence = generate_evidence
        self.persistence_orchestrator = persistence_orchestrator

    def process(
        self,
        source: VideoSource,
        max_frames: int | None = None,
        frame_skip: int | None = None,
        session: ProcessingSessionDomain | None = None,
    ) -> VideoProcessingResult:
        """
        Open a video source, process its frames, and close the stream.
        """

        stream = VideoStream(source)

        effective_max_frames = (
            max_frames
            if max_frames is not None
            else self.config.max_frames
        )

        effective_frame_skip = (
            frame_skip
            if frame_skip is not None
            else self.config.frame_skip
        )

        if (
            effective_max_frames is not None
            and effective_max_frames < 1
        ):
            raise ValueError(
                "max_frames must be greater than 0."
            )

        if effective_frame_skip < 0:
            raise ValueError(
                "frame_skip must be greater than or equal to 0."
            )

        try:
            stream.open()

            if self.provided_processor is not None:
                processor = self.provided_processor
            else:
                tracker = None
                if self.detector is not None and self.tracking_config is not None:
                    tracker = ByteTrackTracker(config=self.tracking_config)
                
                processor = FrameProcessor(
                    detector=self.detector,
                    tracker=tracker,
                    performance_config=self.performance_config
                )

            events: list[Event] = []
            orchestrator = None
            if self.event_config is not None:
                orchestrator = EventOrchestrator(
                    config=self.event_config,
                    zones=self.zones
                )

            unpersisted_observations = []
            unpersisted_events = []
            track_map = {}
            BATCH_SIZE = 30
            frames_since_last_persist = 0
            
            def handle_frame_processed(frame_num: int, ts: float, tracks: list):
                nonlocal frames_since_last_persist, unpersisted_observations, unpersisted_events, track_map
                
                frame_events = []
                if orchestrator:
                    frame_events = orchestrator.process_frame(frame_num, ts, tracks)
                    events.extend(frame_events)
                    unpersisted_events.extend(frame_events)
                    
                if self.persistence_orchestrator and session:
                    for t in tracks:
                        track_map[t.track_id] = t
                        unpersisted_observations.append(
                            TrackObservationDomain(
                                processing_session_id=session.session_id,
                                track_id=f"{session.session_id}-track-{t.track_id}",
                                frame_number=frame_num,
                                timestamp_seconds=ts,
                                class_name=t.class_name,
                                confidence=t.confidence,
                                bbox_x1=t.bounding_box.x1,
                                bbox_y1=t.bounding_box.y1,
                                bbox_x2=t.bounding_box.x2,
                                bbox_y2=t.bounding_box.y2
                            )
                        )
                        
                    frames_since_last_persist += 1
                    if frames_since_last_persist >= BATCH_SIZE:
                        track_domains = []
                        for t_id, t in track_map.items():
                            track_domains.append(
                                TrackDomain(
                                    id=f"{session.session_id}-track-{t.track_id}",
                                    processing_session_id=session.session_id,
                                    session_track_id=t.track_id,
                                    class_id=t.class_id,
                                    class_name=t.class_name,
                                    confidence=t.confidence,
                                    latest_bbox={"x1": t.bounding_box.x1, "y1": t.bounding_box.y1, "x2": t.bounding_box.x2, "y2": t.bounding_box.y2}
                                )
                            )
                        
                        self.persistence_orchestrator.persist_incremental_batch(
                            session=session,
                            tracks=track_domains,
                            observations=unpersisted_observations,
                            events=unpersisted_events,
                            last_frame=frame_num,
                            last_timestamp=ts
                        )
                        
                        unpersisted_observations = []
                        unpersisted_events = []
                        track_map = {}
                        frames_since_last_persist = 0

            result = processor.process(
                stream,
                max_frames=effective_max_frames,
                frame_skip=effective_frame_skip,
                on_frame_processed=handle_frame_processed
            )

            if orchestrator:
                final_events = orchestrator.finalize()
                events.extend(final_events)
                unpersisted_events.extend(final_events)

            risks: list[RiskAssessment] = []
            if self.risk_config is not None and self.risk_config.enabled and events:
                risk_orchestrator = RiskOrchestrator(config=self.risk_config)
                risks = risk_orchestrator.process_events(events)

            evidence: list[Evidence] = []
            if self.generate_evidence and (events or risks):
                evidence_orchestrator = EvidenceOrchestrator(source_id=source.get_source())
                evidence = evidence_orchestrator.process(events, risks)

            # Persistence Integration for the remaining batch + final completion
            if self.persistence_orchestrator and session:
                track_domains = []
                for t_id, t in track_map.items():
                    track_domains.append(
                        TrackDomain(
                            id=f"{session.session_id}-track-{t.track_id}",
                            processing_session_id=session.session_id,
                            session_track_id=t.track_id,
                            class_id=t.class_id,
                            class_name=t.class_name,
                            confidence=t.confidence,
                            latest_bbox={"x1": t.bounding_box.x1, "y1": t.bounding_box.y1, "x2": t.bounding_box.x2, "y2": t.bounding_box.y2}
                        )
                    )
                
                self.processing_completed = True
                
                self.persistence_orchestrator.complete_session(
                    session=session,
                    tracks=track_domains,
                    observations=unpersisted_observations,
                    events=unpersisted_events,
                    risk_assessments=risks,
                    evidence=evidence
                )

            return VideoProcessingResult(
                source=source.get_source(),
                processing=result,
                status=VideoProcessingStatus.COMPLETED,
                events=events,
                risks=risks,
                evidence=evidence
            )

        finally:
            stream.close()