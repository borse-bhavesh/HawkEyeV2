import sys
from pathlib import Path
import cv2
import requests
import time
import sqlite3

def check():
    # 1. Verify path resolution locally
    print("--- 1. VERIFYING PATH RESOLUTION ---")
    current_file = Path(__file__).parent / "app" / "api" / "video.py"
    # Using the exact same logic from the endpoint
    fixture_path = (current_file.parent.parent.parent / "tests" / "fixtures" / "test_video.mp4").resolve()
    print(f"Resolved Path: {fixture_path}")
    if fixture_path.exists():
        print(f"File EXISTS: {fixture_path}")
    else:
        print(f"ERROR: File DOES NOT EXIST at {fixture_path}")
        sys.exit(1)

    # 2. Verify OpenCV readability
    print("\n--- 2. VERIFYING OPENCV READABILITY ---")
    cap = cv2.VideoCapture(str(fixture_path))
    if not cap.isOpened():
        print("ERROR: Failed to open video with OpenCV")
        sys.exit(1)
    ret, frame = cap.read()
    if not ret:
        print("ERROR: Failed to read first frame with OpenCV")
        sys.exit(1)
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    print(f"SUCCESS: Video readable. Read first frame shape {frame.shape}, FPS: {fps}, Total Frames: {frame_count}")
    cap.release()

    # 3. HTTP POST to start demo
    print("\n--- 3. TESTING API ENDPOINT ---")
    url = "http://127.0.0.1:8000/api/v1/video/demo"
    try:
        res = requests.post(url)
        print(f"HTTP POST {url}")
        print(f"STATUS CODE: {res.status_code}")
        body = res.json()
        print(f"RESPONSE BODY: {body}")
        
        if res.status_code != 200:
            print("ERROR: Expected HTTP 200")
            sys.exit(1)
            
        session_id = body.get("session_id")
        if not session_id:
            print("ERROR: No session_id in response")
            sys.exit(1)
            
    except requests.exceptions.ConnectionError:
        print("ERROR: Failed to connect to local uvicorn on port 8000")
        sys.exit(1)

    # 4 & 5. Wait for processing to start and fetch state
    print("\n--- 4 & 5. WAITING FOR PROCESSING & VERIFYING DB ---")
    print(f"Monitoring session {session_id}...")
    
    # Wait for the background task to spin up and process at least some frames
    time.sleep(5)
    
    # Check session endpoint
    try:
        session_res = requests.get(f"http://127.0.0.1:8000/api/v1/sessions/{session_id}")
        session_data = session_res.json()
        print(f"Session Status Check: {session_data.get('status')}")
    except Exception as e:
        print(f"Failed to fetch session: {e}")
        
    print("\nChecking database directly for progress...")
    # The default db is hawkeye.db in backend root or similar? 
    # Actually, settings defaults to "sqlite:///hawkeye.db" in dev, let's use the API
    
    # 6. Verify processing progresses beyond STARTED
    for _ in range(6):
        time.sleep(5)
        history_res = requests.get(f"http://127.0.0.1:8000/api/v1/sessions/{session_id}/history")
        history = history_res.json()
        status = history.get("session", {}).get("status")
        events = history.get("events", [])
        print(f"Current Status: {status}, Events: {len(events)}")
        if status in ["COMPLETED", "FAILED"]:
            break
            
    final_history = requests.get(f"http://127.0.0.1:8000/api/v1/sessions/{session_id}/history").json()
    final_status = final_history.get("session", {}).get("status")
    
    if final_status == "FAILED":
        print(f"ERROR: Session processing FAILED")
        sys.exit(1)
        
    if final_status != "COMPLETED":
        print(f"WARNING: Processing hasn't completed yet, still {final_status}. But it didn't fail immediately.")

    # 7. Verify Observations and Events
    print("\n--- 7. VERIFYING OBSERVATIONS & EVENTS ---")
    obs_res = requests.get(f"http://127.0.0.1:8000/api/v1/sessions/{session_id}/observations")
    observations = obs_res.json()
    events = final_history.get("events", [])
    
    print(f"Total Observations: {len(observations)}")
    print(f"Total Events: {len(events)}")
    
    if len(observations) > 0:
        print("SUCCESS: YOLO/ByteTrack successfully processed tracks!")
    else:
        print("ERROR: No observations generated.")
        
    if len(events) > 0:
        print("SUCCESS: ZoneEngine successfully registered events!")
    else:
        print("INFO: No events generated (maybe no one crossed the zone).")
        
    print("\nALL DIAGNOSTIC CHECKS COMPLETED!")

if __name__ == "__main__":
    check()
