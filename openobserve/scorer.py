"""Local scorers: functions the customer runs, whose results are self-reported.

A local scorer is not a platform Scorer and the two never merge. The platform
kind is a versioned server-side object; this kind is ordinary Python that runs
beside the task and reports what it decided. Keeping them distinct is what lets
a result page say honestly which judgements the platform made and which it was
told.
"""

import inspect
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ._eval.errors import ValidationError

# Parameters a local scorer may declare. They are injected by name, so a scorer
# asks for exactly what it needs and nothing else.
INJECTABLE_PARAMETERS = ("output", "expected_output", "input", "metadata", "context")


class LocalScorer:
    """A customer function bound to a score config.

    Declaring an ``expected_output`` parameter is what makes a scorer
    reference-based — referencing is declaring. There is no separate flag to
    keep in sync with the signature, and therefore no way for the two to
    disagree.
    """

    def __init__(
        self,
        function: Callable[..., Any],
        *,
        config: str,
        key: Optional[str] = None,
    ) -> None:
        config = (config or "").strip()
        if not config:
            raise ValidationError(
                f"local scorer {function.__name__!r} must bind a score config: @scorer(config=...)"
            )
        parameters = _declared_parameters(function)
        unknown = [name for name in parameters if name not in INJECTABLE_PARAMETERS]
        if unknown:
            raise ValidationError(
                f"local scorer {function.__name__!r} declares unknown parameter(s) "
                f"{', '.join(sorted(unknown))}; choose from {', '.join(INJECTABLE_PARAMETERS)}"
            )
        self.function = function
        self.config = config
        self.key = (key or function.__name__).strip()
        self.parameters = parameters
        self.__name__ = function.__name__
        self.__doc__ = function.__doc__

    @property
    def is_reference_based(self) -> bool:
        """Whether this dimension needs the dataset's expected output."""
        return "expected_output" in self.parameters

    def applies_to(self, has_reference: bool) -> bool:
        """Whether the dimension can judge a slot at all.

        A reference-based dimension facing a case with no expected output is
        not applicable — a distinct outcome from scoring it badly, and one the
        run reports as a count rather than hiding.
        """
        return has_reference or not self.is_reference_based

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.function(*args, **kwargs)

    def invoke(
        self,
        *,
        output: Any,
        expected_output: Any = None,
        input: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Any = None,
    ) -> Any:
        available = {
            "output": output,
            "expected_output": expected_output,
            "input": input,
            "metadata": metadata or {},
            "context": context,
        }
        return self.function(**{name: available[name] for name in self.parameters})


def scorer(
    _function: Optional[Callable[..., Any]] = None,
    *,
    config: str = "",
    key: Optional[str] = None,
) -> Any:
    """Bind a function to a score config so its results can be reported.

    Usage::

        @scorer(config="exact_match")
        def exact_match(output, expected_output):
            return 1.0 if output.strip() == expected_output.strip() else 0.0

    ``key`` overrides the stable identity reported to the platform, which
    defaults to the function name. Override it when two scorers share a score
    config and would otherwise be indistinguishable, or when renaming the
    function must not break continuity with earlier runs.
    """

    def decorate(function: Callable[..., Any]) -> LocalScorer:
        return LocalScorer(function, config=config, key=key)

    if _function is not None:
        return decorate(_function)
    return decorate


class PlatformScorerRef:
    """A reference to a server-side Scorer, optionally pinned to a version."""

    def __init__(self, name: str, version: Optional[int] = None) -> None:
        self.name = name
        self.version = version

    @classmethod
    def parse(cls, reference: str) -> "PlatformScorerRef":
        """Parse ``name`` or ``name@version``."""
        text = reference.strip()
        if not text:
            raise ValidationError("platform scorer reference cannot be empty")
        if "@" not in text:
            return cls(text)
        name, _, version = text.rpartition("@")
        if not name:
            raise ValidationError(f"scorer reference {reference!r} is missing a name")
        try:
            return cls(name, int(version))
        except ValueError as error:
            raise ValidationError(
                f"scorer reference {reference!r} has a non-numeric version"
            ) from error

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"PlatformScorerRef({self.name!r}, {self.version!r})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, PlatformScorerRef)
            and other.name == self.name
            and other.version == self.version
        )


def split_scorers(
    scorers: Sequence[Any],
) -> Tuple[List[PlatformScorerRef], List[LocalScorer]]:
    """Sort a mixed ``scorers=[...]`` list into its two kinds.

    Callers write one list because that is how they think about the run; the
    two halves travel to completely different places, so the split happens once
    here rather than at every use.
    """
    platform: List[PlatformScorerRef] = []
    local: List[LocalScorer] = []
    seen_keys = set()
    for entry in scorers or []:
        if isinstance(entry, LocalScorer):
            if entry.key in seen_keys:
                raise ValidationError(
                    f"two local scorers share the key {entry.key!r}; pass key= to tell them apart"
                )
            seen_keys.add(entry.key)
            local.append(entry)
        elif isinstance(entry, PlatformScorerRef):
            platform.append(entry)
        elif isinstance(entry, str):
            platform.append(PlatformScorerRef.parse(entry))
        elif callable(entry):
            raise ValidationError(
                f"{getattr(entry, '__name__', entry)!r} is a plain function; decorate it with "
                "@scorer(config=...) so its results bind to a score config"
            )
        else:
            raise ValidationError(
                f"{entry!r} is not a scorer: pass a platform reference string or a "
                "@scorer-decorated function"
            )
    return platform, local


def _declared_parameters(function: Callable[..., Any]) -> Tuple[str, ...]:
    signature = inspect.signature(function)
    names = []
    for name, parameter in signature.parameters.items():
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        names.append(name)
    return tuple(names)


__all__ = [
    "LocalScorer",
    "PlatformScorerRef",
    "scorer",
    "split_scorers",
]
