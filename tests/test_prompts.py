"""Behavioral tests for the public remote-prompt store."""

import httpx
import pytest

from openobserve import PromptBinding, RemotePromptError, RemotePromptStore


def _body(name: str, version: int = 1) -> dict[str, object]:
    entity_id = f"entity-{name}"
    return {
        "prompt": {"entityId": entity_id, "name": name, "type": "text"},
        "version": {
            "entityId": entity_id,
            "version": version,
            "payload": f"Instruction v{version}",
            "contentHash": f"hash-{version}",
        },
        "label": "production",
    }


def _store(client: httpx.AsyncClient) -> RemotePromptStore:
    return RemotePromptStore(
        enabled=True,
        url="http://o2.test/api/acme/prompts/resolve",
        auth_token="token",
        refresh_interval_seconds=60,
        bindings=(PromptBinding("assistant", "assistant-prompt", "production"),),
        client=client,
    )


@pytest.mark.asyncio
async def test_resolves_prompt_and_keeps_snapshot_on_conditional_not_modified():
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json=_body("assistant-prompt"), headers={"ETag": '"v1"'})
        return httpx.Response(304)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        store = _store(client)
        await store.initialize()
        first = store.get("assistant")
        await store.refresh_once()

    assert first is not None and store.get("assistant") is first
    assert first.body == "Instruction v1"
    assert dict(requests[0].url.params) == {
        "name": "assistant-prompt",
        "label": "production",
    }
    assert requests[0].headers["authorization"] == "Bearer token"
    assert requests[1].headers["if-none-match"] == '"v1"'
    assert store.status()["ready"] is True


@pytest.mark.asyncio
async def test_failed_initial_resolution_surfaces_safe_error_without_caching():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(403))
    ) as client:
        store = _store(client)
        with pytest.raises(RemotePromptError, match="Initial remote prompt load failed"):
            await store.initialize()

    assert store.get("assistant") is None
    assert store.status()["ready"] is False
    assert "token" not in str(store.status())


@pytest.mark.asyncio
async def test_invalid_prompt_identity_is_rejected_before_snapshot_replacement():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=_body("wrong-name"), headers={"ETag": '"v1"'})
        )
    ) as client:
        store = _store(client)
        with pytest.raises(RemotePromptError, match="Initial remote prompt load failed"):
            await store.initialize()

    assert store.get("assistant") is None
