"""Conditional prompt resolution with immutable, last-known-good snapshots."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class PromptError(RuntimeError):
    """A prompt could not be loaded or validated."""


def normalize_auth_header(token: str) -> str:
    """Return a bare credential as a Bearer header, preserving Basic and Bearer values."""
    token = (token or "").strip()
    if token and token.split(" ", 1)[0].lower() not in {"basic", "bearer"}:
        return f"Bearer {token}"
    return token


@dataclass(frozen=True)
class PromptBinding:
    key: str
    name: str
    label: str


@dataclass(frozen=True)
class ResolvedPrompt:
    name: str
    version: int
    body: str
    label: Optional[str]  # noqa: UP045
    entity_id: str = ""
    content_hash: str = ""
    etag: str = ""


class PromptStore:
    """Resolve text prompts by caller-defined key, refreshing by ETag."""

    def __init__(
        self,
        *,
        enabled: bool,
        url: str,
        auth_token: Optional[str],  # noqa: UP045
        refresh_interval_seconds: float,
        bindings: tuple[PromptBinding, ...],
        client: Optional[httpx.AsyncClient] = None,  # noqa: UP045
    ) -> None:
        self._url = url.strip().rstrip("/")
        self._auth_token = (auth_token or "").strip()
        self._refresh_interval_seconds = refresh_interval_seconds
        self._bindings = {
            binding.key: binding
            for binding in bindings
            if binding.name.strip() and binding.label.strip()
        }
        self._managed_active = bool(enabled and self._url and self._bindings)
        self._client = client
        self._owns_client = client is None
        self._snapshots: dict[str, ResolvedPrompt] = {}
        self._last_success_at: dict[str, float] = {}
        self._last_errors: dict[str, str] = {}
        self._stop = asyncio.Event()

    @property
    def managed_keys(self) -> frozenset[str]:
        """Keys that use configured prompts instead of embedded prompts."""
        return frozenset(self._bindings) if self._managed_active else frozenset()

    def get(self, key: str) -> Optional[ResolvedPrompt]:  # noqa: UP045
        """Return the immutable prompt selected for a new operation."""
        return self._snapshots.get(key)

    async def initialize(self) -> None:
        """Load all configured prompts before the store becomes ready."""
        if not self._managed_active:
            return
        self._validate_configuration()
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=5.0, follow_redirects=False)
        try:
            await self.refresh_once(initial=True)
        except Exception:
            self._snapshots = {}
            await self.close()
            raise

    async def refresh_once(self, *, initial: bool = False) -> None:
        """Refresh each prompt without replacing a valid snapshot on failure."""
        if not self._managed_active:
            return
        errors: list[PromptError] = []
        for binding in self._bindings.values():
            try:
                await self._refresh_binding(binding)
            except PromptError as exc:
                self._last_errors[binding.key] = str(exc)
                if initial:
                    errors.append(exc)
                else:
                    logger.warning(
                        "Prompt refresh failed for key=%s name=%s; retaining the last-known-good version: %s",
                        binding.key,
                        binding.name,
                        exc,
                    )
        if errors:
            raise PromptError(
                f"Initial prompt load failed for {len(errors)} binding(s)"
            ) from errors[0]

    async def run_refresh_loop(self) -> None:
        """Check for changes at the configured interval until closed."""
        if not self._managed_active:
            return
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._refresh_interval_seconds)
            except asyncio.TimeoutError:
                await self.refresh_once()

    async def close(self) -> None:
        """Stop refreshes and close only HTTP clients owned by this store."""
        self._stop.set()
        if self._client is not None and self._owns_client:
            await self._client.aclose()
        self._client = None

    def status(self) -> dict[str, Any]:
        """Return metadata without exposing prompt content, ETags, or credentials."""
        bindings: dict[str, dict[str, Any]] = {}
        for key, binding in self._bindings.items():
            snapshot = self._snapshots.get(key)
            bindings[key] = {
                "name": binding.name,
                "label": binding.label,
                "version": snapshot.version if snapshot else None,
                "last_success_at": self._last_success_at.get(key),
                "error": self._last_errors.get(key),
            }
        return {
            "mode": "managed" if self._managed_active else "embedded",
            "ready": not self._managed_active or len(self._snapshots) == len(self._bindings),
            "degraded": bool(self._last_errors),
            "bindings": bindings,
        }

    def _validate_configuration(self) -> None:
        parsed = urlparse(self._url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise PromptError("Prompt resolve URL must be an HTTP(S) URL")
        if not parsed.path.endswith("/prompts/resolve") or parsed.query or parsed.fragment:
            raise PromptError(
                "Prompt resolve URL must end at /prompts/resolve without query or fragment"
            )
        if not self._auth_token:
            raise PromptError("Prompt read credential is required")
        if self._refresh_interval_seconds <= 0:
            raise PromptError("Prompt refresh interval must be positive")

    async def _refresh_binding(self, binding: PromptBinding) -> None:
        if self._client is None:
            raise PromptError("Prompt HTTP client is not initialized")
        current = self._snapshots.get(binding.key)
        headers = {"Authorization": normalize_auth_header(self._auth_token)}
        if current is not None:
            headers["If-None-Match"] = current.etag
        try:
            response = await self._client.get(
                self._url,
                params={"name": binding.name, "label": binding.label},
                headers=headers,
            )
        except httpx.RequestError as exc:
            raise PromptError("OpenObserve could not be reached") from exc

        if response.status_code == 304:
            if current is None:
                raise PromptError("OpenObserve returned 304 without a cached version")
            self._mark_success(binding.key)
            return
        if response.status_code in {401, 403}:
            raise PromptError("OpenObserve denied prompt read access")
        if response.status_code == 404:
            raise PromptError("Configured prompt or label was not found")
        if response.status_code != 200:
            raise PromptError(f"OpenObserve returned HTTP {response.status_code}")

        etag = response.headers.get("etag", "").strip()
        if not etag:
            raise PromptError("OpenObserve prompt response did not include an ETag")
        try:
            snapshot = _parse_resolved(response.json(), binding, etag)
        except ValueError as exc:
            raise PromptError("OpenObserve returned an invalid prompt response") from exc

        self._snapshots = {**self._snapshots, binding.key: snapshot}
        self._mark_success(binding.key)
        logger.info(
            "Loaded prompt key=%s name=%s version=%d label=%s",
            binding.key,
            snapshot.name,
            snapshot.version,
            snapshot.label,
        )

    def _mark_success(self, key: str) -> None:
        self._last_success_at[key] = time.time()
        self._last_errors.pop(key, None)


def _parse_resolved(data: object, binding: PromptBinding, etag: str) -> ResolvedPrompt:
    if not isinstance(data, dict):
        raise ValueError("response is not an object")
    prompt = data.get("prompt")
    version = data.get("version")
    if not isinstance(prompt, dict) or not isinstance(version, dict):
        raise ValueError("prompt or version is not an object")
    if prompt.get("name") != binding.name or prompt.get("type") != "text":
        raise ValueError("unexpected prompt identity or type")
    if data.get("label") != binding.label:
        raise ValueError("unexpected prompt label")

    number = version.get("version")
    body = version.get("payload")
    entity_id = prompt.get("entityId")
    content_hash = version.get("contentHash")
    if type(number) is not int or number < 1:
        raise ValueError("invalid prompt version")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("invalid text prompt payload")
    if not isinstance(entity_id, str) or not entity_id:
        raise ValueError("invalid prompt entity ID")
    if version.get("entityId") != entity_id:
        raise ValueError("version does not belong to prompt")
    if not isinstance(content_hash, str) or not content_hash:
        raise ValueError("invalid prompt content hash")
    return ResolvedPrompt(
        name=binding.name,
        version=number,
        body=body,
        label=binding.label,
        entity_id=entity_id,
        content_hash=content_hash,
        etag=etag,
    )
