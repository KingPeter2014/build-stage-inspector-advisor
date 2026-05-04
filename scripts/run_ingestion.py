#!/usr/bin/env python3
"""
scripts/run_ingestion.py
Open-source ingestion pipeline: source -> clean -> chunk -> embed -> vector store.

Usage:
    python scripts/run_ingestion.py
    python scripts/run_ingestion.py --source-dir ./docs --env staging
    python scripts/run_ingestion.py --source-type web --web-manifest data/web_sources/official_vic_sources.json
"""
import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_ingestion.etl.cleaner import DocumentCleaner
from data_ingestion.chunking.chunker import ChunkStrategy, get_chunker
from data_ingestion.enrichment import enrich_document_metadata
from data_ingestion.identity import sha256_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingestion")


def _build_source_and_store(
    provider: str,
    source_dir: str,
    env: str,
    source_type: str,
    web_manifest: str,
):
    """Return (connector, vector_store) for the OSS runtime."""
    if provider != "open_source":
        raise ValueError("Only the open_source runtime provider is supported.")

    from config.settings import get_settings
    from data_ingestion.sources.file_connector import LocalFileConnector
    from data_ingestion.sources.web_connector import WebPageConnector
    from storage.vector_store.qdrant_store import QdrantVectorStore
    settings = get_settings()
    collection_name = settings.qdrant_collection_name or f"buildstage_documents_{env}"
    connector = (
        WebPageConnector.from_manifest(web_manifest)
        if source_type == "web"
        else LocalFileConnector(source_dir)
    )
    return (
        connector,
        QdrantVectorStore(url=settings.qdrant_url,
                          api_key=settings.qdrant_api_key or None,
                          collection_name=collection_name),
    )


def run_ingestion(
    provider: str,
    source_dir: str,
    env: str = "development",
    source_type: str = "file",
    web_manifest: str = "data/web_sources/official_vic_sources.json",
) -> dict:
    stats = {"docs_fetched": 0, "docs_cleaned": 0, "chunks_indexed": 0, "errors": 0}
    start = time.perf_counter()

    source_label = web_manifest if source_type == "web" else source_dir
    log.info(f"Starting ingestion | provider={provider} env={env} source={source_label}")

    connector, vector_store = _build_source_and_store(
        provider,
        source_dir,
        env,
        source_type,
        web_manifest,
    )
    cleaner = DocumentCleaner(redact_pii=True, min_length=50)
    chunker = get_chunker(ChunkStrategy.FIXED_TOKENS, chunk_size=512, chunk_overlap=64)

    for raw_doc in connector.fetch():
        stats["docs_fetched"] += 1
        try:
            cleaned = cleaner.process(raw_doc)
            if cleaned is None:
                continue
            stats["docs_cleaned"] += 1
            if cleaned.pii_detected:
                log.warning(f"PII redacted in doc {raw_doc.id}")

            metadata = enrich_document_metadata(
                source=cleaned.source,
                metadata=cleaned.metadata,
                source_type=cleaned.source_type,
            )
            document_hash = sha256_text(cleaned.content)
            metadata = {
                **metadata,
                "document_id": cleaned.id,
                "document_hash": document_hash,
            }
            chunks = chunker.chunk(cleaned.id, cleaned.content, metadata=metadata)
            vector_store.delete_by_document(cleaned.id)
            vector_store.upsert_chunks(chunks)
            stats["chunks_indexed"] += len(chunks)
            log.info(f"Indexed {raw_doc.id} -> {len(chunks)} chunks")

        except Exception as e:
            stats["errors"] += 1
            log.error(f"Failed to process {raw_doc.id}: {e}")

    stats["elapsed_seconds"] = round(time.perf_counter() - start, 2)
    log.info(f"Ingestion complete | {stats}")
    return stats


def main():
    parser = argparse.ArgumentParser(description="Build Stage Inspector Advisor ingestion pipeline")
    parser.add_argument("--provider", default="open_source",
                        choices=["open_source"],
                        help="Runtime provider. Only open_source is supported.")
    parser.add_argument("--source-dir", default="./data/raw_docs")
    parser.add_argument("--source-type", default="file",
                        choices=["file", "web"],
                        help="Source connector to use.")
    parser.add_argument("--web-manifest", default="data/web_sources/official_vic_sources.json",
                        help="JSON manifest of allowlisted official web sources.")
    parser.add_argument("--env", default="development",
                        choices=["development", "staging", "production"])
    args = parser.parse_args()
    run_ingestion(
        args.provider,
        args.source_dir,
        args.env,
        source_type=args.source_type,
        web_manifest=args.web_manifest,
    )


if __name__ == "__main__":
    main()
