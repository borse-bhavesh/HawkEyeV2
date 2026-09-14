from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("Calling health...")
response = client.get("/api/v1/health")
print(response.status_code)

print("Calling sessions...")
response = client.get("/api/v1/sessions")
print(response.status_code)

print("Done")
