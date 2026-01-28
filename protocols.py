"""
Protocol definitions for Athena RAG system.
Defines interfaces for LLM and RAG components to enable proper type checking.
"""
from typing import Protocol, Dict, Any, List, Optional, runtime_checkable


@runtime_checkable
class LLMProtocol(Protocol):
    """
    Protocol for Language Model implementations.
    Defines the interface that all LLM wrappers must implement.
    """
    
    def generate(self, prompt: str, timeout: int = 60) -> Dict[str, Any]:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The input prompt text
            timeout: Maximum time to wait for response in seconds
            
        Returns:
            Dictionary with keys:
                - text: str - The generated text
                - error: Optional[str] - Error message if generation failed
                - meta: Dict[str, Any] - Metadata about generation
        """
        ...


@runtime_checkable
class RAGProtocol(Protocol):
    """
    Protocol for RAG (Retrieval-Augmented Generation) implementations.
    Defines the interface for document search and retrieval systems.
    """
    
    def search(
        self,
        query: str,
        n_results: int = 10,
        subject_filter: Optional[str] = None,
        module_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for relevant documents.
        
        Args:
            query: The search query
            n_results: Number of results to return
            subject_filter: Optional subject filter
            module_filter: Optional module filter
            
        Returns:
            Dictionary with search results containing:
                - documents: List[str]
                - metadatas: List[Dict[str, Any]]
                - distances: List[float]
                - query: str
                - total_results: int
        """
        ...
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the document collection.
        
        Returns:
            Dictionary with collection statistics:
                - total_chunks: int
                - subjects: List[str]
                - modules: List[str]
        """
        ...
    
    def ingest_directory(
        self,
        data_dir: str,
        rebuild_bm25: bool = True
    ) -> Dict[str, Any]:
        """
        Ingest documents from a directory.
        
        Args:
            data_dir: Path to directory containing documents
            rebuild_bm25: Whether to rebuild BM25 index
            
        Returns:
            Dictionary with ingestion results
        """
        ...
    
    def clear_database(self) -> None:
        """Clear all documents from the database."""
        ...


@runtime_checkable
class PDFProcessorProtocol(Protocol):
    """
    Protocol for PDF processing implementations.
    """
    
    def extract_text_from_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract text from a PDF file.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            List of dictionaries containing page information
        """
        ...
    
    def process_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Process a PDF into chunks.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            List of dictionaries containing chunk information
        """
        ...


@runtime_checkable
class EmbedderProtocol(Protocol):
    """
    Protocol for text embedding models.
    """
    
    def encode(
        self,
        texts: List[str],
        show_progress_bar: bool = False
    ) -> Any:
        """
        Encode texts into embeddings.
        
        Args:
            texts: List of text strings to encode
            show_progress_bar: Whether to show progress
            
        Returns:
            Array or list of embeddings
        """
        ...


# Type aliases for common types
FileInfo = Dict[str, str]  # Contains: full_path, file_name, subject, module
ChunkInfo = Dict[str, Any]  # Contains: text, file_name, page_number, chunk_number
SearchFilter = Optional[str]
EmbeddingVector = List[float]