import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, ForeignKey, 
    Enum as SQLEnum, Table
)
from sqlalchemy.types import JSON
from sqlalchemy.dialects.postgresql import JSONB

JSONVariant = JSONB().with_variant(JSON(), 'sqlite')
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class EventType(str, enum.Enum):
    TRACK_STARTED = 'TRACK_STARTED'
    TRACK_ENDED = 'TRACK_ENDED'
    ZONE_ENTRY = 'ZONE_ENTRY'
    ZONE_EXIT = 'ZONE_EXIT'
    LOITERING = 'LOITERING'
    RAPID_MOVEMENT = 'RAPID_MOVEMENT'
    DIRECTION_CHANGE = 'DIRECTION_CHANGE'
    MULTIPLE_OBJECT_PROXIMITY = 'MULTIPLE_OBJECT_PROXIMITY'


class RiskLevel(str, enum.Enum):
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    CRITICAL = 'CRITICAL'


class Priority(str, enum.Enum):
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    CRITICAL = 'CRITICAL'


class RiskAssessmentStatus(str, enum.Enum):
    OPEN = 'OPEN'
    ACKNOWLEDGED = 'ACKNOWLEDGED'
    RESOLVED = 'RESOLVED'


class EvidenceType(str, enum.Enum):
    FRAME = 'FRAME'
    VIDEO_SEGMENT = 'VIDEO_SEGMENT'


class ProcessingSession(Base):
    """
    Represents a discrete run or stream processing session.
    """
    __tablename__ = 'processing_sessions'

    session_id = Column(String, primary_key=True)
    source_id = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="STARTED")
    created_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    restricted_zone = Column(JSONVariant, nullable=True)
    processed_until_frame = Column(Integer, nullable=True)
    processed_until_timestamp = Column(Float, nullable=True)

    tracks = relationship("Track", back_populates="session", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="session", cascade="all, delete-orphan")
    risk_assessments = relationship("RiskAssessment", back_populates="session", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="session", cascade="all, delete-orphan")


class Track(Base):
    """
    Represents a detected and tracked object across frames within a processing session.
    """
    __tablename__ = 'tracks'

    id = Column(String, primary_key=True)
    processing_session_id = Column(String, ForeignKey('processing_sessions.session_id'), nullable=False, index=True)
    session_track_id = Column(Integer, nullable=False)
    class_id = Column(Integer, nullable=True)
    class_name = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    latest_bbox = Column(JSONVariant, nullable=True)

    session = relationship("ProcessingSession", back_populates="tracks")
    events = relationship("Event", back_populates="track")


class TrackObservation(Base):
    """
    Represents a bounding box observation of a track in a specific frame.
    """
    __tablename__ = 'track_observations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    processing_session_id = Column(String, ForeignKey('processing_sessions.session_id'), nullable=False, index=True)
    track_id = Column(String, ForeignKey('tracks.id'), nullable=False, index=True)
    
    frame_number = Column(Integer, nullable=False, index=True)
    timestamp_seconds = Column(Float, nullable=False, index=True)
    
    class_name = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    
    # Bounding box coordinates in source resolution
    bbox_x1 = Column(Float, nullable=False)
    bbox_y1 = Column(Float, nullable=False)
    bbox_x2 = Column(Float, nullable=False)
    bbox_y2 = Column(Float, nullable=False)

    session = relationship("ProcessingSession")
    track = relationship("Track")


risk_assessment_events = Table(
    'risk_assessment_events',
    Base.metadata,
    Column('assessment_id', String, ForeignKey('risk_assessments.assessment_id'), primary_key=True),
    Column('event_id', String, ForeignKey('events.event_id'), primary_key=True)
)


class Event(Base):
    """
    Represents an intelligence event (e.g., LOITERING, ZONE_ENTRY) detected in the system.
    """
    __tablename__ = 'events'

    event_id = Column(String, primary_key=True)
    processing_session_id = Column(String, ForeignKey('processing_sessions.session_id'), nullable=False, index=True)
    
    event_type = Column(SQLEnum(EventType), nullable=False, index=True)
    frame_number = Column(Integer, nullable=False)
    timestamp_seconds = Column(Float, nullable=False)
    description = Column(String, nullable=False)
    
    track_id = Column(String, ForeignKey('tracks.id'), nullable=True, index=True)
    
    # Stores domain-specific data such as zone_id, loitering_duration, etc.
    evidence_data = Column(JSONVariant, nullable=True)

    session = relationship("ProcessingSession", back_populates="events")
    track = relationship("Track", back_populates="events")
    
    risk_assessments = relationship("RiskAssessment", secondary=risk_assessment_events, back_populates="contributing_events")
    evidence_items = relationship("Evidence", back_populates="event", cascade="all, delete-orphan")


class RiskAssessment(Base):
    """
    Represents an escalated risk assessment based on one or more contributing events.
    """
    __tablename__ = 'risk_assessments'

    assessment_id = Column(String, primary_key=True)
    processing_session_id = Column(String, ForeignKey('processing_sessions.session_id'), nullable=False, index=True)
    
    risk_level = Column(SQLEnum(RiskLevel), nullable=False)
    priority = Column(SQLEnum(Priority), nullable=False)
    status = Column(SQLEnum(RiskAssessmentStatus), nullable=False)
    reason = Column(String, nullable=False)

    session = relationship("ProcessingSession", back_populates="risk_assessments")
    contributing_events = relationship("Event", secondary=risk_assessment_events, back_populates="risk_assessments")
    
    evidence_items = relationship("Evidence", back_populates="assessment", cascade="all, delete-orphan")


class Evidence(Base):
    """
    Represents metadata for a piece of evidence (frame or video segment) tied to an event or assessment.
    Does NOT store raw media bytes.
    """
    __tablename__ = 'evidence'

    evidence_id = Column(String, primary_key=True)
    processing_session_id = Column(String, ForeignKey('processing_sessions.session_id'), nullable=True, index=True)
    
    evidence_type = Column(SQLEnum(EvidenceType), nullable=False)
    
    source_id = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    
    # Structured metadata for the frame or segment
    frame_metadata = Column(JSONVariant, nullable=True)
    segment_metadata = Column(JSONVariant, nullable=True)
    
    event_id = Column(String, ForeignKey('events.event_id'), nullable=True, index=True)
    assessment_id = Column(String, ForeignKey('risk_assessments.assessment_id'), nullable=True, index=True)

    session = relationship("ProcessingSession", back_populates="evidence")
    event = relationship("Event", back_populates="evidence_items")
    assessment = relationship("RiskAssessment", back_populates="evidence_items")
