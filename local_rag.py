# local_rag.py
import chromadb
from sentence_transformers import SentenceTransformer
import numpy as np
import os
import logging
from typing import List, Dict, Any, Optional
from pdf_processor import PDFProcessor, get_pdf_files_recursive, get_organization_structure

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LocalRAG:
    def __init__(self, persist_directory: str = "./chroma_db", model_name: str = "all-MiniLM-L6-v2"):
        self.persist_directory = persist_directory
        self.model_name = model_name
        
        # Initialize components
        self._initialize_chroma()
        self._initialize_embedder()
        self.pdf_processor = PDFProcessor()
        
        logger.info(f"🚀 Local RAG initialized with model: {model_name}")
    
    def _initialize_chroma(self):
        """Initialize ChromaDB client and collection."""
        try:
            self.client = chromadb.PersistentClient(path=self.persist_directory)
            self.collection = self.client.get_or_create_collection(
                name="engineering_documents",
                metadata={"description": "Athena Knowledge Base"}
            )
            logger.info("✅ ChromaDB initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize ChromaDB: {e}")
            raise
    
    def _initialize_embedder(self):
        """Initialize the embedding model."""
        try:
            self.embedder = SentenceTransformer(self.model_name)
            logger.info(f"✅ Embedding model '{self.model_name}' loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load embedding model: {e}")
            raise
    
    def ingest_pdf(self, file_info: Dict[str, str]) -> int:
        """
        Ingest a single PDF file into the vector database.
        
        Args:
            file_info: Dictionary containing file information from get_pdf_files_recursive
        
        Returns:
            Number of chunks added
        """
        try:
            file_path = file_info['full_path']
            
            # Process PDF
            chunks = self.pdf_processor.process_pdf(file_path)
            
            if not chunks:
                logger.warning(f"⚠️ No text extracted from {file_path}")
                return 0
            
            # Prepare data for ChromaDB
            ids = []
            documents = []
            metadatas = []
            embeddings = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{file_info['subject']}_{file_info['module']}_{os.path.basename(file_path)}_{chunk['page_number']}_{chunk['chunk_number']}"
                
                ids.append(chunk_id)
                documents.append(chunk['text'])
                metadatas.append({
                    'file_name': chunk['file_name'],
                    'file_path': chunk['file_path'],
                    'subject': file_info['subject'],
                    'module': file_info['module'],
                    'page_number': chunk['page_number'],
                    'chunk_number': chunk['chunk_number'],
                    'total_pages': chunk['total_pages']
                })
                
                # Generate embedding
                embedding = self.embedder.encode(chunk['text']).tolist()
                embeddings.append(embedding)
            
            # Add to collection
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings
            )
            
            logger.info(f"✅ Added {len(chunks)} chunks from {file_info['subject']}/{file_info['module']}/{os.path.basename(file_path)}")
            return len(chunks)
            
        except Exception as e:
            logger.error(f"❌ Failed to ingest {file_info['full_path']}: {e}")
            return 0
    
    def ingest_directory(self, data_dir: str = "./data") -> Dict[str, Any]:
        """
        Ingest all PDFs from a directory recursively.
        
        Returns:
            Dictionary with ingestion statistics
        """
        pdf_files = get_pdf_files_recursive(data_dir)
        results = {
            'total_files': 0,
            'total_chunks': 0,
            'by_subject': {},
            'by_module': {}
        }
        
        if not pdf_files:
            logger.warning(f"📭 No PDF files found in {data_dir}")
            return results
        
        logger.info(f"📚 Processing {len(pdf_files)} PDF files from {data_dir}")
        
        for file_info in pdf_files:
            chunk_count = self.ingest_pdf(file_info)
            
            # Update statistics
            results['total_files'] += 1
            results['total_chunks'] += chunk_count
            
            # Update subject statistics
            subject = file_info['subject']
            if subject not in results['by_subject']:
                results['by_subject'][subject] = {'files': 0, 'chunks': 0}
            results['by_subject'][subject]['files'] += 1
            results['by_subject'][subject]['chunks'] += chunk_count
            
            # Update module statistics
            module_key = f"{subject}/{file_info['module']}"
            if module_key not in results['by_module']:
                results['by_module'][module_key] = {'files': 0, 'chunks': 0}
            results['by_module'][module_key]['files'] += 1
            results['by_module'][module_key]['chunks'] += chunk_count
        
        # Log detailed statistics
        logger.info(f"🎉 Ingested {results['total_chunks']} total chunks from {results['total_files']} files")
        for subject, stats in results['by_subject'].items():
            logger.info(f"   📂 {subject}: {stats['files']} files, {stats['chunks']} chunks")
        
        return results
    
    def search(self, query: str, n_results: int = 5, 
               subject_filter: Optional[str] = None,
               module_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Search for relevant documents with organizational filtering.
        
        Args:
            query: Search query
            n_results: Number of results to return
            subject_filter: Filter by subject
            module_filter: Filter by module
        
        Returns:
            Search results with documents and metadata
        """
        try:
            # Generate query embedding
            query_embedding = self.embedder.encode([query]).tolist()
            
            # Prepare filters
            where_filter = {}
            if subject_filter:
                where_filter['subject'] = subject_filter
            if module_filter:
                where_filter['module'] = module_filter
            
            # Search in ChromaDB
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                where=where_filter if where_filter else None,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            formatted_results = {
                'documents': results['documents'][0] if results['documents'] else [],
                'metadatas': results['metadatas'][0] if results['metadatas'] else [],
                'distances': results['distances'][0] if results['distances'] else [],
                'query': query,
                'filters': {'subject': subject_filter, 'module': module_filter},
                'total_results': len(results['documents'][0]) if results['documents'] else 0
            }
            
            logger.info(f"🔍 Found {formatted_results['total_results']} results for query: '{query}'")
            return formatted_results
            
        except Exception as e:
            logger.error(f"❌ Search failed for query '{query}': {e}")
            return {
                'documents': [],
                'metadatas': [],
                'distances': [],
                'query': query,
                'filters': {'subject': subject_filter, 'module': module_filter},
                'total_results': 0
            }
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get detailed statistics about the collection."""
        try:
            count = self.collection.count()
            
            # Get unique subjects and modules
            all_metadatas = self.collection.get(include=['metadatas'])
            subjects = set()
            modules = set()
            
            if all_metadatas and 'metadatas' in all_metadatas:
                for metadata in all_metadatas['metadatas']:
                    if metadata and 'subject' in metadata:
                        subjects.add(metadata['subject'])
                    if metadata and 'module' in metadata:
                        modules.add(metadata['module'])
            
            return {
                'total_chunks': count,
                'subjects': list(subjects),
                'modules': list(modules),
                'persist_directory': self.persist_directory,
                'embedding_model': self.model_name
            }
        except Exception as e:
            logger.error(f"❌ Failed to get collection stats: {e}")
            return {'total_chunks': 0, 'subjects': [], 'modules': []}
    
    def get_organization_info(self) -> Dict[str, Any]:
        """Get organizational structure information."""
        stats = self.get_collection_stats()
        file_structure = get_organization_structure()
        
        return {
            'database_stats': stats,
            'file_structure': file_structure
        }
    
    def clear_database(self):
        """Clear all data from the collection."""
        try:
            self.client.delete_collection("engineering_documents")
            self.collection = self.client.get_or_create_collection("engineering_documents")
            logger.info("🗑️ Database cleared successfully")
        except Exception as e:
            logger.error(f"❌ Failed to clear database: {e}")

def create_rag_system(data_dir: str = "./data", reload: bool = False) -> LocalRAG:
    """
    Create and initialize RAG system with documents.
    
    Args:
        data_dir: Directory containing PDF files
        reload: Whether to reload documents even if database exists
    
    Returns:
        Initialized LocalRAG instance
    """
    rag = LocalRAG()
    
    # Check if database already has data
    stats = rag.get_collection_stats()
    
    if stats['total_chunks'] == 0 or reload:
        logger.info("📥 Loading documents into database...")
        rag.ingest_directory(data_dir)
    else:
        logger.info(f"📊 Database already contains {stats['total_chunks']} chunks across {len(stats['subjects'])} subjects")
    
    return rag