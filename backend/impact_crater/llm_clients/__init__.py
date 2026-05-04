"""LLM abstraction per ADR-0007.

Modules:
  - base       — `LLMClient` Protocol + supporting types
  - exceptions — `LLMOperationFailed` + transient/retryable variants
  - anthropic_client — Anthropic Claude implementation (Sonnet + Opus)
  - google_client    — Google Gemini implementation (Flash + embeddings)
  - prompts    — Jinja2 prompt-template loader
  - cache      — read-through cache against the SQLite cache_index table
  - router     — LLMRouter that maps Operation → (provider, model) and
                 dispatches through the right client
"""
