#!/usr/bin/env python3
"""
scripts/run_ingestion.py
Provider-aware ingestion pipeline: source → clean → chunk → embed → vector store.

Usage:
    python scripts/run_ingestion.py                              # open_source (default)
    python scripts/run_ingestion.py --provider azure             # ADLS Gen2 → Azure AI Search
    python scripts/run_ingestion.py --provider aws               # S3 → OpenSearch
    python scripts/run_ingestion.py --provider gcp               # GCS → Vertex Vector Search
    python scripts/run_ingestion.py --source-dir ./docs --env staging
"""
import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_ingestion.etl.cleaner import DocumentCleaner
from data_ingestion.chunking.chunker import ChunkStrategy, get_chunker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingestion")


def _build_source_and_store(provider: str, source_dir: str, env: str):
    """Return (connector, vector_store) for the selected provider."""
    if provider == "azure":
        from providers.azure.data_ingestion.adf_connector import ADLSGen2Connector
        from providers.azure.storage.ai_search_store import AzureAISearchStore
        return ADLSGen2Connector(prefix=source_dir), AzureAISearchStore()

    if provider == "aws":
        from providers.aws.data_ingestion.glue_connector import S3SourceConnector
        from providers.aws.storage.opensearch_store import OpenSearchVectorStore
        return S3SourceConnector(prefix=source_dir), OpenSearchVectorStore()

    if provider == "gcp":
        from providers.gcp.data_ingestion.dataflow_connector import GCSSourceConnector
        from providers.gcp.storage.vertex_vector_search import VertexVectorSearch
        return GCSSourceConnector(prefix=source_dir), VertexVectorSearch()

    # Default: open_source
    from config.settings import get_settings
    from data_ingestion.sources.file_connector import LocalFileConnector
    from storage.vector_store.qdrant_store import QdrantVectorStore
    settings = get_settings()
    return (
        LocalFileConnector(source_dir),
        QdrantVectorStore(url=settings.qdrant_url,
                          api_key=settings.qdrant_api_key or None,
                          collection_name=f"llmops_{env}"),
    )


def run_ingestion(provider: str, source_dir: str, env: str = "development") -> dict:
    stats = {"docs_fetched": 0, "docs_cleaned": 0, "chunks_indexed": 0, "errors": 0}
    start = time.perf_counter()

    log.info(f"Starting ingestion | provider={provider} env={env} source={source_dir}")

    connector, vector_store = _build_source_and_store(provider, source_dir, env)
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

            chunks = chunker.chunk(cleaned.id, cleaned.content, metadata=cleaned.metadata)
            vector_store.upsert_chunks(chunks)
            stats["chunks_indexed"] += len(chunks)
            log.info(f"Indexed {raw_doc.id} → {len(chunks)} chunks")

        except Exception as e:
            stats["errors"] += 1
            log.error(f"Failed to process {raw_doc.id}: {e}")

    stats["elapsed_seconds"] = round(time.perf_counter() - start, 2)
    log.info(f"Ingestion complete | {stats}")
    return stats


def main():
    parser = argparse.ArgumentParser(description="LLMOps ingestion pipeline")
    parser.add_argument("--provider", default="open_source",
                        choices=["open_source", "azure", "aws", "gcp"],
                        help="Target provider stack")
    parser.add_argument("--source-dir", default="./data/raw_docs")
    parser.add_argument("--env", default="development",
                        choices=["development", "staging", "production"])
    args = parser.parse_args()
    run_ingestion(args.provider, args.source_dir, args.env)


if __name__ == "__main__":
    main()
