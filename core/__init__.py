"""
core — shared interfaces and schemas for all LLMOps provider stacks.

Import rules:
  - core imports only stdlib and pydantic (zero cloud SDKs).
  - Every provider (open_source, azure, aws, gcp) implements these ABCs.
"""
