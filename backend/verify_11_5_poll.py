import requests
import time

print("Starting Demo Camera...")
res = requests.post('http://127.0.0.1:8000/api/v1/video/demo')
session_id = res.json()['session_id']
print(f'Started session: {session_id}')

timeout = 150
start_time = time.time()
final_status = 'STARTED'
print("Polling session APIs...")

observations = 0
events = 0
risks = 0
processed_until = None

while time.time() - start_time < timeout:
    try:
        hist_res = requests.get(f'http://127.0.0.1:8000/api/v1/sessions/{session_id}/history')
        if hist_res.status_code == 200:
            hist_data = hist_res.json()
            session = hist_data['session']
            final_status = session['status']
            processed_until = session.get('processed_until_timestamp')
            
            events = len(hist_data.get('events', []))
            risks = len(hist_data.get('risk_assessments', []))
            
        obs_res = requests.get(f'http://127.0.0.1:8000/api/v1/sessions/{session_id}/observations')
        if obs_res.status_code == 200:
            observations = len(obs_res.json())
            
        print(f"[{final_status}] Obs: {observations} | Evt: {events} | Risk: {risks} | Until: {processed_until}")
        
        if final_status in ['COMPLETED', 'FAILED']:
            break
            
    except Exception as e:
        print("Error polling:", e)
        
    time.sleep(5)
