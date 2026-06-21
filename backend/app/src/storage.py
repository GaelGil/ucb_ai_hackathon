from __future__ import annotations

import re

import httpx

from app.src.config import Settings


class SupabaseStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def bucket(self) -> str:
        return self.settings.supabase_storage_bucket

    def upload(
        self,
        *,
        path: str,
        data: bytes,
        content_type: str | None = None,
    ) -> tuple[str, str]:
        if not self.settings.supabase_url or not self.settings.supabase_service_role_key:
            return self.bucket, path

        base_url = self.settings.supabase_url.rstrip("/")
        url = f"{base_url}/storage/v1/object/{self.bucket}/{path}"
        headers = {
            "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
            "apikey": self.settings.supabase_service_role_key,
            "x-upsert": "true",
        }
        if content_type:
            headers["Content-Type"] = content_type

        with httpx.Client(timeout=self.settings.http_timeout_seconds) as client:
            response = client.post(url, headers=headers, content=data)
            response.raise_for_status()

        return self.bucket, path


def storage_path_for_upload(dataset_id: str, import_id: str, filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip("-") or "upload"
    return f"datasets/{dataset_id}/imports/{import_id}/{cleaned}"
