from __future__ import annotations

import pytest

from rag.ingestion.cli import main as ingest_main
from tests.conftest import KB


@pytest.mark.parametrize("chunker", ["heading", "fixed"])
def test_offline_ingestion_reports_counts(chunker: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert ingest_main(["--kb", str(KB), "--chunker", chunker]) == 0
    out = capsys.readouterr().out
    assert "10 documents" in out
    assert "1 skipped" in out
    assert "handbook/benefits.html" in out
