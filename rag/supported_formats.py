from __future__ import annotations


SUPPORTED_TEXT_FORMATS = {".txt", ".md", ".py", ".json", ".csv"}
OPTIONAL_BINARY_FORMATS = {".pdf", ".docx"}
SUPPORTED_FORMATS = SUPPORTED_TEXT_FORMATS | OPTIONAL_BINARY_FORMATS


def _normalize_extension(extension: str) -> str:
    extension = extension.strip().lower()
    if extension and not extension.startswith("."):
        extension = "." + extension
    return extension


def is_supported_extension(extension: str) -> bool:
    return _normalize_extension(extension) in SUPPORTED_FORMATS


def is_text_extension(extension: str) -> bool:
    return _normalize_extension(extension) in SUPPORTED_TEXT_FORMATS


def is_optional_binary_extension(extension: str) -> bool:
    return _normalize_extension(extension) in OPTIONAL_BINARY_FORMATS
