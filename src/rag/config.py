"""Runtime settings, read from environment variables prefixed with ``RAG_``."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAG_", extra="ignore")

    backend: Literal["offline", "azure"] = "offline"
    auth_mode: Literal["easy-auth", "dev-headers"] = "easy-auth"

    openai_endpoint: str = ""
    openai_api_version: str = "2024-10-21"
    chat_deployment: str = "chat"
    embedding_deployment: str = "embedding"
    embedding_dimensions: int = Field(default=1536, ge=8, le=3072)

    search_endpoint: str = ""
    search_index: str = "handbook"
    semantic_configuration: str = "default"

    top_k: int = Field(default=5, ge=1, le=50)
    min_reranker_score: float = Field(default=1.2, ge=0.0, le=4.0)
    max_question_chars: int = Field(default=2000, ge=50, le=20000)

    knowledge_base_path: str = "data/knowledge-base"
