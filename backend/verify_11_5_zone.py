import requests
import time
from pathlib import Path
from app.db.database import SessionLocal
from app.db.models import ProcessingSession, TrackObservation, RiskAssessment, Evidence
from sqlalchemy import text

db = SessionLocal()

print("Starting Demo Camera...")
res = requests.post('http://127.0.0.1:8000/api/v1/video/demo')
if res.status_code != 200:
    print('Failed to start demo:', res.status_code, res.text)
    exit(1)
    
data = res.json()
session_id = data['session_id']
print(f'Started session: {session_id}')

timeout = 120
start_time = time.time()
final_status = 'STARTED'
print("Polling session status...")

while time.time() - start_time < timeout:
    session = db.query(ProcessingSession).filter(ProcessingSession.session_id == session_id).first()
    if session:
        final_status = session.status
        if final_status in ['COMPLETED', 'FAILED']:
            print(f'Session finished with status: {final_status}')
            break
    time.sleep(2)

if final_status not in ['COMPLETED', 'FAILED']:
    print(f'Session timed out after {timeout} seconds, status: {final_status}')

print("\n--- RESULTS ---")
obs_count = db.query(TrackObservation).filter(TrackObservation.processing_session_id == session_id).count()
event_count = db.execute(text(f"SELECT COUNT(*) FROM track_events WHERE session_id='{session_id}'")).scalar()
risk_count = db.query(RiskAssessment).filter(RiskAssessment.session_id == session_id).count()
evidence_count = db.query(Evidence).filter(Evidence.session_id == session_id).count()

print(f'Observations: {obs_count}')
print(f'Events: {event_count}')
print(f'Risks: {risk_count}')
print(f'Evidence: {evidence_count}')

events = db.execute(text(f"SELECT event_type FROM track_events WHERE session_id='{session_id}'")).fetchall()
zone_entries = [e[0] for e in events if e[0] == 'ZONE_ENTRY']
print(f'ZONE_ENTRY occurrences: {len(zone_entries)}')

media_dir = Path('D:/HawkEye_V2/media/sessions') / session_id
print(f'Media directory exists: {media_dir.exists()}')

video_res = requests.get(f'http://127.0.0.1:8000/api/v1/sessions/{session_id}/video', stream=True)
print(f'Video Endpoint HTTP Status: {video_res.status_code}')
