from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag.evaluation.cli import main as eval_main
from rag.evaluation.dataset import load_eval_set, parse_case
from rag.evaluation.harness import Thresholds, check_gate, run_evaluation
from rag.evaluation.report import render_markdown
from rag.factory import Components
from tests.conftest import EVAL_SET, KB, THRESHOLDS


def test_eval_set_is_valid_and_covers_every_category() -> None:
    cases = load_eval_set(EVAL_SET)
    assert len(cases) >= 30
    assert {c.category for c in cases} == {"factual", "access_denied", "out_of_scope", "injection"}


def test_factual_case_needs_relevant_sources() -> None:
    with pytest.raises(ValueError, match="relevant_sources"):
        parse_case({"id": "x", "question": "q", "category": "factual"})
    with pytest.raises(ValueError, match="category"):
        parse_case({"id": "x", "question": "q", "category": "trivia"})


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    line = json.dumps({"id": "a", "question": "q", "category": "out_of_scope"})
    path = tmp_path / "dup.jsonl"
    path.write_text(f"{line}\n{line}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_eval_set(path)


def test_offline_run_meets_the_gate(components: Components) -> None:
    report = run_evaluation(load_eval_set(EVAL_SET), components.retriever, components.service)
    summary = report.summary
    assert check_gate(summary, Thresholds.load(THRESHOLDS)) == []
    assert summary.access_violations == 0
    assert summary.quarantined_chunks >= 1


def test_gate_reports_each_failure(components: Components) -> None:
    report = run_evaluation(load_eval_set(EVAL_SET)[:3], components.retriever, components.service)
    failures = check_gate(report.summary, Thresholds({"recall_at_k": 1.1, "nonsense": 0.1}, -1))
    assert any("recall_at_k" in f for f in failures)
    assert any("unknown metric" in f for f in failures)
    assert any("access_violations" in f for f in failures)


def test_report_renders_tables(components: Components) -> None:
    report = run_evaluation(load_eval_set(EVAL_SET)[:4], components.retriever, components.service)
    markdown = render_markdown(report, Thresholds.load(THRESHOLDS))
    assert markdown.startswith("# Evaluation report (offline)")
    assert "| Recall@5 |" in markdown
    assert "## Gate" in markdown
    assert "No thresholds given." in render_markdown(report)


def test_cli_writes_report_and_fails_on_regression(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    code = eval_main(
        [
            "--kb",
            str(KB),
            "--eval-set",
            str(EVAL_SET),
            "--thresholds",
            str(THRESHOLDS),
            "--report",
            str(report),
        ]
    )
    assert code == 0
    assert "All thresholds met." in report.read_text(encoding="utf-8")

    strict = tmp_path / "strict.toml"
    strict.write_text("[gate]\nmrr = 1.01\n", encoding="utf-8")
    args = [
        "--kb",
        str(KB),
        "--eval-set",
        str(EVAL_SET),
        "--thresholds",
        str(strict),
        "--report",
        str(report),
    ]
    assert eval_main(args) == 1
    assert eval_main([*args, "--no-gate"]) == 0
