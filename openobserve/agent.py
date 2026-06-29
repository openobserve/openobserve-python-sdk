"""
GenAI agent identity helpers for OpenObserve trace spans.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, Optional

from opentelemetry import baggage
from opentelemetry import context as otel_context
from opentelemetry.sdk.trace import Span, SpanProcessor

AGENT_ID_ATTRIBUTE = "gen_ai.agent.id"
AGENT_NAME_ATTRIBUTE = "gen_ai.agent.name"


def _normalize_value(value: object) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


@dataclass(frozen=True)
class AgentIdentity:
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "agent_id", _normalize_value(self.agent_id))
        object.__setattr__(self, "agent_name", _normalize_value(self.agent_name))

    def has_any(self) -> bool:
        return self.agent_id is not None or self.agent_name is not None


def normalize_agent_identity(
    agent_id: object, agent_name: object, *, required: bool = False
) -> Optional[AgentIdentity]:
    identity = AgentIdentity(agent_id=_normalize_value(agent_id), agent_name=_normalize_value(agent_name))
    if identity.has_any():
        return identity
    if required:
        raise ValueError("Agent identity requires at least one of agent_id or agent_name")
    return None


_current_agent_identity: ContextVar[Optional[AgentIdentity]] = ContextVar(
    "openobserve_agent_identity", default=None
)


def _resolve_agent_identity(static_identity: Optional[AgentIdentity] = None) -> Optional[AgentIdentity]:
    local_identity = _current_agent_identity.get()
    if local_identity is not None and local_identity.has_any():
        return local_identity

    if static_identity is not None and static_identity.has_any():
        return static_identity

    return normalize_agent_identity(
        baggage.get_baggage(AGENT_ID_ATTRIBUTE),
        baggage.get_baggage(AGENT_NAME_ATTRIBUTE),
    )


@contextmanager
def openobserve_agent(
    agent_id: Optional[str] = None, agent_name: Optional[str] = None
) -> Iterator[None]:
    """Set the active GenAI agent identity for spans in this context."""
    identity = normalize_agent_identity(agent_id, agent_name, required=True)
    assert identity is not None
    local_token = _current_agent_identity.set(identity)

    baggage_context = otel_context.get_current()
    if identity.agent_id is not None:
        baggage_context = baggage.set_baggage(
            AGENT_ID_ATTRIBUTE, identity.agent_id, context=baggage_context
        )
    else:
        baggage_context = baggage.remove_baggage(AGENT_ID_ATTRIBUTE, context=baggage_context)

    if identity.agent_name is not None:
        baggage_context = baggage.set_baggage(
            AGENT_NAME_ATTRIBUTE, identity.agent_name, context=baggage_context
        )
    else:
        baggage_context = baggage.remove_baggage(AGENT_NAME_ATTRIBUTE, context=baggage_context)

    baggage_token = otel_context.attach(baggage_context)
    try:
        yield
    finally:
        otel_context.detach(baggage_token)
        _current_agent_identity.reset(local_token)


class AgentIdentitySpanProcessor(SpanProcessor):
    """Stamp resolved GenAI agent identity on every recording span."""

    def __init__(self, static_identity: Optional[AgentIdentity] = None):
        self._static_identity = static_identity

    def on_start(self, span: Span, parent_context=None) -> None:
        if not span.is_recording():
            return

        identity = _resolve_agent_identity(self._static_identity)
        if identity is None:
            return

        if identity.agent_id is not None:
            span.set_attribute(AGENT_ID_ATTRIBUTE, identity.agent_id)
        if identity.agent_name is not None:
            span.set_attribute(AGENT_NAME_ATTRIBUTE, identity.agent_name)

    def on_end(self, span) -> None:
        return None

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True
