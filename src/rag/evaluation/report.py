"""Render an evaluation report as Markdown, ready for a CI job summary or an artifact."""

from __future__ import annotations

from rag.evaluation.harness import EvalReport, Thresholds, check_gate

_LABELS = {
    "recall_at_k": "Recall@{k}",
    "mrr": "MRR",
    "ndcg_at_k": "nDCG@{k}",
    "answer_rate": "Answer rate (answerable cases)",
    "citation_coverage": "Citation coverage",
    "groundedness": "Groundedness (lexical)",
    "term_recall": "Expected term recall",
    "refusal_accuracy": "Refusal accuracy",
    "access_violations": "Access violations",
    "quarantined_chunks": "Chunks quarantined for injected instructions",
}
_COUNTS = {"access_violations", "quarantined_chunks"}


def _cell(text: str, limit: int = 90) -> str:
    flat = " ".join(text.split()).replace("|", "\\|")
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


def render_markdown(report: EvalReport, thresholds: Thresholds | None = None) -> str:
    summary = report.summary
    values = summary.as_dict()
    failures = check_gate(summary, thresholds) if thresholds else []
    lines = [
        f"# Evaluation report ({report.label})",
        "",
        f"{summary.cases} cases, {summary.answerable} answerable, top k = {report.k}.",
        "",
    ]
    lines += [f"> {note}" for note in report.notes]
    if report.notes:
        lines.append("")
    lines += ["## Summary", "", "| Metric | Value | Gate | Status |", "| --- | --- | --- | --- |"]
    for key, label in _LABELS.items():
        value = values[key]
        shown = f"{int(value)}" if key in _COUNTS else f"{value:.3f}"
        gate, status = "", ""
        if thresholds:
            if key == "access_violations":
                gate = f"<= {thresholds.max_access_violations}"
                status = "pass" if value <= thresholds.max_access_violations else "FAIL"
            elif key in thresholds.minimums:
                gate = f">= {thresholds.minimums[key]:.2f}"
                status = "pass" if value >= thresholds.minimums[key] else "FAIL"
        lines.append(f"| {label.format(k=report.k)} | {shown} | {gate} | {status} |")

    lines += [
        "",
        "## By category",
        "",
        "| Category | Cases | Refused | Refusal correct |",
        "| --- | --- | --- | --- |",
    ]
    categories = sorted({r.case.category for r in report.results})
    for category in categories:
        rows = [r for r in report.results if r.case.category == category]
        refused = sum(r.refused for r in rows)
        correct = sum(r.refusal_correct for r in rows)
        lines.append(f"| {category} | {len(rows)} | {refused} | {correct}/{len(rows)} |")

    lines += [
        "",
        "## Cases",
        "",
        "| Id | Category | Recall | RR | Outcome | Answer |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in report.results:
        outcome = f"refused ({r.refusal_reason})" if r.refused else "answered"
        recall = f"{r.recall:.2f}" if r.case.answerable else "n/a"
        rr = f"{r.reciprocal_rank:.2f}" if r.case.answerable else "n/a"
        lines.append(
            f"| {r.case.id} | {r.case.category} | {recall} | {rr} | {outcome} | {_cell(r.answer)} |"
        )

    lines += ["", "## Gate", ""]
    if thresholds is None:
        lines.append("No thresholds given.")
    elif failures:
        lines += [f"- FAIL: {f}" for f in failures]
    else:
        lines.append("All thresholds met.")
    return "\n".join(lines) + "\n"
