#!/usr/bin/env python3
"""
Run a quick RAG smoke query against the gateway or local RAG pipeline.

Examples:
    python scripts/smoke_rag_query.py --api-url http://localhost:4000/v1/rag/query
    python scripts/smoke_rag_query.py --local --question "What should I check at waterproofing?"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.schemas.rag import RAGQueryRequest
from serving.rag.service import build_filter, query_knowledge_base_api, query_knowledge_base_local


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test a RAG query")
    parser.add_argument(
        "--question",
        default="For bathroom waterproofing in a Victorian Class 1 home, what should I look for under NCC DTS?",
    )
    parser.add_argument("--api-url", default="http://localhost:4000/v1/rag/query")
    parser.add_argument("--local", action="store_true", help="Use the local pipeline instead of the gateway API")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--document-type", default="")
    parser.add_argument("--inspection-stage", default="waterproofing")
    parser.add_argument("--jurisdiction", default="VIC")
    parser.add_argument("--building-class", default="1")
    parser.add_argument("--tenant-id", default="")
    args = parser.parse_args()

    request = RAGQueryRequest(
        question=args.question,
        filter_by=build_filter(
            document_type=args.document_type,
            inspection_stage=args.inspection_stage,
            jurisdiction=args.jurisdiction,
            building_class=args.building_class,
            tenant_id=args.tenant_id,
        ),
        top_k=args.top_k,
    )

    response = (
        query_knowledge_base_local(request)
        if args.local
        else query_knowledge_base_api(request, api_url=args.api_url)
    )

    print("\nAnswer")
    print(response.answer)
    print("\nSources")
    for index, source in enumerate(response.sources, start=1):
        metadata = source.metadata or {}
        title = metadata.get("source_title") or metadata.get("filename") or source.document_id
        locator = metadata.get("clause") or metadata.get("section") or metadata.get("volume") or ""
        print(f"{index}. score={source.score:.3f} id={source.document_id} title={title} {locator}".strip())


if __name__ == "__main__":
    main()
