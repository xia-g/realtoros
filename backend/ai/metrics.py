"""Knowledge Foundation Platform — Prometheus metrics."""

try:
    from prometheus_client import Counter, Histogram, Gauge

    documents_processed_total = Counter("knowledge_documents_total", "Documents processed", ["status", "doc_type"])
    ocr_duration_seconds = Histogram("knowledge_ocr_duration_seconds", "OCR duration", ["provider"])
    classification_duration_seconds = Histogram("knowledge_classification_duration_seconds", "Classification duration", ["strategy"])
    extraction_duration_seconds = Histogram("knowledge_extraction_duration_seconds", "Entity extraction duration", ["doc_type"])
    resolution_duration_seconds = Histogram("knowledge_resolution_duration_seconds", "Entity resolution duration", ["entity_type"])
    graph_nodes_total = Gauge("knowledge_graph_nodes_total", "Total graph nodes")
    graph_edges_total = Gauge("knowledge_graph_edges_total", "Total graph edges")
    embedding_generation_seconds = Histogram("knowledge_embedding_duration_seconds", "Embedding generation duration")
    search_latency_seconds = Histogram("knowledge_search_latency_seconds", "Search latency", ["entity_type"])

    # AI metrics (P2.1)
    ai_calls_total = Counter("ai_calls_total", "AI provider calls", ["provider", "model", "status"])
    ai_cost_total = Counter("ai_cost_total", "AI cost in USD", ["provider", "model"])
    ai_latency_seconds = Histogram("ai_latency_seconds", "AI provider latency", ["provider", "model"])
    ai_provider_failures_total = Counter("ai_provider_failures_total", "Provider failures", ["provider", "error_type"])
    ai_budget_rejections_total = Counter("ai_budget_rejections_total", "Budget rejections", ["level"])
    ai_fallback_total = Counter("ai_fallback_total", "Fallback activations", ["primary_provider", "fallback_provider"])
    ai_prompt_injection_detected_total = Counter("ai_prompt_injection_detected_total", "Prompt injection events", ["severity"])

    # Context Builder metrics (P3)
    context_build_duration_seconds = Histogram("context_build_duration_seconds", "Context build duration", buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0))
    context_tokens_total = Histogram("context_tokens_total", "Context tokens per section", ["section"])
    context_entities_total = Gauge("context_entities_total", "Entities included in context")
    context_documents_total = Gauge("context_documents_total", "Documents included in context")
    context_dedup_ratio = Gauge("context_dedup_ratio", "Deduplication ratio (removed/total)")
    context_truncations_total = Counter("context_truncations_total", "Context truncation events", ["section"])
    context_overflow_total = Counter("context_overflow_total", "Context overflow errors")

    # Memory Layer metrics (P4)
    knowledge_sessions_active = Gauge("knowledge_sessions_active", "Active knowledge sessions")
    knowledge_messages_total = Counter("knowledge_messages_total", "Total messages appended")
    knowledge_memory_tokens_total = Counter("knowledge_memory_tokens_total", "Memory token count consumed")
    knowledge_session_expired_total = Counter("knowledge_session_expired_total", "Sessions expired")
    knowledge_memory_truncation_total = Counter("knowledge_memory_truncation_total", "Memory truncation events")

    # Security Layer metrics (P5)
    knowledge_security_scans_total = Counter("knowledge_security_scans_total", "Security scans performed")
    knowledge_security_findings_total = Counter("knowledge_security_findings_total", "Security findings detected")
    knowledge_security_critical_total = Counter("knowledge_security_critical_total", "Critical security findings")
    knowledge_security_sanitized_total = Counter("knowledge_security_sanitized_total", "Content sanitization events")
    knowledge_security_scan_duration_seconds = Histogram(
        "knowledge_security_scan_duration_seconds", "Security scan duration",
        buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1),
    )
    knowledge_injection_attempts_total = Counter("knowledge_injection_attempts_total", "Injection attempt events")
    knowledge_regulation_security_events_total = Counter(
        "knowledge_regulation_security_events_total", "Regulatory security events",
        ["event_type"],
    )

    # Agent Runtime metrics (P6)
    agent_requests_total = Counter("agent_requests_total", "Agent requests", ["intent"])
    agent_request_duration_seconds = Histogram("agent_request_duration_seconds", "Agent request duration", buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0))
    agent_tool_calls_total = Counter("agent_tool_calls_total", "Agent tool calls", ["tool_name"])
    agent_tool_failures_total = Counter("agent_tool_failures_total", "Agent tool failures", ["tool_name"])
    agent_intent_total = Counter("agent_intent_total", "Agent intent distribution", ["intent"])
    agent_response_tokens_total = Histogram("agent_response_tokens_total", "Agent response tokens")
    agent_rate_limit_hits_total = Counter("agent_rate_limit_hits_total", "Rate limit hits", ["user_id"])

    agent_limit_hit_total = Counter(
        "agent_limit_hit_total", "Agent execution limit hits", ["limit_type"]
    )
    agent_active_sessions_total = Gauge("agent_active_sessions_total", "Active agent sessions")

except ImportError:
    class _Stub:
        def labels(self, **kwargs):
            return self
        def inc(self, n=1):
            pass
        def dec(self, n=1):
            pass
        def observe(self, n):
            pass
        def set(self, n):
            pass

    documents_processed_total = _Stub()
    ocr_duration_seconds = _Stub()
    classification_duration_seconds = _Stub()
    extraction_duration_seconds = _Stub()
    resolution_duration_seconds = _Stub()
    graph_nodes_total = _Stub()
    graph_edges_total = _Stub()
    embedding_generation_seconds = _Stub()
    search_latency_seconds = _Stub()
    ai_calls_total = _Stub()
    ai_cost_total = _Stub()
    ai_latency_seconds = _Stub()
    ai_provider_failures_total = _Stub()
    ai_budget_rejections_total = _Stub()
    ai_fallback_total = _Stub()
    ai_prompt_injection_detected_total = _Stub()
    context_build_duration_seconds = _Stub()
    context_tokens_total = _Stub()
    context_entities_total = _Stub()
    context_documents_total = _Stub()
    context_dedup_ratio = _Stub()
    context_truncations_total = _Stub()
    context_overflow_total = _Stub()

    # Memory Layer metrics (P4)
    knowledge_sessions_active = _Stub()
    knowledge_messages_total = _Stub()
    knowledge_memory_tokens_total = _Stub()
    knowledge_session_expired_total = _Stub()
    knowledge_memory_truncation_total = _Stub()

    # Security Layer metrics (P5)
    knowledge_security_scans_total = _Stub()
    knowledge_security_findings_total = _Stub()
    knowledge_security_critical_total = _Stub()
    knowledge_security_sanitized_total = _Stub()
    knowledge_security_scan_duration_seconds = _Stub()
    knowledge_injection_attempts_total = _Stub()
    knowledge_regulation_security_events_total = _Stub()

    # Agent Runtime metrics (P6)
    agent_requests_total = _Stub()
    agent_request_duration_seconds = _Stub()
    agent_tool_calls_total = _Stub()
    agent_tool_failures_total = _Stub()
    agent_intent_total = _Stub()
    agent_response_tokens_total = _Stub()
    agent_rate_limit_hits_total = _Stub()
    agent_limit_hit_total = _Stub()
    agent_active_sessions_total = _Stub()