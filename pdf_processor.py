"""
PDF Processor — text extraction (with OCR fallback) and semantic chunking.
Also provides file-discovery utilities for all supported document formats.
"""

import io
import logging
import os
import platform
import re
import shutil
from typing import Any, Dict, List, Optional

import fitz  # pymupdf
import numpy as np
from PIL import Image

from config import get_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (were magic numbers scattered across methods)
# ---------------------------------------------------------------------------

OCR_FAILED_MARKER = "[OCR_FAILED_PAGE]"

SUPPORTED_EXTENSIONS = frozenset({
    ".pdf", ".docx", ".pptx", ".txt", ".md", ".epub",
})

# OCR tuning
_OCR_DPI = 200
_BLANK_PAGE_STD_THRESHOLD = 5.0
_MIN_OCR_WORDS = 5
_MIN_TEXT_CHARS_FOR_DIGITAL = 200  # below this → fall back to OCR

# Chunking tuning
_MIN_CHUNK_CHARS = 100
_MIN_CHUNK_WORDS = 15
_MIN_PARAGRAPH_CHARS = 40
_MAX_HEADING_CHARS = 120


# ---------------------------------------------------------------------------
# Tesseract configuration (was a hardcoded Windows path)
# ---------------------------------------------------------------------------

def _configure_tesseract() -> None:
    """
    Locate the Tesseract binary.

    Priority:
      1. ``TESSERACT_CMD`` environment variable
      2. Already on ``PATH``
      3. Platform-specific default location
    """
    import pytesseract

    # 1. Env var
    env_path = os.environ.get("TESSERACT_CMD")
    if env_path and os.path.isfile(env_path):
        pytesseract.pytesseract.tesseract_cmd = env_path
        return

    # 2. PATH
    found = shutil.which("tesseract")
    if found:
        pytesseract.pytesseract.tesseract_cmd = found
        return

    # 3. Platform default
    if platform.system() == "Windows":
        win_default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.isfile(win_default):
            pytesseract.pytesseract.tesseract_cmd = win_default
            return

    logger.warning(
        "Tesseract not found — OCR will fail.  "
        "Install Tesseract or set the TESSERACT_CMD environment variable."
    )


_configure_tesseract()


# ---------------------------------------------------------------------------
# PDFProcessor
# ---------------------------------------------------------------------------

