"""Provider registry for RAG retrievers."""
from __future__ import annotations

from typing import Any, Callable

from core.interfaces.rag_retriever import AbstractRAGRetriever

RetrieverFactory = Callable[..., AbstractRAGRetriever]


def _oss_factory(**kwargs: Any) -> AbstractRAGRetriever:
    from providers.open_source.serving.rag import build_rag_retriever
    return build_rag_retriever(**kwargs)


RAG_RETRIEVER_FACTORIES: dict[str, RetrieverFactory] = {
    "open_source": _oss_factory,
}


def build_provider_rag_retriever(provider: str, **kwargs: Any) -> AbstractRAGRetriever:
    try:
        factory = RAG_RETRIEVER_FACTORIES[provider]
    except KeyError as exc:
        valid = ", ".join(sorted(RAG_RETRIEVER_FACTORIES))
        raise ValueError(f"Unknown RAG provider '{provider}'. Expected one of: {valid}") from exc
    return factory(**kwargs)
