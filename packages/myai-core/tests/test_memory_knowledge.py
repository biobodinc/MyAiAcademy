from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from myai_core.knowledge.chunking import chunk_text
from myai_core.knowledge.extract import UnsupportedDocumentError, extract_text, media_type_for
from myai_core.knowledge.service import (
    DocumentAddPath,
    DocumentAddText,
    KnowledgeError,
    KnowledgeService,
)
from myai_core.memory.service import (
    MemoryCategory,
    MemoryCreate,
    MemoryService,
    MemoryStoreError,
    MemoryUpdate,
)
from myai_core.profile.schemas import ProfileCreate
from myai_core.profile.service import ProfileService


@pytest.fixture
def ai_id(session: Session) -> str:
    return ProfileService(session).create(ProfileCreate(name="Nova")).ai_id


# --- memory -------------------------------------------------------------------------------


def test_memory_crud_and_search(session: Session, ai_id: str) -> None:
    svc = MemoryService(session, ai_id)
    a = svc.add(
        MemoryCreate(content="  Alex   prefers dark   mode ", category=MemoryCategory.PREFERENCE)
    )
    assert a.content == "Alex prefers dark mode" and a.uid.startswith("mem_")
    svc.add(MemoryCreate(content="The horse project is a cinematic adventure film"))
    assert len(svc.list_all()) == 2

    hits = svc.search("horses")  # porter stemming: horses -> horse
    assert [h.content for h in hits] == ["The horse project is a cinematic adventure film"]
    assert svc.search("dark mo") and svc.search("nothing-here") == []
    assert svc.search('"; DROP TABLE memories; --') == []

    updated = svc.update(a.id, MemoryUpdate(content="Alex prefers light mode", expected_version=1))
    assert updated.version == 2
    assert svc.search("light")[0].id == a.id and svc.search("dark") == []
    with pytest.raises(MemoryStoreError):
        svc.update(a.id, MemoryUpdate(content="x", expected_version=1))

    svc.delete(a.id)
    assert svc.search("light") == []
    assert svc.clear() == 1 and svc.list_all() == []


def test_memory_is_scoped_per_ai(session: Session, ai_id: str) -> None:
    other = MemoryService(session, "myai_other")
    MemoryService(session, ai_id).add(MemoryCreate(content="private fact"))
    assert other.search("private") == [] and other.list_all() == []
    with pytest.raises(MemoryStoreError):
        other.get(MemoryService(session, ai_id).list_all()[0].id)


# --- knowledge ----------------------------------------------------------------------------


def test_chunking_respects_paragraphs_and_overlap() -> None:
    paras = [f"Paragraph {i}. " + ("word " * 120).strip() for i in range(6)]
    chunks = chunk_text("\n\n".join(paras))
    assert 2 <= len(chunks) <= 6
    assert all(len(c) <= 1300 for c in chunks)
    assert chunks[0].startswith("Paragraph 0.")
    assert chunk_text("   \n\n  ") == []
    long_sentence = "x" * 5000
    assert all(len(c) <= 1200 for c in chunk_text(long_sentence))


def test_extract_supported_and_unsupported(tmp_path: Path) -> None:
    md = tmp_path / "notes.md"
    md.write_text("# Title\n\nSome notes about horses.", encoding="utf-8")
    assert media_type_for(md) == "text/markdown"
    assert "horses" in extract_text(md)
    with pytest.raises(UnsupportedDocumentError):
        media_type_for(tmp_path / "photo.png")


def test_extract_pdf(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    pdf = tmp_path / "doc.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with pdf.open("wb") as fh:
        writer.write(fh)
    with pytest.raises(UnsupportedDocumentError, match="No extractable text"):
        extract_text(pdf)


def test_knowledge_ingest_search_delete(session: Session, ai_id: str, tmp_path: Path) -> None:
    svc = KnowledgeService(session, ai_id)
    doc_file = tmp_path / "horses.txt"
    doc_file.write_text(
        "Horses are herbivores.\n\nThe cinematic horse adventure needs dramatic lighting "
        "and a moody soundtrack.\n\nBudget notes: nothing relevant here.",
        encoding="utf-8",
    )
    doc = svc.add_path(DocumentAddPath(path=str(doc_file)))
    assert doc.title == "horses.txt" and doc.chunk_count >= 1 and doc.status == "ready"
    with pytest.raises(KnowledgeError, match="Already"):
        svc.add_path(DocumentAddPath(path=str(doc_file)))

    svc.add_text(DocumentAddText(title="Recipe", text="Pancakes need flour, milk and eggs."))
    hits = svc.search("what lighting does the horse film need?")
    assert hits and hits[0].document_title == "horses.txt"
    assert "lighting" in hits[0].content
    assert svc.search("pancake flour")[0].document_title == "Recipe"
    assert svc.search("zzzz") == []
    assert svc.stats() == (2, sum(d.chunk_count for d in svc.list_all()))

    svc.delete(doc.id)
    assert svc.search("lighting") == []
    with pytest.raises(KnowledgeError):
        svc.add_path(DocumentAddPath(path=str(tmp_path / "missing.txt")))
    (tmp_path / "x.png").write_bytes(b"\x89PNG")
    with pytest.raises(KnowledgeError, match="Unsupported"):
        svc.add_path(DocumentAddPath(path=str(tmp_path / "x.png")))
