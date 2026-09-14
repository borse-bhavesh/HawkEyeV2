import pytest
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.sqltypes import Enum

from app.db.models import (
    Base, ProcessingSession, Track, Event, RiskAssessment, Evidence,
    EventType, RiskLevel, Priority, RiskAssessmentStatus, EvidenceType,
    risk_assessment_events
)


@pytest.fixture(scope="module")
def mapper_registry():
    """Returns the SQLAlchemy registry for metadata inspection."""
    return Base.metadata


def test_tables_exist(mapper_registry):
    """Ensure all required tables are defined in the declarative base."""
    expected_tables = {
        'processing_sessions', 'tracks', 'events', 
        'risk_assessments', 'evidence', 'risk_assessment_events'
    }
    actual_tables = set(mapper_registry.tables.keys())
    assert expected_tables.issubset(actual_tables), f"Missing tables: {expected_tables - actual_tables}"


def test_processing_session_model():
    """Ensure ProcessingSession has correct schema, columns, and relationships."""
    mapper = inspect(ProcessingSession)
    
    # Primary Key
    assert mapper.primary_key[0].name == 'session_id'
    
    # Required/Nullable
    columns = mapper.columns
    assert not columns.session_id.nullable
    assert not columns.source_id.nullable
    assert not columns.source_type.nullable
    assert not columns.status.nullable
    assert not columns.created_at.nullable
    assert columns.started_at.nullable
    assert columns.completed_at.nullable
    
    # Relationships
    relationships = mapper.relationships
    assert 'tracks' in relationships
    assert 'events' in relationships
    assert 'risk_assessments' in relationships
    assert 'evidence' in relationships


def test_track_model():
    """Ensure Track has correct schema, columns, and relationships."""
    mapper = inspect(Track)
    
    # Primary Key
    assert mapper.primary_key[0].name == 'id'
    
    columns = mapper.columns
    # Foreign Key
    assert len(columns.processing_session_id.foreign_keys) == 1
    assert not columns.processing_session_id.nullable
    
    # Required/Nullable
    assert not columns.session_track_id.nullable
    assert columns.class_id.nullable
    assert columns.class_name.nullable
    assert columns.confidence.nullable
    
    # JSONB check
    assert isinstance(columns.latest_bbox.type, JSONB)
    assert columns.latest_bbox.nullable
    
    # Relationships
    assert 'session' in mapper.relationships
    assert 'events' in mapper.relationships


def test_event_model():
    """Ensure Event has correct schema, columns, and relationships."""
    mapper = inspect(Event)
    
    # Primary Key
    assert mapper.primary_key[0].name == 'event_id'
    
    columns = mapper.columns
    # Foreign Keys
    assert len(columns.processing_session_id.foreign_keys) == 1
    assert len(columns.track_id.foreign_keys) == 1
    assert columns.track_id.nullable
    
    # Enum
    assert isinstance(columns.event_type.type, Enum)
    assert columns.event_type.type.enum_class is EventType
    
    # Required
    assert not columns.frame_number.nullable
    assert not columns.timestamp_seconds.nullable
    assert not columns.description.nullable
    
    # JSONB check
    assert isinstance(columns.evidence_data.type, JSONB)
    assert columns.evidence_data.nullable
    
    # Relationships
    assert 'session' in mapper.relationships
    assert 'track' in mapper.relationships
    assert 'risk_assessments' in mapper.relationships
    assert 'evidence_items' in mapper.relationships


def test_risk_assessment_model():
    """Ensure RiskAssessment has correct schema, columns, and relationships."""
    mapper = inspect(RiskAssessment)
    
    # Primary Key
    assert mapper.primary_key[0].name == 'assessment_id'
    
    columns = mapper.columns
    assert len(columns.processing_session_id.foreign_keys) == 1
    
    # Enums
    assert isinstance(columns.risk_level.type, Enum)
    assert columns.risk_level.type.enum_class is RiskLevel
    
    assert isinstance(columns.priority.type, Enum)
    assert columns.priority.type.enum_class is Priority
    
    assert isinstance(columns.status.type, Enum)
    assert columns.status.type.enum_class is RiskAssessmentStatus
    
    assert not columns.reason.nullable
    
    # Relationships
    relationships = mapper.relationships
    assert 'session' in relationships
    assert 'contributing_events' in relationships
    assert 'evidence_items' in relationships


def test_evidence_model():
    """Ensure Evidence has correct schema, columns, and relationships."""
    mapper = inspect(Evidence)
    
    # Primary Key
    assert mapper.primary_key[0].name == 'evidence_id'
    
    columns = mapper.columns
    # Foreign Keys
    assert len(columns.processing_session_id.foreign_keys) == 1
    assert columns.processing_session_id.nullable
    
    assert len(columns.event_id.foreign_keys) == 1
    assert columns.event_id.nullable
    
    assert len(columns.assessment_id.foreign_keys) == 1
    assert columns.assessment_id.nullable
    
    # Enum
    assert isinstance(columns.evidence_type.type, Enum)
    assert columns.evidence_type.type.enum_class is EvidenceType
    
    assert not columns.source_id.nullable
    assert not columns.source_type.nullable
    
    # JSONB
    assert isinstance(columns.frame_metadata.type, JSONB)
    assert columns.frame_metadata.nullable
    
    assert isinstance(columns.segment_metadata.type, JSONB)
    assert columns.segment_metadata.nullable
    
    # Relationships
    assert 'session' in mapper.relationships
    assert 'event' in mapper.relationships
    assert 'assessment' in mapper.relationships


def test_no_raw_media_columns():
    """Ensure no raw binary/blob columns are defined in the schema."""
    for table_name, table in Base.metadata.tables.items():
        for column in table.columns:
            # We don't want LargeBinary or similar types for media storage
            col_type = type(column.type).__name__
            assert col_type not in ['LargeBinary', 'BLOB', 'BYTEA'], f"Raw media column found: {table_name}.{column.name}"


def test_model_domain_separation():
    """Ensure SQLAlchemy models don't bleed into Pydantic domain models or vice-versa."""
    from app.services.events.models import Event as DomainEvent
    from app.services.risk.models import RiskAssessment as DomainRisk
    
    # SQLAlchemy model should not be a subclass of BaseModel
    assert not hasattr(Event, 'model_dump')
    assert not hasattr(RiskAssessment, 'model_dump')
    
    # Domain model should not have SQLAlchemy metadata
    assert not hasattr(DomainEvent, '__tablename__')
    assert not hasattr(DomainRisk, '__tablename__')
