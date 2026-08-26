"""Local scorers, and how a mixed scorer list is sorted into its two kinds."""

import pytest

from openobserve._eval.errors import ValidationError
from openobserve.scorer import LocalScorer, PlatformScorerRef, scorer, split_scorers


@scorer(config="exact_match")
def exact_match(output, expected_output):
    return 1.0 if str(output).strip() == str(expected_output).strip() else 0.0


@scorer(config="tone")
def tone(output):
    return "warm" if "please" in str(output) else "flat"


def test_declaring_expected_output_is_what_makes_a_scorer_reference_based():
    # Referencing is declaring: there is no separate flag to drift out of sync
    # with the signature.
    assert exact_match.is_reference_based is True
    assert tone.is_reference_based is False


def test_a_reference_based_dimension_does_not_apply_to_a_case_without_a_reference():
    assert exact_match.applies_to(has_reference=True) is True
    assert exact_match.applies_to(has_reference=False) is False
    # A reference-free dimension judges every case.
    assert tone.applies_to(has_reference=False) is True


def test_a_scorer_must_bind_a_score_config():
    with pytest.raises(ValidationError, match="must bind a score config"):

        @scorer(config="")
        def unbound(output):
            return 1.0


def test_a_scorer_may_not_ask_for_parameters_the_sdk_cannot_inject():
    with pytest.raises(ValidationError, match="unknown parameter"):

        @scorer(config="exact_match")
        def confused(output, temperature):
            return 1.0


def test_parameters_are_injected_by_name_and_nothing_else_is_passed():
    calls = {}

    @scorer(config="exact_match")
    def picky(output, metadata):
        calls["output"] = output
        calls["metadata"] = metadata
        return 1.0

    picky.invoke(output="answer", expected_output="unused", input="q", metadata={"a": 1})
    assert calls == {"output": "answer", "metadata": {"a": 1}}


def test_a_mixed_list_splits_into_platform_references_and_local_functions():
    platform, local = split_scorers(["answer_correctness@2", exact_match, "toxicity"])

    assert platform == [
        PlatformScorerRef("answer_correctness", 2),
        PlatformScorerRef("toxicity", None),
    ]
    assert [s.key for s in local] == ["exact_match"]


def test_an_undecorated_function_is_rejected_with_the_fix_named():
    def plain(output):
        return 1.0

    with pytest.raises(ValidationError, match="decorate it with @scorer"):
        split_scorers([plain])


def test_two_local_scorers_may_not_share_a_key():
    other = LocalScorer(exact_match.function, config="exact_match")
    with pytest.raises(ValidationError, match="share the key"):
        split_scorers([exact_match, other])


def test_a_key_override_lets_two_scorers_share_one_score_config():
    strict = LocalScorer(exact_match.function, config="exact_match", key="strict")
    platform, local = split_scorers([exact_match, strict])

    assert platform == []
    assert sorted(s.key for s in local) == ["exact_match", "strict"]


def test_a_scorer_reference_version_must_be_numeric():
    with pytest.raises(ValidationError, match="non-numeric version"):
        PlatformScorerRef.parse("answer_correctness@latest")
