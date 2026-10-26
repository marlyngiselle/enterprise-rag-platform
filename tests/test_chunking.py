from __future__ import annotations

import re

import pytest

from rag.ingestion.chunking import (
    FixedSizeChunker,
    HeadingChunker,
    chunk_id,
    fixed_windows,
    recursive_split,
    split_sections,
    word_count,
)
from tests.conftest import make_document


def _words(n: int, prefix: str = "w") -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def test_fixed_windows_overlap_and_cover_everything() -> None:
    windows = fixed_windows(_words(100), max_words=40, overlap_words=10)
    assert [word_count(w) for w in windows] == [40, 40, 40]
    assert windows[0].split()[-10:] == windows[1].split()[:10]
    assert windows[-1].split()[-1] == "w99"


def test_fixed_windows_empty_text() -> None:
    assert fixed_windows("   ", 20, 5) == []


@pytest.mark.parametrize(("max_words", "overlap"), [(5, 0), (20, 10), (20, -1)])
def test_invalid_sizes_are_rejected(max_words: int, overlap: int) -> None:
    with pytest.raises(ValueError, match="must"):
        FixedSizeChunker(max_words, overlap)


def test_recursive_split_prefers_paragraph_boundaries() -> None:
    text = f"{_words(30, 'a')}\n\n{_words(30, 'b')}\n\n{_words(30, 'c')}"
    pieces = recursive_split(text, max_words=65, overlap_words=0)
    assert len(pieces) == 2
    assert pieces[0].startswith("a0")
    assert pieces[0].rstrip().endswith("b29")
    assert pieces[1].startswith("c0")


def test_recursive_split_carries_overlap_and_respects_limit() -> None:
    sentences = ". ".join(_words(12, f"s{i}x") for i in range(12)) + "."
    pieces = recursive_split(sentences, max_words=40, overlap_words=8)
    assert all(word_count(p) <= 40 for p in pieces)
    assert pieces[0].split()[-8:] == pieces[1].split()[:8]


def test_recursive_split_falls_back_to_fixed_windows() -> None:
    pieces = recursive_split(_words(250), max_words=100, overlap_words=10)
    assert all(word_count(p) <= 100 for p in pieces)
    assert len(pieces) == 3


def test_sections_keep_heading_path_and_skip_fenced_code() -> None:
    md = "# Top\nintro\n## A\ntext a\n```\n# not a heading\n```\n### A1\ndeep\n## B\ntext b"
    sections = split_sections(md)
    assert [s.breadcrumb for s in sections] == ["Top", "Top > A", "Top > A > A1", "Top > B"]
    assert "# not a heading" in sections[1].text


def test_heading_chunker_uses_breadcrumb_as_section() -> None:
    doc = make_document("# Policy\n## Leave\nYou get 27 days.\n## Sick\nCall your manager.")
    chunks = HeadingChunker().split(doc)
    assert [c.section for c in chunks] == ["Policy > Leave", "Policy > Sick"]
    assert [c.position for c in chunks] == [0, 1]
    assert all(c.acl_groups == ("all-employees",) for c in chunks)


def test_heading_chunker_splits_long_sections() -> None:
    doc = make_document("## Long\n" + "\n\n".join(_words(60, f"p{i}x") for i in range(5)))
    chunks = HeadingChunker(max_words=100, overlap_words=20).split(doc)
    assert len(chunks) > 1
    assert all(word_count(c.text) <= 100 for c in chunks)


def test_fixed_chunker_section_is_title() -> None:
    chunks = FixedSizeChunker(max_words=20, overlap_words=5).split(make_document(_words(50)))
    assert {c.section for c in chunks} == {"Doc"}


def test_chunk_ids_are_deterministic_and_valid_search_keys() -> None:
    assert chunk_id("a.md", 1) == chunk_id("a.md", 1)
    assert chunk_id("a.md", 1) != chunk_id("a.md", 2)
    assert re.fullmatch(r"[a-f0-9]{32}", chunk_id("dir/a b.md", 0))
