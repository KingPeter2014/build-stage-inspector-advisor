"""
serving/rag/pipeline.py
Retrieval-Augmented Generation pipeline.
Retrieves relevant chunks from the vector store and assembles context
for the LLM, with full OpenTelemetry tracing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import litellm

from storage.vector_store.qdrant_store import QdrantVectorStore, SearchResult
from storage.prompt_registry.registry import LocalPromptRegistry
from observability.tracing.tracer import get_tracer
from core.interfaces.rag_retriever import AbstractRAGRetriever, RetrievalRequest
from core.rag import RAGOptions, RAGSecurityMode, merge_retrieval_filters
from serving.rag.retriever import GenericRAGRetriever

tracer = get_tracer("rag_pipeline")


@dataclass
class RAGResponse:
    answer: str
    sources: list[SearchResult]
    prompt_version: int
    model: str
    usage: dict = field(default_factory=dict)


class RAGPipeline:
    def __init__(
        self,
        vector_store: QdrantVectorStore,
        prompt_registry: LocalPromptRegistry,
        model: str = "gpt-4o",
        top_k: int = 5,
        max_context_chars: int = 6000,
        rag_options: RAGOptions | None = None,
        retriever: AbstractRAGRetriever | None = None,
    ):
        self.vector_store = vector_store
        self.retriever = retriever or GenericRAGRetriever("open_source", vector_store)
        self.prompt_registry = prompt_registry
        self.model = model
        self.top_k = top_k
        self.max_context_chars = max_context_chars
        self.rag_options = rag_options or RAGOptions.from_env()
        self.rag_options.validate()

    def _build_context(self, results: list[SearchResult]) -> str:
        context_parts = []
        total_chars = 0
        for r in results:
            chunk = f"[Source: {r.metadata.get('filename', r.document_id)}]\n{r.content}"
            if total_chars + len(chunk) > self.max_context_chars:
                break
            context_parts.append(chunk)
            total_chars += len(chunk)
        return "\n\n---\n\n".join(context_parts)

    def query(
        self,
        question: str,
        filter_by: dict | None = None,
        acl_filter: dict | None = None,
    ) -> RAGResponse:
        with tracer.start_as_current_span("rag_query") as span:
            span.set_attribute("question", question[:200])
            span.set_attribute("rag_retrieval_mode", self.rag_options.retrieval_mode.value)
            span.set_attribute("rag_security_mode", self.rag_options.security_mode.value)

            if self.rag_options.security_mode.requires_acl_filter and not acl_filter:
                raise PermissionError(
                    f"RAG_SECURITY_MODE={self.rag_options.security_mode.value} requires acl_filter. "
                    "Pass user/group/tenant/document ACL constraints before retrieval."
                )

            effective_filter = merge_retrieval_filters(filter_by, acl_filter)
            if self.rag_options.security_mode == RAGSecurityMode.METADATA_FILTERING and not effective_filter:
                span.set_attribute("rag_metadata_filter_missing", True)

            # 1. Retrieve
            with tracer.start_as_current_span("retrieval"):
                results = self.retriever.retrieve(RetrievalRequest(
                    query=question,
                    top_k=self.top_k,
                    retrieval_mode=self.rag_options.retrieval_mode,
                    security_mode=self.rag_options.security_mode,
                    metadata_filter=filter_by,
                    acl_filter=acl_filter,
                )).results
            span.set_attribute("retrieved_chunks", len(results))

            # 2. Assemble context
            context = self._build_context(results)

            # 3. Fetch versioned prompt
            try:
                prompt_version = self.prompt_registry.get("rag_qa")
            except KeyError:
                # Register a default if none exists
                from storage.prompt_registry.registry import PromptVersion
                prompt_version = self.prompt_registry.push(PromptVersion(
                    name="rag_qa",
                    version=1,
                    template=(
                        "You are a helpful assistant. Answer the question using ONLY the context below. "
                        "If the answer is not in the context, say 'I don't know'.\n\n"
                        "Context:\n{{ context }}\n\n"
                        "Question: {{ question }}\n\nAnswer:"
                    ),
                ))

            prompt_text = prompt_version.render(context=context, question=question)
            span.set_attribute("prompt_version", prompt_version.version)

            # 4. Generate
            with tracer.start_as_current_span("llm_generate"):
                response = litellm.completion(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt_text}],
                    max_tokens=1024,
                )

            answer = response.choices[0].message.content

            return RAGResponse(
                answer=answer,
                sources=results,
                prompt_version=prompt_version.version,
                model=self.model,
                usage=dict(response.usage),
            )
