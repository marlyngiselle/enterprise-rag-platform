"""Evaluation set: one JSON object per line."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Category = Literal["factual", "access_denied", "out_of_scope", "injection"]
_CATEGORIES = {"factual", "access_denied", "out_of_scope", "injection"}


@dataclass(frozen=True)
class EvalCase:
    id: str
    question: str
    groups: tuple[str, ...]
    category: Category
    relevant_sources: tuple[str, ...] = ()
    expected_terms: tuple[str, ...] = ()

    @property
    def answerable(self) -> bool:
        return self.category == "factual"


def parse_case(raw: dict[str, object]) -> EvalCase:
    category = str(raw.get("category", "factual"))
    if category not in _CATEGORIES:
        msg = f"case {raw.get('id')}: unknown category {category!r}"
        raise ValueError(msg)

    def strings(key: str) -> tuple[str, ...]:
        value = raw.get(key, [])
        if not isinstance(value, list):
            msg = f"case {raw.get('id')}: {key} must be a list"
            raise ValueError(msg)
        return tuple(str(v) for v in value)

    case = EvalCase(
        id=str(raw["id"]),
        question=str(raw["question"]),
        groups=strings("groups"),
        category=category,  # type: ignore[arg-type]
        relevant_sources=strings("relevant_sources"),
        expected_terms=strings("expected_terms"),
    )
    if case.answerable and not case.relevant_sources:
        msg = f"case {case.id}: factual cases need relevant_sources"
        raise ValueError(msg)
    return case


def load_eval_set(path: Path) -> list[EvalCase]:
    cases = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip() and not line.lstrip().startswith("//"):
            try:
                cases.append(parse_case(json.loads(line)))
            except (KeyError, json.JSONDecodeError) as exc:
                msg = f"{path}:{number}: {exc}"
                raise ValueError(msg) from exc
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        msg = "duplicate case ids in evaluation set"
        raise ValueError(msg)
    return cases
