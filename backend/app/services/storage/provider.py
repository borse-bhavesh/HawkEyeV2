from typing import Protocol, runtime_checkable
import os
import shutil
from pathlib import Path
from app.core.config import settings

@runtime_checkable
class StorageProvider(Protocol):
    def upload(self, session_id: str, file_path: str, filename: str) -> None:
        """Uploads a local file to storage under the given session."""
        ...

    def download(self, session_id: str, filename: str, destination_path: str) -> None:
        """Downloads a file from storage to a local path."""
        ...

    def delete(self, session_id: str) -> None:
        """Deletes all files associated with a session."""
        ...

    def get_presigned_url(self, session_id: str, filename: str, expires_in: int = 3600) -> str:
        """Gets a presigned URL or public URL for a file."""
        ...


class LocalFilesystemStorageProvider:
    def __init__(self):
        self.media_root = Path(settings.media_root).resolve() / "sessions"

    def _get_session_dir(self, session_id: str) -> Path:
        return self.media_root / session_id

    def upload(self, session_id: str, file_path: str, filename: str) -> None:
        session_dir = self._get_session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        dest = session_dir / filename
        if str(Path(file_path).resolve()) != str(dest.resolve()):
            shutil.copy2(file_path, dest)

    def download(self, session_id: str, filename: str, destination_path: str) -> None:
        source = self._get_session_dir(session_id) / filename
        if not source.exists():
            raise FileNotFoundError(f"File {source} not found")
        if str(source.resolve()) != str(Path(destination_path).resolve()):
            shutil.copy2(source, destination_path)

    def delete(self, session_id: str) -> None:
        session_dir = self._get_session_dir(session_id)
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)

    def get_presigned_url(self, session_id: str, filename: str, expires_in: int = 3600) -> str:
        # Local provider doesn't truly have presigned URLs; returns a mock or route path.
        # Currently the app serves local files directly via the FastAPI endpoint.
        return f"/api/v1/sessions/{session_id}/video"


class SupabaseStorageProvider:
    def __init__(self):
        from supabase import create_client, Client
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise ValueError("Supabase credentials missing")
        self.bucket = settings.supabase_storage_bucket
        self.client: Client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    def _get_path(self, session_id: str, filename: str) -> str:
        return f"sessions/{session_id}/{filename}"

    def upload(self, session_id: str, file_path: str, filename: str) -> None:
        remote_path = self._get_path(session_id, filename)
        with open(file_path, "rb") as f:
            self.client.storage.from_(self.bucket).upload(
                file=f,
                path=remote_path,
                file_options={"x-upsert": "true"}
            )

    def download(self, session_id: str, filename: str, destination_path: str) -> None:
        remote_path = self._get_path(session_id, filename)
        data = self.client.storage.from_(self.bucket).download(remote_path)
        with open(destination_path, "wb") as f:
            f.write(data)

    def delete(self, session_id: str) -> None:
        prefix = f"sessions/{session_id}/"
        files = self.client.storage.from_(self.bucket).list(prefix)
        if files:
            paths_to_delete = [f"{prefix}{f['name']}" for f in files]
            if paths_to_delete:
                self.client.storage.from_(self.bucket).remove(paths_to_delete)

    def get_presigned_url(self, session_id: str, filename: str, expires_in: int = 3600) -> str:
        remote_path = self._get_path(session_id, filename)
        res = self.client.storage.from_(self.bucket).create_signed_url(remote_path, expires_in)
        return res["signedURL"]


def get_storage_provider() -> StorageProvider:
    if settings.storage_provider == "supabase":
        return SupabaseStorageProvider()
    return LocalFilesystemStorageProvider()