class PDFProcessor:
    """Extract text from PDFs (with OCR fallback) and chunk semantically."""

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> None:
        import torch

        config = get_config()
        self.chunk_size: int = chunk_size or config.chunk_size
        self.chunk_overlap: int = chunk_overlap or config.chunk_overlap
        self.use_gpu: bool = torch.cuda.is_available()
        self._ocr_reader: Any = None  # lazy-loaded EasyOCR

        logger.info(
            "PDFProcessor: chunk_size=%d, overlap=%d, GPU=%s",
            self.chunk_size,
            self.chunk_overlap,
            self.use_gpu,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_text_from_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract text page-by-page.

        Falls back to OCR when no page exceeds ``_MIN_TEXT_CHARS_FOR_DIGITAL``
        characters of digital text.
        """
        pages = self._extract_pymupdf(file_path)

        has_digital_text = any(
            len(p["text"]) > _MIN_TEXT_CHARS_FOR_DIGITAL for p in pages
        )

        if not has_digital_text:
            try:
                pages = self._extract_ocr(file_path)
            except Exception:
                logger.warning(
                    "OCR failed for %s — using sparse digital text", file_path
                )
        return pages

    def process_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract → chunk → return list of chunk dicts."""
        pages = self.extract_text_from_pdf(file_path)
        all_chunks: List[Dict[str, Any]] = []

        for page in pages:
            if page["text"] == OCR_FAILED_MARKER:
                continue

            chunks = self.semantic_chunking(page["text"])
            for idx, chunk_text in enumerate(chunks, start=1):
                if (
                    len(chunk_text) < _MIN_CHUNK_CHARS
                    or len(chunk_text.split()) < _MIN_CHUNK_WORDS
                ):
                    continue
                all_chunks.append({
                    "text": chunk_text,
                    "file_name": page["file_name"],
                    "file_path": page["file_path"],
                    "page_number": page["page_number"],
                    "chunk_number": idx,
                    "total_chunks": len(chunks),
                    "total_pages": page["total_pages"],
                })

        logger.info(
            "Created %d chunks for %s", len(all_chunks), os.path.basename(file_path)
        )
        return all_chunks

    # ------------------------------------------------------------------
    # Extraction backends
    # ------------------------------------------------------------------

    def _extract_pymupdf(self, file_path: str) -> List[Dict[str, Any]]:
        """Digital text extraction via pymupdf."""
        pages: List[Dict[str, Any]] = []
        with fitz.open(file_path) as doc:
            total = len(doc)
            for i, page in enumerate(doc, start=1):
                text = self.clean_text(page.get_text("text") or "")
                if text:
                    pages.append(self._make_page(text, i, file_path, total))
        return pages

    def _extract_ocr(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Per-page OCR pipeline:
          1. Tesseract (fast, CPU)
          2. EasyOCR fallback (GPU) when Tesseract yields < _MIN_OCR_WORDS
        """
        pages: List[Dict[str, Any]] = []

        with fitz.open(file_path) as doc:
            total = len(doc)
            for i, page in enumerate(doc, start=1):
                pix = page.get_pixmap(dpi=_OCR_DPI)
                pil_img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")

                if self._is_blank_page(pil_img):
                    continue

                # Step 1 — fast Tesseract
                cleaned = self._tesseract_ocr(pil_img)

                # Accept if Tesseract produced enough text
                if len(cleaned.split()) > _MIN_OCR_WORDS:
                    pages.append(self._make_page(cleaned, i, file_path, total))
                    continue

                # Step 2 — EasyOCR fallback (GPU only)
                if self.use_gpu:
                    gpu_text = self._easyocr_fallback(pil_img, page_number=i)
                    if gpu_text:
                        cleaned = gpu_text

                pages.append(
                    self._make_page(cleaned or OCR_FAILED_MARKER, i, file_path, total)
                )

        return pages

    def _tesseract_ocr(self, image: Image.Image) -> str:
        """Run Tesseract; return cleaned text or empty string on failure."""
        import pytesseract

        try:
            raw = pytesseract.image_to_string(image, config="--oem 3 --psm 6")
            return self.clean_text(raw)
        except Exception:
            logger.debug("Tesseract failed", exc_info=True)
            return ""

    def _easyocr_fallback(self, image: Image.Image, page_number: int) -> str:
        """Run EasyOCR (GPU); return cleaned text or empty string on failure."""
        if self._ocr_reader is None:
            import easyocr

            logger.info("Loading EasyOCR on GPU …")
            self._ocr_reader = easyocr.Reader(["en"], gpu=True)

        try:
            img_np = np.array(image)
            results = self._ocr_reader.readtext(img_np, detail=0, batch_size=8)
            return self.clean_text(" ".join(results))
        except Exception:
            logger.warning("EasyOCR failed on page %d", page_number, exc_info=True)
            return ""

    # ------------------------------------------------------------------
    # Text cleaning & chunking
    # ------------------------------------------------------------------

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Normalise whitespace and strip control characters.

        Preserves unicode (math symbols, accented characters, etc.).
        """
        if not text:
            return ""
        # URLs
        text = re.sub(r"https?://\S+", " ", text)
        # Control characters only — NOT all non-ASCII
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def semantic_chunking(self, text: str) -> List[str]:
        """
        Split *text* into semantically coherent chunks.

        Headings are detected and prepended to subsequent chunks for context.
        Overlap is achieved by carrying the last paragraph of the previous
        chunk into the next (paragraph-based, not character-count-based).

        Note:
            ``self.chunk_overlap`` controls maximum chunk size; overlap is
            handled via paragraph carry-over, not a sliding character window.
        """
        heading_re = re.compile(
            r"^(?:[A-Z][A-Z\s]{3,}"
            r"|(?:\d+\.)+\s+\w"
            r"|[IVXLC]+\.\s+\w"
            r").{0,80}$",
            re.MULTILINE,
        )

        paragraphs = [
            p.strip()
            for p in re.split(r"\n{2,}", text)
            if len(p.strip()) > _MIN_PARAGRAPH_CHARS
        ]

        chunks: List[str] = []
        current_chunk = ""
        current_heading = ""

        for para in paragraphs:
            if heading_re.match(para) and len(para) < _MAX_HEADING_CHARS:
                current_heading = para
                continue

            candidate = f"{current_heading}\n{para}" if current_heading else para

            if not current_chunk:
                current_chunk = candidate
            elif len(current_chunk) + len(candidate) < self.chunk_size:
                current_chunk += "\n\n" + candidate
            else:
                chunks.append(current_chunk.strip())
                last_para = current_chunk.split("\n\n")[-1]
                current_chunk = (
                    f"{current_heading}\n{last_para}\n\n{candidate}"
                    if current_heading
                    else f"{last_para}\n\n{candidate}"
                )

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_page(
        text: str, page_number: int, file_path: str, total_pages: int,
    ) -> Dict[str, Any]:
        return {
            "text": text,
            "page_number": page_number,
            "file_name": os.path.basename(file_path),
            "file_path": file_path,
            "total_pages": total_pages,
        }

    @staticmethod
    def _is_blank_page(pil_img: Image.Image) -> bool:
        """True when pixel variance is below threshold (near-uniform image)."""
        return float(np.array(pil_img).std()) < _BLANK_PAGE_STD_THRESHOLD


# ---------------------------------------------------------------------------
# File-discovery utilities
# ---------------------------------------------------------------------------

def get_supported_files(data_dir: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Recursively find supported files under *data_dir*.

    Expected directory convention::

        data_dir/
          <subject>/
            <module>/
              file.pdf
    """
    if data_dir is None:
        data_dir = str(get_config().data_dir)

    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        logger.warning("Created data directory: %s", data_dir)
        return []

    files: List[Dict[str, str]] = []
    for root, _, filenames in os.walk(data_dir):
        for fname in filenames:
            if os.path.splitext(fname)[1].lower() not in SUPPORTED_EXTENSIONS:
                continue

            full = os.path.join(root, fname)
            rel = os.path.relpath(full, data_dir)
            parts = rel.split(os.sep)

            # parts = ["file.pdf"]                    → Unknown / General
            # parts = ["Math", "file.pdf"]            → Math    / General
            # parts = ["Math", "Algebra", "file.pdf"] → Math    / Algebra
            files.append({
                "full_path": full,
                "file_name": fname,
                "subject": parts[0] if len(parts) > 1 else "Unknown",
                "module": parts[1] if len(parts) > 2 else "General",
                "relative_path": rel,
            })

    logger.info("Found %d supported files in %s", len(files), data_dir)
    return files


# Backward-compat alias
get_pdf_files_recursive = get_supported_files


def get_organization_structure(
    data_dir: Optional[str] = None,
) -> Dict[str, Dict[str, List[str]]]:
    """Return ``{subject: {module: [filenames]}}``."""
    if data_dir is None:
        data_dir = str(get_config().data_dir)

    files = get_supported_files(data_dir)
    structure: Dict[str, Dict[str, List[str]]] = {}
    for f in files:
        structure.setdefault(f["subject"], {}).setdefault(f["module"], []).append(
            f["file_name"]
        )
    return structure