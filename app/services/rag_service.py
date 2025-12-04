"""Retrieval-Augmented Generation service using Google Gemini."""

from __future__ import annotations

import logging
from threading import Lock
from typing import Optional

from llama_index.core import Settings, SimpleDirectoryReader, VectorStoreIndex
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.llms.gemini import Gemini

from app.config import get_settings

LOGGER = logging.getLogger(__name__)


class RAGEngine:
    """Load documents once and expose a thread-safe query method."""

    _instance: Optional["RAGEngine"] = None
    _lock: Lock = Lock()

    def __new__(cls) -> "RAGEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._settings = get_settings()
        self._query_engine = self._build_query_engine()
        self._initialized = True

    def _build_query_engine(self):  # type: ignore[no-untyped-def]
        data_dir = self._settings.data_dir
        if not data_dir.exists():
            LOGGER.warning("Data directory %s not found; using fallback responses.", data_dir)
            return None

        try:
            Settings.llm = Gemini(
                model=self._settings.gemini_model,
                api_key=self._settings.google_api_key,
            )
            Settings.embed_model = GeminiEmbedding(
                model_name=self._settings.gemini_embedding_model,
                api_key=self._settings.google_api_key,
            )
            documents = SimpleDirectoryReader(input_dir=str(data_dir)).load_data()
            if not documents:
                LOGGER.warning("No documents found under %s; using fallback responses.", data_dir)
                return None
            index = VectorStoreIndex.from_documents(documents)
            return index.as_query_engine()
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("Failed to build RAG index: %s", exc)
            return None

    def query(self, prompt: str) -> str:
        if not prompt:
            return "No input provided."
        if self._query_engine is None:
            llm = Gemini(
                model=self._settings.gemini_model,
                api_key=self._settings.google_api_key,
            )
            response = llm.complete(f"You are a helpful assistant. Answer briefly: {prompt}")
            return response.text

        response = self._query_engine.query(prompt)
        if hasattr(response, "response"):
            return response.response  # type: ignore[return-value]
        return str(response)
