# pdf_processor.py 
import os
import re
from typing import List, Dict
from PyPDF2 import PdfReader
import logging

logger = logging.getLogger(__name__)

class PDFProcessor:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def extract_text_from_pdf(self, file_path: str) -> List[Dict]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF not found: {file_path}")

        logger.info("Extracting PDF: %s", os.path.basename(file_path))
        pages = []
        try:
            reader = PdfReader(file_path)
            num_pages = len(reader.pages)
            for i, page in enumerate(reader.pages):
                try:
                    text = page.extract_text() or ""
                except Exception:
                    text = ""
                cleaned = self.enhanced_clean_text(text)
                if cleaned:
                    pages.append({
                        "text": cleaned,
                        "page_number": i + 1,
                        "file_name": os.path.basename(file_path),
                        "file_path": file_path,
                        "total_pages": num_pages
                    })
            logger.info("Extracted %d pages from %s", len(pages), os.path.basename(file_path))
            return pages
        except Exception as e:
            logger.exception("Failed reading PDF %s: %s", file_path, e)
            raise

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
        # Split into sentences (simple heuristic)
        sentences = re.split(r'(?<=[\.\?\!])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        chunks = []
        current = ""
        for sent in sentences:
            if not current:
                current = sent
            elif len(current) + 1 + len(sent) <= self.chunk_size:
                current = current + " " + sent
            else:
                chunks.append(current.strip())
                # overlap: carry last part of current into new start
                overlap = " ".join(current.split()[-max(1, int(self.chunk_overlap / 10)):])
                current = overlap + " " + sent
        if current:
            chunks.append(current.strip())
        return chunks

    def process_pdf(self, file_path: str) -> List[Dict]:
        pages = self.extract_text_from_pdf(file_path)
        all_chunks = []
        for page in pages:
            chunks = self.semantic_chunking(page["text"])
            for idx, c in enumerate(chunks, start=1):
                if len(c) < 30:
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


def get_pdf_files_recursive(data_dir: str = "./data") -> List[Dict[str, str]]:
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        logger.warning("Created data directory: %s", data_dir)
        return []
    pdf_files = []
    for root, _, files in os.walk(data_dir):
        for fname in files:
            if fname.lower().endswith(".pdf"):
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
