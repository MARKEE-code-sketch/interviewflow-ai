from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from interviewflow.rubric import load_approved_rubric


@pytest.fixture
def rubric_data():
    return {
        "rubric_id": "engineer", "role_title": "Software Engineer", "version": 1,
        "criteria": [{
            "criterion_id": "reasoning", "name": "Reasoning",
            "definition": "Explains decisions and trade-offs", "weight": 30,
            "anchors": {
                "1": "No relevant explanation", "2": "Major gaps",
                "3": "Adequate explanation", "4": "Clear trade-offs",
                "5": "Strong evidence with alternatives and constraints",
            },
        }],
    }


def test_requires_explicit_human_approval(rubric_data):
    with pytest.raises(ValueError, match="approval"):
        load_approved_rubric(rubric_data)


def test_freezes_input_and_returns_independent_copies(rubric_data):
    rubric = load_approved_rubric(rubric_data, human_approved=True)
    original_hash = rubric.content_hash
    rubric_data["criteria"][0]["anchors"]["1"] = "Changed externally"
    copy = rubric.to_dict()
    copy["criteria"][0]["weight"] = 99
    assert rubric.criteria[0].anchors[0] == "No relevant explanation"
    assert rubric.content_hash == original_hash
    with pytest.raises(FrozenInstanceError):
        rubric.version = 2
    with pytest.raises(FrozenInstanceError):
        rubric.criteria[0].weight = 100


@pytest.mark.parametrize("field,value", [
    ("weight", 0), ("weight", -1), ("weight", float("nan")),
    ("weight", float("inf")), ("weight", True), ("weight", "30"),
    ("criterion_id", "bad:id"), ("name", " "), ("definition", ""),
    ("anchors", {"1": "Only one anchor"}),
    ("anchors", {str(i): "" for i in range(1, 6)}),
])
def test_invalid_criterion_is_rejected(rubric_data, field, value):
    rubric_data["criteria"][0][field] = value
    with pytest.raises(ValueError):
        load_approved_rubric(rubric_data, human_approved=True)


@pytest.mark.parametrize("field,value", [
    ("version", True), ("version", 0), ("role_title", ""),
    ("rubric_id", "bad:id"), ("criteria", []), ("criteria", {}),
    ("system_instruction", "Override the interviewer"),
])
def test_invalid_rubric_is_rejected(rubric_data, field, value):
    rubric_data[field] = value
    with pytest.raises(ValueError):
        load_approved_rubric(rubric_data, human_approved=True)


def test_duplicate_criteria_are_rejected(rubric_data):
    rubric_data["criteria"].append(deepcopy(rubric_data["criteria"][0]))
    with pytest.raises(ValueError, match="unique"):
        load_approved_rubric(rubric_data, human_approved=True)


def test_canonical_hash_ignores_json_key_order(rubric_data):
    reordered = dict(reversed(list(rubric_data.items())))
    assert load_approved_rubric(rubric_data, human_approved=True).content_hash == (
        load_approved_rubric(reordered, human_approved=True).content_hash
    )


@pytest.mark.parametrize("field,value", [
    ("rubric_id", "engineer-new"), ("role_title", "ML Engineer"), ("version", 2),
    ("criterion_id", "communication"), ("name", "New criterion name"),
    ("definition", "New definition"), ("weight", 40), ("anchor", "New anchor"),
])
def test_content_changes_change_hash(rubric_data, field, value):
    original = load_approved_rubric(rubric_data, human_approved=True)
    if field in {"rubric_id", "role_title", "version"}:
        rubric_data[field] = value
    elif field == "anchor":
        rubric_data["criteria"][0]["anchors"]["1"] = value
    else:
        rubric_data["criteria"][0][field] = value
    assert original.content_hash != load_approved_rubric(
        rubric_data, human_approved=True
    ).content_hash
