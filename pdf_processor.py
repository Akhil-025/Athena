# pdf_processor.py
import os
import re
from typing import List, Dict
from PyPDF2 import PdfReader
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PDFProcessor:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def extract_text_from_pdf(self, file_path: str) -> List[Dict[str, any]]:
        """Extract text from PDF with page-level metadata and better text cleaning."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        logger.info(f"📖 Extracting text from: {os.path.basename(file_path)}")
        
        try:
            reader = PdfReader(file_path)
            pages_data = []
            
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                
                if text.strip():
                    # Enhanced text cleaning
                    cleaned_text = self.enhanced_clean_text(text)
                    
                    pages_data.append({
                        'text': cleaned_text,
                        'page_number': page_num + 1,
                        'file_name': os.path.basename(file_path),
                        'file_path': file_path,
                        'total_pages': len(reader.pages)
                    })
            
            logger.info(f"✅ Extracted {len(pages_data)} pages from {os.path.basename(file_path)}")
            return pages_data
            
        except Exception as e:
            logger.error(f"❌ Failed to extract text from {file_path}: {e}")
            raise
    
    def enhanced_clean_text(self, text: str) -> str:
        """Enhanced text cleaning for better search relevance."""
        # Remove URLs that might be interfering with semantic meaning
        text = re.sub(r'https?://\S+', '', text)
        
        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but preserve technical symbols and codes
        text = re.sub(r'[^\w\s\.\,\-\+\*\/\(\)\[\]\{\}\:\;\"\'\=\<\>\%\$\#\@\!\&\|\?]', ' ', text)
        
        # Preserve G-codes and technical terms
        text = re.sub(r'\b(G\d+)\b', r' \1 ', text)  # Ensure G-codes are treated as separate tokens
        
        return text.strip()
    
    def semantic_chunking(self, text: str) -> List[str]:
        """Improved chunking that preserves semantic meaning."""
        # Split by sentences first for better context
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # If adding this sentence exceeds chunk size, save current chunk
            if len(current_chunk) + len(sentence) > self.chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                # Start new chunk with overlap from previous chunk
                overlap_sentences = current_chunk.split('.')[-2:]  # Last 2 sentences as overlap
                current_chunk = '. '.join(overlap_sentences) + '. ' + sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def process_pdf(self, file_path: str) -> List[Dict[str, any]]:
        """Enhanced PDF processing with better chunking."""
        pages_data = self.extract_text_from_pdf(file_path)
        all_chunks = []
        
        for page_data in pages_data:
            # Use semantic chunking instead of simple word splitting
            chunks = self.semantic_chunking(page_data['text'])
            
            for chunk_num, chunk in enumerate(chunks):
                if len(chunk) > 50:  # Only include meaningful chunks
                    all_chunks.append({
                        'text': chunk,
                        'file_name': page_data['file_name'],
                        'file_path': page_data['file_path'],
                        'page_number': page_data['page_number'],
                        'chunk_number': chunk_num + 1,
                        'total_chunks': len(chunks),
                        'total_pages': page_data['total_pages']
                    })
        
        logger.info(f"📊 Created {len(all_chunks)} semantic chunks from {os.path.basename(file_path)}")
        return all_chunks



def get_pdf_files_recursive(data_dir: str = "./data") -> List[Dict[str, str]]:
    """
    Get all PDF files recursively with their organizational structure.
    
    Returns:
        List of dictionaries with file info including subject and module
    """
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        logger.warning(f"📁 Created data directory: {data_dir}")
        return []
    
    pdf_files = []
    
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.lower().endswith('.pdf'):
                full_path = os.path.join(root, file)
                
                # Extract organizational structure
                relative_path = os.path.relpath(full_path, data_dir)
                path_parts = relative_path.split(os.sep)
                
                # Determine subject and module
                subject = path_parts[0] if len(path_parts) > 0 else "Unknown"
                module = path_parts[1] if len(path_parts) > 1 else "General"
                
                pdf_files.append({
                    'full_path': full_path,
                    'file_name': file,
                    'subject': subject,
                    'module': module,
                    'relative_path': relative_path
                })
    
    logger.info(f"📚 Found {len(pdf_files)} PDF files in {data_dir}")
    
    # Log organization structure
    subjects = set(f['subject'] for f in pdf_files)
    for subject in subjects:
        subject_files = [f for f in pdf_files if f['subject'] == subject]
        modules = set(f['module'] for f in subject_files)
        logger.info(f"   📂 {subject}: {len(subject_files)} files in {len(modules)} modules")
    
    return pdf_files

def get_organization_structure(data_dir: str = "./data") -> Dict[str, Dict[str, List[str]]]:
    """Get the complete organizational structure of documents."""
    pdf_files = get_pdf_files_recursive(data_dir)
    
    structure = {}
    for file_info in pdf_files:
        subject = file_info['subject']
        module = file_info['module']
        file_name = file_info['file_name']
        
        if subject not in structure:
            structure[subject] = {}
        
        if module not in structure[subject]:
            structure[subject][module] = []
        
        structure[subject][module].append(file_name)
    
    return structure