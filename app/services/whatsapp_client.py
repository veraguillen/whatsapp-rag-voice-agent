"""Client utilities for interacting with the WhatsApp Cloud API."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import requests

from app.config import get_settings

LOGGER = logging.getLogger(__name__)


class WhatsAppClient:
    """Simple wrapper around the Graph API for WhatsApp Cloud."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._base_url = f"https://graph.facebook.com/{self._settings.graph_version}"
        self._token = self._settings.whatsapp_token
        self._phone_number_id = self._settings.phone_number_id

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def download_media(self, media_id: str) -> bytes:
        """Retrieve binary content for a media asset."""

        meta_url = f"{self._base_url}/{media_id}"
        resp = requests.get(meta_url, headers=self._auth_headers(), params={"fields": "url"}, timeout=30)
        resp.raise_for_status()
        media_url: Optional[str] = resp.json().get("url")
        if not media_url:
            raise RuntimeError("Media URL missing from WhatsApp response")

        media_resp = requests.get(media_url, headers=self._auth_headers(), timeout=30)
        media_resp.raise_for_status()
        return media_resp.content

    def upload_media(self, file_path: Path | str) -> str:
        """Upload an audio file and return the media id."""

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        url = f"{self._base_url}/{self._phone_number_id}/media"
        files = {"file": (path.name, path.read_bytes(), "audio/mpeg")}
        data = {"messaging_product": "whatsapp"}
        resp = requests.post(url, headers=self._auth_headers(), data=data, files=files, timeout=30)
        resp.raise_for_status()
        media_id: Optional[str] = resp.json().get("id")
        if not media_id:
            raise RuntimeError("Failed to obtain media id from WhatsApp")
        return media_id

    def send_message(self, to: str, text: str, media_id: Optional[str] = None) -> None:
        """Send a text or audio message to a WhatsApp user."""

        url = f"{self._base_url}/{self._phone_number_id}/messages"
        payload: dict[str, object] = {
            "messaging_product": "whatsapp",
            "to": to,
        }

        if media_id:
            payload.update({"type": "audio", "audio": {"id": media_id}})
        else:
            if not text:
                raise ValueError("Text message body is required when media_id is not provided")
            payload.update({"type": "text", "text": {"body": text[:1000]}})

        resp = requests.post(url, headers={**self._auth_headers(), "Content-Type": "application/json"}, json=payload, timeout=30)
        resp.raise_for_status()


WHATSAPP_CLIENT = WhatsAppClient()
