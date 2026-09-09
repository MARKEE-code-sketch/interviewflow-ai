"""Validate and freeze human-approved role rubrics without an LLM call."""

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass


def require_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")


def require_id(value: object) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("IDs must contain only letters, digits, underscores or hyphens")


def _require_fields(value: object, fields: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("Rubric fields do not match the required schema")


@dataclass(frozen=True, slots=True)
class RubricCriterion:
    criterion_id: str
    name: str
    definition: str
    weight: float
    anchors: tuple[str, ...]  # Positions 0 through 4 correspond to scores 1 through 5.

    def __post_init__(self) -> None:
        require_id(self.criterion_id)
        require_text(self.name, "Criterion name")
        require_text(self.definition, "Criterion definition")
        if (
            type(self.weight) not in (int, float)
            or not math.isfinite(self.weight)
            or self.weight <= 0
        ):
            raise ValueError("Criterion weight must be a finite positive number")
        object.__setattr__(self, "weight", float(self.weight))
        if not isinstance(self.anchors, tuple) or len(self.anchors) != 5:
            raise ValueError("Exactly five immutable score anchors are required")
        for anchor in self.anchors:
            require_text(anchor, "Score anchor")


@dataclass(frozen=True, slots=True)
class ApprovedRubric:
    """Caller must supply human approval; this is not an authentication mechanism."""

    rubric_id: str
    role_title: str
    version: int
    criteria: tuple[RubricCriterion, ...]
    human_approved: bool = False

    def __post_init__(self) -> None:
        if self.human_approved is not True:
            raise ValueError("Explicit human rubric approval is required")
        require_id(self.rubric_id)
        require_text(self.role_title, "Role title")
        if type(self.version) is not int or self.version < 1:
            raise ValueError("Rubric version must be a positive integer")
        if not isinstance(self.criteria, tuple) or not self.criteria:
            raise ValueError("An immutable non-empty criteria tuple is required")
        if any(not isinstance(item, RubricCriterion) for item in self.criteria):
            raise ValueError("Every criterion must be a validated RubricCriterion")
        ids = [item.criterion_id for item in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("Criterion IDs must be unique")
        if not math.isfinite(sum(item.weight for item in self.criteria)):
            raise ValueError("Total rubric weight must be finite")

    def to_dict(self) -> dict:
        criteria = []
        for item in self.criteria:
            criterion = asdict(item)
            criterion["anchors"] = {
                str(score): anchor for score, anchor in enumerate(item.anchors, start=1)
            }
            criteria.append(criterion)
        return dict(
            rubric_id=self.rubric_id, role_title=self.role_title,
            version=self.version, criteria=criteria,
        )

    @property
    def content_hash(self) -> str:
        canonical = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_approved_rubric(data: dict, *, human_approved: bool = False) -> ApprovedRubric:
    """Copy the documented JSON schema into validated immutable Python values."""
    _require_fields(data, {"rubric_id", "role_title", "version", "criteria"})
    if not isinstance(data["criteria"], list):
        raise ValueError("Rubric criteria must be a list")
    criteria = []
    for item in data["criteria"]:
        _require_fields(item, {"criterion_id", "name", "definition", "weight", "anchors"})
        _require_fields(item["anchors"], {"1", "2", "3", "4", "5"})
        criteria.append(RubricCriterion(
            criterion_id=item["criterion_id"], name=item["name"],
            definition=item["definition"], weight=item["weight"],
            anchors=tuple(item["anchors"][str(score)] for score in range(1, 6)),
        ))
    return ApprovedRubric(
        rubric_id=data["rubric_id"], role_title=data["role_title"],
        version=data["version"], criteria=tuple(criteria), human_approved=human_approved,
    )
