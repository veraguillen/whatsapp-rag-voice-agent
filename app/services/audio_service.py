"""Audio utilities: Gemini STT and edge-tts TTS."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

import edge_tts
from google.generativeai import upload_file
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from app.config import get_settings

LOGGER = logging.getLogger(__name__)
_settings = get_settings()


async def transcribe_audio(file_path: Path | str) -> str:
    """Transcribe audio using Google Gemini 1.5 Flash."""

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    def _call_gemini_transcribe() -> str:
        import google.generativeai as genai

        genai.configure(api_key=_settings.google_api_key)
        file_response = upload_file(str(path))
        model = genai.GenerativeModel(_settings.gemini_model)
        response = model.generate_content(
            [
                "Please transcribe this audio file. Return only the transcribed text, nothing else.",
                file_response,
            ],
            safety_settings={
                HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            },
        )
        return response.text

    return await asyncio.to_thread(_call_gemini_transcribe)


async def generate_audio(text: str, output_path: Path | str | None = None) -> Path:
    """Generate speech from text using edge-tts, save to /tmp or specified path."""

    if output_path is None:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            path = Path(tmp_file.name)
    else:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

    def _call_edge_tts() -> Path:
        import asyncio as aio

        async def _tts_task():
            communicate = edge_tts.Communicate(text, voice=_settings.edge_tts_voice)
            await communicate.save(str(path))

        aio.run(_tts_task())
        return path

    return await asyncio.to_thread(_call_edge_tts)
