"""文档解析（FUNCTIONAL_SPEC 5.5 / 5.6）。

上传与灌数都从磁盘读回原始文件，先按扩展名分派，再把字节解成纯文本；
文本类依次尝试 `utf-8 → gbk → gb2312 → latin-1`。解析失败抛
`DocumentParseError`，由向量化任务把该文件置为 3「失败」并允许重试。
"""

from __future__ import annotations

from pathlib import Path

TEXT_SUFFIXES = (".txt", ".md", ".markdown")
PDF_SUFFIXES = (".pdf",)
WORD_SUFFIXES = (".doc", ".docx")
SUPPORTED_SUFFIXES = TEXT_SUFFIXES + PDF_SUFFIXES + WORD_SUFFIXES

TEXT_ENCODINGS = ("utf-8", "gbk", "gb2312", "latin-1")


class UnsupportedDocumentType(ValueError):
    """扩展名不在支持列表内（FUNCTIONAL_SPEC 5.6：直接拒绝，不入库）。"""


class DocumentParseError(RuntimeError):
    """扩展名受支持，但字节无法解析为文本。"""


def load_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return _load_text(path)
    if suffix in PDF_SUFFIXES:
        return _load_pdf(path)
    if suffix in WORD_SUFFIXES:
        return _load_word(path)
    raise UnsupportedDocumentType(f"不支持的文件类型：{suffix or path.name}")


def _load_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in TEXT_ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DocumentParseError(f"无法解码文本文件：{path.name}")


def _load_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as error:  # pragma: no cover - depends on the install
        raise DocumentParseError("缺少 PDF 解析依赖 pypdf") from error
    try:
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as error:  # noqa: BLE001 - any reader failure is a parse failure
        raise DocumentParseError(f"无法解析 PDF：{path.name}") from error


def _load_word(path: Path) -> str:
    if path.suffix.lower() == ".doc":
        # python-docx reads the OOXML `.docx` container, not the legacy binary
        # `.doc`. The file is still accepted for storage; it ends in state 3 and
        # can be re-vectorized once converted (see the ticket report).
        raise DocumentParseError("不支持旧版 .doc 二进制格式，请另存为 .docx")
    try:
        from docx import Document
    except ImportError as error:  # pragma: no cover - depends on the install
        raise DocumentParseError("缺少 Word 解析依赖 python-docx") from error
    try:
        document = Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception as error:  # noqa: BLE001 - any reader failure is a parse failure
        raise DocumentParseError(f"无法解析 Word 文档：{path.name}") from error
