"""Initialize the pgvector schema. Run once after `docker compose up -d`.

    python -m scripts.init_db
"""
from __future__ import annotations

from src.config import settings
from src.rag import store


def main() -> None:
    print(f"Connecting to {settings.pg_host}:{settings.pg_port}/{settings.pg_database} ...")
    store.init_schema()
    s = store.stats()
    print("Schema ready.")
    print(f"  documents: {s['documents']}  chunks: {s['chunks']}")
    print(f"  embedding dim: {settings.embedding_dim}")


if __name__ == "__main__":
    main()
