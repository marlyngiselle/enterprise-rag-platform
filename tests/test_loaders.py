from __future__ import annotations

from pathlib import Path

import pytest

from rag.ingestion.loaders import (
    load_directory,
    load_html,
    load_markdown,
    load_path,
    load_pdf,
    parse_front_matter,
    parse_groups,
)
from tests.conftest import KB


def test_parse_groups_handles_lists_and_quotes() -> None:
    assert parse_groups("[b, 'a', a]") == ("a", "b")
    assert parse_groups("") == ()


def test_front_matter_is_split_from_body() -> None:
    meta, body = parse_front_matter("---\ntitle: T\nacl_groups: [x]\n---\n# H\ntext")
    assert meta == {"title": "T", "acl_groups": "[x]"}
    assert body.startswith("# H")


def test_markdown_without_front_matter_has_no_groups(tmp_path: Path) -> None:
    path = tmp_path / "plain.md"
    path.write_text("# Plain title\n\nBody.", encoding="utf-8")
    doc = load_markdown(path, "plain.md")
    assert doc.title == "Plain title"
    assert doc.acl_groups == ()


def test_markdown_metadata_is_kept() -> None:
    doc = load_path(KB / "hr" / "compensation-review-2026.md", KB)
    assert doc.source == "hr/compensation-review-2026.md"
    assert doc.acl_groups == ("hr-compensation",)
    assert doc.metadata["classification"] == "Restricted"


def test_html_drops_hidden_text_scripts_and_reads_acl() -> None:
    doc = load_html(KB / "handbook" / "benefits.html", "handbook/benefits.html")
    assert doc.title == "Employee Benefits"
    assert doc.acl_groups == ("all-employees",)
    assert "## Pension" in doc.text
    assert "- A gym or sports allowance" in doc.text
    assert "Ignore all previous instructions" not in doc.text
    assert "document.title" not in doc.text


def test_html_hidden_attribute_and_nested_elements(tmp_path: Path) -> None:
    path = tmp_path / "page.html"
    path.write_text(
        "<html><body><h2>Visible</h2><div hidden><p>secret <b>bold</b></p></div>"
        "<p>shown<br>line</p><!-- comment --></body></html>",
        encoding="utf-8",
    )
    doc = load_html(path, "page.html")
    assert "secret" not in doc.text
    assert "comment" not in doc.text
    assert "## Visible" in doc.text
    assert "shown\nline" in doc.text


def _minimal_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


def test_pdf_text_and_sidecar_metadata(tmp_path: Path) -> None:
    path = tmp_path / "policy.pdf"
    path.write_bytes(_minimal_pdf("Badges must be worn on site."))
    (tmp_path / "policy.pdf.meta.json").write_text(
        '{"title": "Badge Policy", "acl_groups": ["all-employees"]}', encoding="utf-8"
    )
    doc = load_pdf(path, "policy.pdf")
    assert doc.title == "Badge Policy"
    assert doc.acl_groups == ("all-employees",)
    assert "## Page 1" in doc.text
    assert "Badges must be worn" in doc.text


def test_pdf_without_sidecar_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "orphan.pdf"
    path.write_bytes(_minimal_pdf("No owner."))
    assert load_pdf(path, "orphan.pdf").acl_groups == ()


def test_unsupported_type_raises(tmp_path: Path) -> None:
    path = tmp_path / "notes.docx"
    path.write_bytes(b"")
    with pytest.raises(ValueError, match="unsupported"):
        load_path(path)


def test_load_directory_is_sorted_and_complete() -> None:
    docs = load_directory(KB)
    sources = [d.source for d in docs]
    assert sources == sorted(sources)
    assert len(docs) == 11
    assert "drafts/hybrid-policy-draft.md" in sources
