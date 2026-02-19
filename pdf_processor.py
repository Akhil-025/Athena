# pdf_processor.py 
import os
import re
from typing import List, Dict
from PyPDF2 import PdfReader
import logging
from config import get_config
import fitz  # pymupdf
import pdfplumber
import pytesseract
from PIL import Image
import io
import torch

logger = logging.getLogger(__name__)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class PDFProcessor:
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        config = get_config()
        self.chunk_size = chunk_size or config.chunk_size
        self.chunk_overlap = chunk_overlap or config.chunk_overlap

        # ---- GPU availability check (moved to __init__) ----
        self.use_gpu = torch.cuda.is_available()
        self._ocr_reader = None
        logger.info(f"PDFProcessor initialized: chunk_size={self.chunk_size}, "
                    f"overlap={self.chunk_overlap}, GPU available={self.use_gpu}")

    def extract_text_from_pdf(self, file_path: str) -> List[Dict]:
        pages = self._extract_pymupdf(file_path)

        # ---- Fixed condition: trigger OCR only if no page has substantial text ----
        if not any(len(p["text"]) > 200 for p in pages):
            try:
                pages = self._extract_ocr(file_path)
            except Exception as e:
                logger.warning(f"OCR failed for {file_path}, skipping: {e}")
                # return whatever pymupdf got, even if sparse
                return pages
        return pages

    def _extract_pymupdf(self, file_path: str) -> List[Dict]:
        pages = []
        doc = fitz.open(file_path)
        for i, page in enumerate(doc):
            text = page.get_text("text") or ""
            cleaned = self.enhanced_clean_text(text)
            if cleaned:
                pages.append({
                    "text": cleaned,
                    "page_number": i + 1,
                    "file_name": os.path.basename(file_path),
                    "file_path": file_path,
                    "total_pages": len(doc)
                })

        doc.close()
        return pages

    def _extract_ocr(self, file_path: str) -> List[Dict]:
        """
        Hybrid OCR per page:
          - First try Tesseract (fast CPU).
          - If result is too short (<=80 chars), fallback to EasyOCR (GPU) if available.
        """
        import numpy as np

        pages = []
        doc = fitz.open(file_path)

        for i, page in enumerate(doc):
            # Use 200 DPI (good balance between speed and accuracy)
            pix = page.get_pixmap(dpi=200)
            pil_img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")

            if self._is_blank_page(pil_img):
                del pix, pil_img
                continue

            # ---- Step 1: Fast Tesseract ----
            try:
                text = pytesseract.image_to_string(
                    pil_img,
                    config="--oem 3 --psm 6"
                )

            except Exception:
                text = ""

            cleaned = self.enhanced_clean_text(text)

            word_count = len(cleaned.split())

            # If strong OCR result → accept
            if word_count > 25:
                pages.append({
                    "text": cleaned,
                    "page_number": i + 1,
                    "file_name": os.path.basename(file_path),
                    "file_path": file_path,
                    "total_pages": len(doc)
                })
                del pix, pil_img
                continue

            # If some text exists (likely diagram captions), accept without GPU
            if 5 < word_count <= 25:
                pages.append({
                    "text": cleaned,
                    "page_number": i + 1,
                    "file_name": os.path.basename(file_path),
                    "file_path": file_path,
                    "total_pages": len(doc)
                })
                del pix, pil_img
                continue

            
            # ---- Step 2: EasyOCR fallback (GPU) ----
            if self.use_gpu:
                if self._ocr_reader is None:
                    import easyocr
                    logger.info("Loading EasyOCR on GPU...")
                    self._ocr_reader = easyocr.Reader(['en'], gpu=True)

                img_np = np.array(pil_img)
                try:
                    results = self._ocr_reader.readtext(img_np, detail=0, batch_size=8)
                    text = " ".join(results)
                except Exception as e:
                    logger.warning(f"EasyOCR failed on page {i+1}: {e}")
                    text = ""

                cleaned = self.enhanced_clean_text(text)

            # Final safety: ensure page is not dropped
            if not cleaned:
                cleaned = "[OCR_FAILED_PAGE]"

            pages.append({
                "text": cleaned,
                "page_number": i + 1,
                "file_name": os.path.basename(file_path),
                "file_path": file_path,
                "total_pages": len(doc)
            })

            del pix, pil_img


        doc.close()
        return pages

    def enhanced_clean_text(self, text: str) -> str:
        if not text:
            return ""
        # Remove URLs
        text = re.sub(r"https?://\S+", " ", text)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        # Keep technical symbols; remove accidental control chars
        text = re.sub(r"[^\x20-\x7E\n\r\t]", " ", text)
        # Keep G-codes together as tokens
        text = re.sub(r"\b(G\d+)\b", r" \1 ", text)
        return text.strip()

    def semantic_chunking(self, text: str) -> List[str]:
        heading_pattern = re.compile(
            r'^(?:[A-Z][A-Z\s]{3,}|(?:\d+\.)+\s+\w|[IVXLC]+\.\s+\w).{0,80}$',
            re.MULTILINE
        )
        paragraphs = re.split(r'\n{2,}', text)
        paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 40]
        chunks, current_chunk, current_heading = [], "", ""
        for para in paragraphs:
            if heading_pattern.match(para) and len(para) < 120:
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
                current_chunk = f"{current_heading}\n{last_para}\n\n{candidate}" if current_heading else f"{last_para}\n\n{candidate}"
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks

    def process_pdf(self, file_path: str) -> List[Dict]:
        pages = self.extract_text_from_pdf(file_path)
        all_chunks = []
        for page in pages:
            if page["text"] == "[OCR_FAILED_PAGE]":
                continue
            chunks = self.semantic_chunking(page["text"])
            for idx, c in enumerate(chunks, start=1):
                if len(c) < 100 or len(c.split()) < 15:
                    continue
                all_chunks.append({
                    "text": c,
                    "file_name": page["file_name"],
                    "file_path": page["file_path"],
                    "page_number": page["page_number"],
                    "chunk_number": idx,
                    "total_chunks": len(chunks),
                    "total_pages": page["total_pages"]
                })
        logger.info("Created %d chunks for %s", len(all_chunks), os.path.basename(file_path))
        return all_chunks
    
    def _is_blank_page(self, pil_img: Image.Image) -> bool:
        import numpy as np
        arr = np.array(pil_img)
        # If variance is extremely low → page is blank
        return arr.std() < 5



def get_pdf_files_recursive(data_dir: str = None) -> List[Dict[str, str]]:
    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md", ".epub"}
    if data_dir is None:
        config = get_config()
        data_dir = str(config.data_dir)

    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        logger.warning("Created data directory: %s", data_dir)
        return []
        
    pdf_files = []
    for root, _, files in os.walk(data_dir):
        for fname in files:
            if os.path.splitext(fname)[1].lower() in SUPPORTED_EXTENSIONS:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, data_dir)
                parts = rel.split(os.sep)
                subject = parts[0] if len(parts) > 0 else "Unknown"
                module = parts[1] if len(parts) > 1 else "General"
                pdf_files.append({
                    "full_path": full,
                    "file_name": fname,
                    "subject": subject,
                    "module": module,
                    "relative_path": rel
                })
    logger.info("Found %d PDF files in %s", len(pdf_files), data_dir)
    return pdf_files


def get_organization_structure(data_dir: str = "./data") -> Dict[str, Dict[str, List[str]]]:
    files = get_pdf_files_recursive(data_dir)
    structure = {}
    for f in files:
        s = f["subject"]
        m = f["module"]
        structure.setdefault(s, {}).setdefault(m, []).append(f["file_name"])
    return structure