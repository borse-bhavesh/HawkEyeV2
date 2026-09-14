import os
import requests
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient

app = FastAPI()

@app.get("/video")
def get_video():
    return FileResponse(path="test_video.mp4", media_type="video/mp4", headers={"Accept-Ranges": "bytes"})

client = TestClient(app)

def test_range_request():
    with open("test_video.mp4", "wb") as f:
        f.write(b"A" * 2000)

    # Test full request
    resp_full = client.get("/video")
    assert resp_full.status_code == 200
    assert len(resp_full.content) == 2000

    # Test range request
    headers = {"Range": "bytes=0-1023"}
    resp_range = client.get("/video", headers=headers)
    print("Status Code:", resp_range.status_code)
    print("Content-Range:", resp_range.headers.get("Content-Range"))
    print("Content-Length:", resp_range.headers.get("Content-Length"))
    print("Length of content:", len(resp_range.content))

if __name__ == "__main__":
    test_range_request()
    if os.path.exists("test_video.mp4"):
        os.remove("test_video.mp4")
