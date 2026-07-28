# Native OpenTelemetry Agent Identity

This guide shows how to reproduce the OpenObserve Python SDK's trace behavior with the native OpenTelemetry Python SDK.

Use this when you already own your OpenTelemetry setup and do not want `openobserve_init(...)` to create providers/exporters for you.

## What The OpenObserve SDK Does

For traces, the SDK mainly does four things:

1. Creates an OpenTelemetry `TracerProvider`.
2. Configures OTLP exporters for OpenObserve endpoints and headers.
3. Applies `resource_attributes` through an OpenTelemetry `Resource`.
4. Adds agent identity to spans with `gen_ai.agent.id` and `gen_ai.agent.name`.

The agent identity behavior is intentionally span-based. `agent_id=` and `agent_name=` in `openobserve_init(...)` are process-wide defaults stamped on spans, not resource attributes. `openobserve_agent(...)` sets request-scoped identity using OpenTelemetry baggage and overrides those defaults.

## Option 1: Resource Attributes Only

This is the easiest native OpenTelemetry option when one process represents one static agent.

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

resource = Resource.create(
    {
        "service.name": "support-agent-worker",
        "service.version": "1.0.0",
        "deployment.environment": "production",
        "gen_ai.agent.name": "Support Agent",
    }
)

provider = TracerProvider(resource=resource)
exporter = OTLPSpanExporter(
    endpoint="http://localhost:5080/api/default/v1/traces",
    headers={
        "Authorization": "Basic <base64>",
        "stream-name": "default",
    },
)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)
```

Resource attributes are associated with all spans emitted by that provider through the OTLP `ResourceSpans` envelope. In OpenObserve, resource attributes are stored as service/resource fields. Current OpenObserve agent extraction can use resource `gen_ai.agent.name` / `gen_ai.agent.id` as a fallback for LLM spans and promote them into canonical agent fields.

Use this only when:

- The process has one static agent identity.
- The identity does not change per request.
- You are comfortable with resource identity being a fallback for LLM spans.

Do not use this as the only mechanism when one process handles multiple agents or request-scoped agent identity.

## Option 2: Span Processor Defaults

This is closer to `openobserve_init(agent_id=..., agent_name=...)`: set a process-wide default identity on every recording span as span attributes.

```python
from contextvars import ContextVar

from opentelemetry import baggage
from opentelemetry.sdk.trace import SpanProcessor

AGENT_ID_KEY = "gen_ai.agent.id"
AGENT_NAME_KEY = "gen_ai.agent.name"
_current_agent_identity = ContextVar("agent_identity", default=None)


def _clean(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


class AgentIdentitySpanProcessor(SpanProcessor):
    def __init__(self, agent_id=None, agent_name=None):
        self.agent_id = _clean(agent_id)
        self.agent_name = _clean(agent_name)

    def on_start(self, span, parent_context=None):
        if not span.is_recording():
            return

        local_identity = _current_agent_identity.get()
        if local_identity is not None:
            # Exact SDK behavior: a local partial identity does not mix with
            # static defaults or inherited baggage.
            agent_id, agent_name = local_identity
        elif self.agent_id is not None or self.agent_name is not None:
            agent_id = self.agent_id
            agent_name = self.agent_name
        else:
            agent_id = _clean(baggage.get_baggage(AGENT_ID_KEY, context=parent_context))
            agent_name = _clean(baggage.get_baggage(AGENT_NAME_KEY, context=parent_context))

        if agent_id is not None:
            span.set_attribute(AGENT_ID_KEY, agent_id)
        if agent_name is not None:
            span.set_attribute(AGENT_NAME_KEY, agent_name)

    def on_end(self, span):
        pass

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        return True
```

Register it before the exporter processor:

```python
provider = TracerProvider(resource=resource)
provider.add_span_processor(
    AgentIdentitySpanProcessor(
        agent_id="support-agent",
        agent_name="Support Agent",
    )
)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)
```

This makes every span self-identifying with normal span attributes. That is the safest form for OpenObserve agent attribution, especially for evaluations and non-LLM helper spans that should still carry agent identity.

## Option 3: Request-Scoped Identity With Baggage

This is the native equivalent of `openobserve_agent(...)`.

```python
from contextlib import contextmanager

from opentelemetry import baggage, context

AGENT_ID_KEY = "gen_ai.agent.id"
AGENT_NAME_KEY = "gen_ai.agent.name"


