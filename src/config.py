"""Central configuration, loaded from environment / .env.

Kept import-light so it can be used from the CLI scripts, the Streamlit app,
and the tests without pulling in heavy ML dependencies.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    # LLM
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")

    # Embeddings
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2"
    )
    embedding_dim: int = _int("EMBEDDING_DIM", 768)

    # Reranking
    rerank_enabled: bool = _bool("RERANK_ENABLED", False)
    rerank_model: str = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

    # Hybrid retrieval
    rrf_k: int = _int("RRF_K", 60)
    retrieval_candidates: int = _int("RETRIEVAL_CANDIDATES", 50)
    retrieval_top_k: int = _int("RETRIEVAL_TOP_K", 5)

    # Debate
    max_debate_rounds: int = _int("MAX_DEBATE_ROUNDS", 3)

    # Web search fallback (used when the knowledge base has nothing relevant)
    web_search_enabled: bool = _bool("WEB_SEARCH_ENABLED", True)
    web_search_results: int = _int("WEB_SEARCH_RESULTS", 6)

    # Postgres
    pg_host: str = os.getenv("PGHOST", "localhost")
    pg_port: int = _int("PGPORT", 5432)
    pg_user: str = os.getenv("PGUSER", "agent_user")
    pg_password: str = os.getenv("PGPASSWORD", "agent_pass")
    pg_database: str = os.getenv("PGDATABASE", "agent_db")

    @property
    def pg_dsn(self) -> str:
        return (
            f"host={self.pg_host} port={self.pg_port} user={self.pg_user} "
            f"password={self.pg_password} dbname={self.pg_database}"
        )


settings = Settings()
