"""Identity of the customer code under evaluation.

The fingerprint is what makes a resume safe. An experiment stores it, every
reported record repeats it, and the server refuses a mismatch — so continuing a
run after the code changed is impossible rather than merely discouraged. That
matters because a cohort half-answered by one version and half by another
supports no conclusion at all.
"""

import hashlib
import inspect
from typing import Any, Callable, Optional, Sequence


def task_fingerprint(
    task_fn: Callable[..., Any],
    *,
    scorer_keys: Sequence[str] = (),
    extra: Optional[str] = None,
) -> str:
    """Derive a stable fingerprint from the task's source.

    Source text is used rather than a module version because it changes exactly
    when the behaviour under evaluation changes, with nothing for a developer
    to remember to bump. When source is unavailable — a C extension, an
    interactive session — the qualified name is the honest fallback, and
    ``extra`` lets a caller pin something sharper.
    """
    digest = hashlib.sha256()
    digest.update(_source_of(task_fn).encode("utf-8"))
    for key in sorted(scorer_keys):
        digest.update(b"\x00")
        digest.update(key.encode("utf-8"))
    if extra:
        digest.update(b"\x00")
        digest.update(extra.encode("utf-8"))
    return f"sha256:{digest.hexdigest()}"


def _source_of(task_fn: Callable[..., Any]) -> str:
    try:
        return inspect.getsource(task_fn)
    except (OSError, TypeError):
        module = getattr(task_fn, "__module__", "")
        qualname = getattr(task_fn, "__qualname__", getattr(task_fn, "__name__", "task"))
        return f"{module}.{qualname}"