@contextmanager
def agent_identity(agent_id=None, agent_name=None):
    agent_id = _clean(agent_id)
    agent_name = _clean(agent_name)
    if agent_id is None and agent_name is None:
        raise ValueError("Agent identity requires at least one of agent_id or agent_name")

    local_token = _current_agent_identity.set((agent_id, agent_name))
    ctx = context.get_current()
    if agent_id is not None:
        ctx = baggage.set_baggage(AGENT_ID_KEY, agent_id, context=ctx)
    else:
        ctx = baggage.remove_baggage(AGENT_ID_KEY, context=ctx)

    if agent_name is not None:
        ctx = baggage.set_baggage(AGENT_NAME_KEY, agent_name, context=ctx)
    else:
        ctx = baggage.remove_baggage(AGENT_NAME_KEY, context=ctx)

    token = context.attach(ctx)
    try:
        yield
    finally:
        context.detach(token)
        _current_agent_identity.reset(local_token)
```

Use it around request or workflow execution:

```python
with agent_identity(agent_id="triage", agent_name="Triage Agent"):
    run_agent_workflow()
```

If outbound HTTP instrumentation is configured to propagate W3C baggage, downstream services can inherit the same identity. The downstream service can still override it with its own local or static identity.

The `ContextVar` is not used for propagation. It exists to mirror the SDK's precedence rules inside the current process: local request identity wins, static process identity is next, inherited baggage is last. This also prevents partial local identities from mixing with inherited or static fields.

## Explicit Baggage Propagation

If your application has custom propagation setup, make sure baggage is included:

```python
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator

set_global_textmap(
    CompositePropagator(
        [
            TraceContextTextMapPropagator(),
            W3CBaggagePropagator(),
        ]
    )
)
```

## Full Native Trace Setup

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

resource = Resource.create(
    {
        "service.name": "o2-ai",
        "service.version": "1.0.0",
        "deployment.environment": "production",
    }
)

exporter = OTLPSpanExporter(
    endpoint="http://localhost:5080/api/default/v1/traces",
    headers={
        "Authorization": "Basic <base64>",
        "stream-name": "default",
    },
    timeout=30,
)

provider = TracerProvider(resource=resource)
provider.add_span_processor(
    AgentIdentitySpanProcessor(agent_id="o2-ai", agent_name="O2 AI")
)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("o2-ai")

with agent_identity(agent_id="sre", agent_name="SRE Agent"):
    with tracer.start_as_current_span("agent.workflow") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        run_agent_workflow()
```

## HTTP And gRPC OpenObserve Endpoints

For HTTP/protobuf traces:

```python
OTLPSpanExporter(
    endpoint="https://<openobserve-host>/api/<org>/v1/traces",
    headers={
        "Authorization": "Basic <base64>",
        "stream-name": "default",
    },
)
```

For gRPC traces, use the gRPC exporter and pass OpenObserve headers as metadata:

```python
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

OTLPSpanExporter(
    endpoint="<openobserve-host>:5081",
    headers=(
        ("authorization", "Basic <base64>"),
        ("organization", "default"),
        ("stream-name", "default"),
    ),
    insecure=False,
)
```

Use lowercase header names for gRPC metadata.

## Choosing The Right Approach

| Requirement | Native OTel approach |
| --- | --- |
| One static agent per process | Resource attr can be enough |
| OpenObserve agent attribution on LLM spans | Resource fallback or span processor |
| Every span should be self-identifying | Span processor |
| One process handles multiple agents | Request-scoped baggage plus span processor |
| Identity should propagate to downstream services | Baggage propagation |
| Span identity should override inherited identity | Local request-scoped baggage/context |

## OpenObserve Behavior Notes

- Span attributes named `gen_ai.agent.name` and `gen_ai.agent.id` are the primary agent identity fields.
- Resource attributes are stored separately as resource/service metadata. OpenObserve prefixes non-`service.name` resource fields internally.
- Current OpenObserve extraction can use resource agent fields as a fallback for LLM spans.
- Span-level agent fields win over resource-level fields.
- If a process can emit spans for multiple agents, prefer span attributes over resource attributes.

## What Native OTel Does Not Give You Automatically

Using native OpenTelemetry means you own:

- OpenObserve endpoint construction.
- OpenObserve authorization and stream headers.
- Provider singleton lifecycle.
- Flush and shutdown behavior.
- Agent identity precedence rules.
- Baggage propagation setup.
- Logs and metrics exporter setup, if you need those signals.

Use the OpenObserve SDK when you want those defaults managed for you. Use native OpenTelemetry when your application already has a provider/exporter lifecycle and you only need to add OpenObserve-compatible conventions.
