from __future__ import annotations

from pathlib import Path

from rag.supported_formats import (
    SUPPORTED_FORMATS,
    is_optional_binary_extension,
    is_supported_extension,
    is_text_extension,
)


DOCUMENTS_DIR = Path("data") / "documents"
SUPPORTED_EXTENSIONS = SUPPORTED_FORMATS
SYSTEM_FILE_NAMES = {
    ".gitkeep",
    ".gitignore",
    "desktop.ini",
    "thumbs.db",
}


def get_documents_dir(project_root: Path) -> Path:
    return project_root / DOCUMENTS_DIR


def _is_supported_file(path: Path) -> bool:
    return (
        path.is_file()
        and not path.name.startswith(".")
        and path.name.lower() not in SYSTEM_FILE_NAMES
        and is_supported_extension(path.suffix)
    )


def _read_text_file(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode document: {path.name}")


def _read_pdf_file(path: Path) -> str:
    reader_cls = None

    try:
        from pypdf import PdfReader

        reader_cls = PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader

            reader_cls = PdfReader
        except ImportError as exc:
            raise ValueError(
                "PDF support requires pypdf or PyPDF2. Install dependency or use text formats."
            ) from exc

    reader = reader_cls(str(path))
    pages = []

    for page in reader.pages:
        pages.append(page.extract_text() or "")

    return "\n".join(pages).strip()


def _read_docx_file(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise ValueError(
            "DOCX support requires python-docx. Install dependency or use text formats."
        ) from exc

    document = Document(str(path))
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
    return "\n".join(paragraphs).strip()


def list_documents(project_root: Path) -> list[dict]:
    documents_dir = get_documents_dir(project_root)
    documents_dir.mkdir(parents=True, exist_ok=True)

    documents: list[dict] = []

    for path in sorted(documents_dir.iterdir()):
        if not _is_supported_file(path):
            continue

        documents.append({
            "name": path.name,
            "path": str(path.relative_to(project_root)),
            "extension": path.suffix.lower(),
            "size": path.stat().st_size,
        })

    return documents


def read_document(project_root: Path, filename: str) -> dict:
    documents_dir = get_documents_dir(project_root)
    documents_dir.mkdir(parents=True, exist_ok=True)

    if not filename or not filename.strip():
        raise ValueError("Document filename is required.")

    requested = Path(filename.strip())

    if requested.is_absolute() or ".." in requested.parts or requested.name != filename.strip():
        raise ValueError("Invalid document filename. Use a file name inside data\\documents.")

    extension = requested.suffix.lower()
    if not is_supported_extension(extension):
        raise ValueError(f"Unsupported document format: {extension or '(none)'}")

    document_path = (documents_dir / requested.name).resolve()
    documents_root = documents_dir.resolve()

    if document_path.parent != documents_root:
        raise ValueError("Invalid document filename. Use a file name inside data\\documents.")

    if not document_path.exists() or not document_path.is_file():
        raise FileNotFoundError(f"Document not found: {requested.name}")

    if is_text_extension(extension):
        content = _read_text_file(document_path)
    elif extension == ".pdf":
        content = _read_pdf_file(document_path)
    elif extension == ".docx":
        content = _read_docx_file(document_path)
    elif is_optional_binary_extension(extension):
        raise ValueError(f"Unsupported optional document format: {extension}")
    else:
        raise ValueError(f"Unsupported document format: {extension or '(none)'}")

    return {
        "name": document_path.name,
        "extension": document_path.suffix.lower(),
        "content": content,
        "size": document_path.stat().st_size,
    }
