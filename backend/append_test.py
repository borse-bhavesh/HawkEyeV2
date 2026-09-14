with open('tests/integration/test_video_orchestration.py', 'a') as f:
    f.write('''

def test_incremental_persistence_batching():
    """
    Verifies that persist_incremental_batch explicitly commits to the database,
    making observations and events visible to other database connections mid-processing.
    """
    db1 = SessionLocal()
    orchestrator, history_service = _setup_services(db1)
    
    source = LocalVideoSource(TEST_VIDEO)
    session_id = str(uuid.uuid4())
    
    session = orchestrator.start_session(session_id, source.get_source(), "LOCAL_FILE")
    db1.commit()
    
    # We mock service processing to just call persist_incremental_batch manually
    from app.repositories.domain import TrackDomain, TrackObservationDomain
    
    obs1 = TrackObservationDomain(
        id=str(uuid.uuid4()),
        processing_session_id=session_id,
        session_track_id=1,
        frame_number=10,
        timestamp_seconds=0.33,
        bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10},
        confidence=0.9,
        class_id=0,
        class_name="person"
    )
    
    track1 = TrackDomain(
        id=str(uuid.uuid4()),
        processing_session_id=session_id,
        session_track_id=1,
        class_id=0,
        class_name="person",
        confidence=0.9,
        latest_bbox={"x1": 0, "y1": 0, "x2": 10, "y2": 10}
    )
    
    orchestrator.persist_incremental_batch(
        session=session,
        tracks=[track1],
        observations=[obs1],
        events=[],
        last_frame=10,
        last_timestamp=0.33
    )
    
    # Now verify from a COMPLETELY SEPARATE database connection
    db2 = SessionLocal()
    try:
        _, history2 = _setup_services(db2)
        
        # Get observations (need core service)
        core2 = get_core_service(db2)
        obs_mid = core2.get_session_observations(session_id)
        assert len(obs_mid) == 1, "Observation should be visible in separate connection due to incremental commit"
        
        # Get session state
        sess2 = core2.get_processing_session(session_id)
        assert sess2.processed_until_frame == 10
        assert sess2.processed_until_timestamp == 0.33
    finally:
        db2.close()
        db1.close()
''')
