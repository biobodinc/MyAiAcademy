"""Turn a file into plain text. Only formats we can honestly parse are accepted."""

from __future__ import annotations

from pathlib import Path

TEXT_SUFFIXES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".rst": "text/x-rst",
    ".csv": "text/csv",
    ".json": "application/json",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".toml": "application/toml",
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".ts": "text/typescript",
    ".tsx": "text/typescript",
    ".jsx": "text/javascript",
    ".rs": "text/x-rust",
    ".go": "text/x-go",
    ".java": "text/x-java",
    ".c": "text/x-c",
    ".h": "text/x-c",
    ".cpp": "text/x-c++",
    ".cs": "text/x-csharp",
    ".sh": "text/x-shellscript",
    ".html": "text/html",
    ".css": "text/css",
    ".sql": "application/sql",
}
PDF_SUFFIX = ".pdf"
MAX_FILE_BYTES = 64 * 1024 * 1024


class UnsupportedDocumentError(ValueError):
    pass


def supported_suffixes() -> list[str]:
    return sorted([*TEXT_SUFFIXES, PDF_SUFFIX])


def media_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == PDF_SUFFIX:
        return "application/pdf"
    if suffix in TEXT_SUFFIXES:
        return TEXT_SUFFIXES[suffix]
    raise UnsupportedDocumentError(
        f"Unsupported file type '{suffix or path.name}'. Supported: "
        + ", ".join(supported_suffixes())
    )


def extract_text(path: Path) -> str:
    media_type = media_type_for(path)
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise UnsupportedDocumentError("File is larger than 64 MB.")
    if media_type == "application/pdf":
        return _extract_pdf(path)
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnsupportedDocumentError("Could not decode the file as text.")


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise UnsupportedDocumentError("PDF support is not installed.") from exc
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        raise UnsupportedDocumentError("Encrypted PDFs are not supported.")
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(p.strip() for p in pages if p.strip())
    if not text.strip():
        raise UnsupportedDocumentError(
            "No extractable text (scanned PDF?). OCR is not part of this version."
        )
    return text
