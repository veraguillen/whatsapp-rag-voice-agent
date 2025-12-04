"""WhatsApp webhook router with Gemini + edge-tts."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.services.audio_service import generate_audio, transcribe_audio
from app.services.rag_service import RAGEngine
from app.services.whatsapp_client import WHATSAPP_CLIENT

router = APIRouter()
LOGGER = logging.getLogger(__name__)
SETTINGS = get_settings()
RAG_ENGINE = RAGEngine()


def _extract_messages(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                msg_type = message.get("type")
                from_id = message.get("from")
                if not from_id:
                    continue
                if msg_type == "text":
                    messages.append(
                        {
                            "from": from_id,
                            "type": "text",
                            "text": message.get("text", {}).get("body", ""),
                        }
                    )
                elif msg_type == "audio":
                    audio_id = message.get("audio", {}).get("id")
                    if audio_id:
                        messages.append(
                            {
                                "from": from_id,
                                "type": "audio",
                                "audio_id": audio_id,
                                "mime_type": message.get("audio", {}).get("mime_type"),
                            }
                        )
    return messages


@router.get("/webhook")
async def verify_webhook(request: Request):
    """Verify webhook token from Meta."""
    params = request.query_params
    mode = params.get("hub.mode")
    challenge = params.get("hub.challenge")
    verify_token = params.get("hub.verify_token")

    if mode == "subscribe" and verify_token == SETTINGS.verify_token:
        LOGGER.info("Webhook verified successfully")
        return PlainTextResponse(content=challenge or "", status_code=200)
    LOGGER.warning("Webhook verification failed: invalid token")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_message(request: Request):
    """Receive and process messages from WhatsApp."""
    body = await request.json()
    messages = _extract_messages(body)
    if not messages:
        return {"status": "ignored"}

    LOGGER.info("Received %d message(s)", len(messages))
    tasks = [handle_message(message) for message in messages]
    await asyncio.gather(*tasks, return_exceptions=True)
    return {"status": "processed"}


async def handle_message(message: Dict[str, Any]) -> None:
    """Route message to appropriate handler."""
    try:
        if message["type"] == "text":
            await _handle_text_flow(message["from"], message.get("text", ""))
        elif message["type"] == "audio":
            await _handle_audio_flow(message["from"], message["audio_id"], message.get("mime_type"))
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.exception("Failed to handle message: %s", exc)
        await asyncio.to_thread(
            WHATSAPP_CLIENT.send_message,
            message["from"],
            "Ocurrió un error procesando tu mensaje. Por favor, intenta nuevamente.",
        )


async def _handle_text_flow(user_id: str, text: str) -> None:
    """Handle incoming text message: RAG query -> send text response."""
    if not text:
        await asyncio.to_thread(
            WHATSAPP_CLIENT.send_message,
            user_id,
            "No recibí texto. ¿Puedes intentarlo de nuevo?",
        )
        return
    LOGGER.info("Processing text from %s: %s", user_id, text[:50])
    rag_response = await asyncio.to_thread(RAG_ENGINE.query, text)
    LOGGER.info("Sending text response to %s", user_id)
    await asyncio.to_thread(WHATSAPP_CLIENT.send_message, user_id, rag_response)


async def _handle_audio_flow(user_id: str, audio_id: str, mime_type: str | None) -> None:
    """
    Handle incoming audio: download -> transcribe (Gemini) -> RAG query ->
    generate audio (edge-tts) -> upload -> send audio response.
    """
    LOGGER.info("Processing audio from %s (media_id: %s)", user_id, audio_id)

    # 1. Download audio from Meta
    media_bytes = await asyncio.to_thread(WHATSAPP_CLIENT.download_media, audio_id)
    suffix = (mime_type or "audio/ogg").split("/")[-1]
    with tempfile.NamedTemporaryFile(suffix=f".{suffix}", delete=False) as tmp_file:
        tmp_file.write(media_bytes)
        tmp_file.flush()
        tmp_path = Path(tmp_file.name)

    try:
        # 2. Transcribe with Gemini
        LOGGER.info("Transcribing audio with Gemini for %s", user_id)
        transcript = await transcribe_audio(tmp_path)
        LOGGER.info("Transcript: %s", transcript[:100])

        # 3. Query RAG
        LOGGER.info("Querying RAG for %s", user_id)
        rag_response = await asyncio.to_thread(RAG_ENGINE.query, transcript)

        # 4. Generate audio with edge-tts (saves to /tmp)
        LOGGER.info("Generating audio response with edge-tts for %s", user_id)
        audio_path = await generate_audio(rag_response)

        # 5. Upload audio to Meta
        LOGGER.info("Uploading audio to Meta for %s", user_id)
        media_id = await asyncio.to_thread(WHATSAPP_CLIENT.upload_media, audio_path)

        # 6. Send audio message
        LOGGER.info("Sending audio response to %s", user_id)
        await asyncio.to_thread(WHATSAPP_CLIENT.send_message, user_id, "", media_id)

        # Cleanup
        audio_path.unlink(missing_ok=True)
    finally:
        tmp_path.unlink(missing_ok=True)
