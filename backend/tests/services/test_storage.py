import pytest
import os
import tempfile
from pathlib import Path
from app.services.storage.provider import LocalFilesystemStorageProvider, StorageProvider

class FakeStorageProvider:
    def __init__(self):
        self.files = {}

    def upload(self, session_id: str, file_path: str, filename: str) -> None:
        key = f"{session_id}/{filename}"
        with open(file_path, "rb") as f:
            self.files[key] = f.read()

    def download(self, session_id: str, filename: str, destination_path: str) -> None:
        key = f"{session_id}/{filename}"
        if key not in self.files:
            raise FileNotFoundError()
        with open(destination_path, "wb") as f:
            f.write(self.files[key])

    def delete(self, session_id: str) -> None:
        keys_to_delete = [k for k in self.files.keys() if k.startswith(f"{session_id}/")]
        for k in keys_to_delete:
            del self.files[k]

    def get_presigned_url(self, session_id: str, filename: str, expires_in: int = 3600) -> str:
        return f"https://fake.storage.com/{session_id}/{filename}"


def test_fake_storage_provider():
    provider: StorageProvider = FakeStorageProvider()
    
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"test data")
        temp_path = tf.name
        
    try:
        # Upload
        provider.upload("session1", temp_path, "video.mp4")
        
        # Download
        with tempfile.NamedTemporaryFile(delete=False) as download_tf:
            download_path = download_tf.name
            
        provider.download("session1", "video.mp4", download_path)
        
        with open(download_path, "rb") as f:
            assert f.read() == b"test data"
            
        # Presigned URL
        url = provider.get_presigned_url("session1", "video.mp4")
        assert url == "https://fake.storage.com/session1/video.mp4"
        
        # Delete
        provider.delete("session1")
        
        with pytest.raises(FileNotFoundError):
            provider.download("session1", "video.mp4", download_path)
            
    finally:
        os.remove(temp_path)
        if os.path.exists(download_path):
            os.remove(download_path)


def test_local_filesystem_provider():
    provider = LocalFilesystemStorageProvider()
    
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"local data")
        temp_path = tf.name
        
    try:
        provider.upload("session2", temp_path, "source.mp4")
        
        with tempfile.NamedTemporaryFile(delete=False) as download_tf:
            download_path = download_tf.name
            
        provider.download("session2", "source.mp4", download_path)
        
        with open(download_path, "rb") as f:
            assert f.read() == b"local data"
            
        # Delete
        provider.delete("session2")
        
        with pytest.raises(FileNotFoundError):
            provider.download("session2", "source.mp4", download_path)
            
    finally:
        os.remove(temp_path)
        if os.path.exists(download_path):
            os.remove(download_path)
        provider.delete("session2")  # cleanup dir if still exists
