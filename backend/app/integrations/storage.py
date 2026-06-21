from __future__ import annotations

import re

import httpx

from app.config import Settings


class SupabaseStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def bucket(self) -> str:
        return self.settings.supabase_storage_bucket

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.supabase_url and self.settings.supabase_service_role_key)

    def upload(
        self,
        *,
        path: str,
        data: bytes,
        content_type: str | None = None,
    ) -> tuple[str, str]:
        if not self.is_configured:
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

    def download(self, *, bucket: str, path: str) -> bytes:
        if not self.is_configured:
            raise RuntimeError("Supabase Storage is not configured and the uploaded asset was not stored inline.")

        base_url = self.settings.supabase_url.rstrip("/")
        url = f"{base_url}/storage/v1/object/{bucket}/{path}"
        headers = {
            "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
            "apikey": self.settings.supabase_service_role_key,
        }
        with httpx.Client(timeout=self.settings.http_timeout_seconds) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.content


def storage_path_for_upload(dataset_id: str, import_id: str, filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip("-") or "upload"
    return f"datasets/{dataset_id}/imports/{import_id}/{cleaned}"
