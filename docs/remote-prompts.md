# Remote prompts

`RemotePromptStore` reads text prompts from OpenObserve's prompt registry. It can be used independently of the telemetry SDK and does not depend on an agent framework.

```python
import asyncio

from openobserve import PromptBinding, RemotePromptStore


async def main():
    store = RemotePromptStore(
        enabled=True,
        url="https://openobserve.example.com/api/default/prompts/resolve",
        auth_token="Basic <base64-credentials>",
        refresh_interval_seconds=60,
        bindings=(PromptBinding("assistant", "assistant-prompt", "production"),),
    )
    await store.initialize()
    try:
        prompt = store.get("assistant")
        if prompt is not None:
            print(prompt.body)
        await store.run_refresh_loop()
    finally:
        await store.close()


asyncio.run(main())
```

The resolve URL must end in `/prompts/resolve`. Every binding has a caller-defined key, prompt name, and label. The store sends those as `name` and `label` query parameters and requires an Authorization credential; bare credentials receive a `Bearer ` prefix, while `Basic ` and `Bearer ` values are preserved. Redirects are disabled.

`initialize()` validates configuration and resolves every binding before returning. Failure raises `RemotePromptError`; partial snapshots are not retained after failed initial startup. Successful responses must include an ETag and a matching text prompt identity, label, positive version, entity ID, content hash, and non-empty payload.

`refresh_once()` sends `If-None-Match` for existing snapshots. A 304 keeps the same immutable snapshot. A failed refresh records a safe status error and retains the last-known-good value. `status()` omits prompt text, ETags, and credentials. Inject an `httpx.AsyncClient` with `client=` to control transport and client lifecycle; injected clients remain caller-owned. Close the store to stop its refresh loop and close only clients it created.

Install with `pip install openobserve-python-sdk`; HTTPX is included as a runtime dependency.
