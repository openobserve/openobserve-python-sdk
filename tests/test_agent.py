"""
Tests for GenAI agent identity propagation and span stamping.
"""

import pytest
from opentelemetry import baggage
from opentelemetry import context as otel_context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from openobserve import openobserve_agent
from openobserve.agent import AgentIdentity, AgentIdentitySpanProcessor


def _record_span(processor, attributes=None):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(processor)
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    tracer = provider.get_tracer(__name__)
    with tracer.start_as_current_span("test-span", attributes=attributes):
        pass

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    return spans[0]


def _attach_inherited_identity(agent_id="inherited-id", agent_name="Inherited Agent"):
    ctx = baggage.set_baggage("gen_ai.agent.id", agent_id)
    ctx = baggage.set_baggage("gen_ai.agent.name", agent_name, context=ctx)
    return otel_context.attach(ctx)


def test_static_agent_identity_stamps_all_recording_spans_and_overwrites_existing_attrs():
    span = _record_span(
        AgentIdentitySpanProcessor(
            AgentIdentity(agent_id="agent-123", agent_name="Support Agent")
        ),
        attributes={
            "gen_ai.agent.id": "old-id",
            "gen_ai.agent.name": "Old Name",
            "other": "kept",
        },
    )

    assert span.attributes["gen_ai.agent.id"] == "agent-123"
    assert span.attributes["gen_ai.agent.name"] == "Support Agent"
    assert span.attributes["other"] == "kept"


def test_inherited_baggage_identity_is_used_without_local_identity():
    token = _attach_inherited_identity()
    try:
        span = _record_span(AgentIdentitySpanProcessor())
    finally:
        otel_context.detach(token)

    assert span.attributes["gen_ai.agent.id"] == "inherited-id"
    assert span.attributes["gen_ai.agent.name"] == "Inherited Agent"


def test_openobserve_agent_name_only_overrides_static_and_suppresses_inherited_id():
    token = _attach_inherited_identity()
    try:
        with openobserve_agent(agent_name="  Local Agent  "):
            assert baggage.get_baggage("gen_ai.agent.name") == "Local Agent"
            assert baggage.get_baggage("gen_ai.agent.id") is None
            span = _record_span(
                AgentIdentitySpanProcessor(
                    AgentIdentity(agent_id="static-id", agent_name="Static Agent")
                )
            )
    finally:
        otel_context.detach(token)

    assert "gen_ai.agent.id" not in span.attributes
    assert span.attributes["gen_ai.agent.name"] == "Local Agent"


def test_openobserve_agent_rejects_only_empty_values():
    with pytest.raises(ValueError, match="Agent identity requires"):
        with openobserve_agent(agent_id=" ", agent_name="\t"):
            pass
