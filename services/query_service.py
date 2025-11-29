"""
Query service - handles the complete query flow.
Consolidates: search → cache check → generate → cache save
"""
import logging
from typing import Optional

from models import QueryResult, SearchResults, SourceDocument
from services.prompt_builder import PromptBuilder
from utils.llm_cache import question_hash, load_cached_answer, save_cached_answer

logger = logging.getLogger(__name__)


class QueryService:
    """
    Manages the complete query lifecycle.
    Used by both CLI (main.py) and API (flask_api_server.py).
    """
    
    def __init__(self, rag, ai_integration):
        """
        Initialize query service.
        
        Args:
            rag: The RAG instance (MergedLocalRAG)
            ai_integration: The AI integration instance (AIIntegration)
        """
        self.rag = rag
        self.ai = ai_integration
    
    def execute_query(
        self,
        question: str,
        use_cloud: bool = False,
        subject_filter: Optional[str] = None,
        module_filter: Optional[str] = None,
        n_results: int = None
    ) -> QueryResult:
        """
        Execute a complete query: search, check cache, generate answer, save cache.
        
        Args:
            question: The user's question
            use_cloud: Whether to use cloud LLM
            subject_filter: Optional subject filter for search
            module_filter: Optional module filter for search
            n_results: Number of results to retrieve (uses config default if None)
            
        Returns:
            QueryResult with answer and sources
        """
        # Step 1: Search for relevant documents
        logger.info("🔍 Searching for: %s", question[:100])
        
        from config import get_config
        config = get_config()
        n_results = n_results or config.default_search_results
        
        rag_response = self.rag.search(
            question,
            n_results=n_results,
            subject_filter=subject_filter,
            module_filter=module_filter
        )
        
        search_results = SearchResults.from_rag_response(rag_response)
        
        # Handle no results
        if search_results.total_results == 0:
            logger.warning("No relevant documents found")
            return QueryResult(
                question=question,
                answer="❌ No relevant information found in your documents.",
                sources=[],
                cached=False,
                mode="none",
                total_sources=0
            )
        
        # Convert to SourceDocument objects
        sources = search_results.to_source_documents()
        
        # Step 2: Check cache
        cache_key = self._generate_cache_key(question, sources)
        cached_result = load_cached_answer(cache_key)
        
        if cached_result:
            logger.info("✅ Using cached answer")
            return QueryResult(
                question=question,
                answer=cached_result.get("answer", ""),
                sources=self._sources_from_cache(cached_result, sources),
                cached=True,
                mode=cached_result.get("mode", "unknown"),
                total_sources=len(sources)
            )
        
        # Step 3: Generate answer
        logger.info("🤖 Generating answer (cloud=%s)", use_cloud)
        
        answer = self.ai.generate_answer(question, sources, use_cloud=use_cloud)
        
        # Step 4: Save to cache
        self._save_to_cache(cache_key, answer, sources, use_cloud)
        
        # Step 5: Return result
        return QueryResult(
            question=question,
            answer=answer,
            sources=sources,
            cached=False,
            mode="cloud" if use_cloud else "local",
            total_sources=len(sources)
        )
    
    def _generate_cache_key(self, question: str, 
                           sources: list[SourceDocument]) -> str:
        """Generate cache key from question and sources"""
        context_ids = [
            f"{s.file_name}:{s.page_number}:{s.chunk_number or 0}"
            for s in sources
        ]
        return question_hash(question, context_ids)
    
    def _save_to_cache(self, cache_key: str, answer: str, 
                      sources: list[SourceDocument], use_cloud: bool):
        """Save answer to cache with metadata"""
        try:
            cache_payload = {
                "answer": answer,
                "sources": [s.to_dict() for s in sources],
                "mode": "cloud" if use_cloud else "local"
            }
            save_cached_answer(cache_key, cache_payload)
            logger.debug("💾 Saved to cache: %s", cache_key[:16])
        except Exception as e:
            logger.warning("Failed to save cache: %s", e)
    
    def _sources_from_cache(self, cached_result: dict, 
                           current_sources: list[SourceDocument]) -> list[SourceDocument]:
        """
        Reconstruct SourceDocument objects from cached data.
        Falls back to current sources if cache doesn't have source details.
        """
        cached_sources = cached_result.get("sources", [])
        
        if not cached_sources:
            return current_sources
        
        # If cached sources are simple strings (old format), use current sources
        if isinstance(cached_sources[0], str):
            return current_sources
        
        # Reconstruct from cached dict format
        return [
            SourceDocument(
                text=s.get("text", ""),
                file_name=s.get("file_name", "unknown"),
                file_path=s.get("file_path", ""),
                page_number=s.get("page", 0),
                subject=s.get("subject"),
                module=s.get("module"),
                chunk_number=s.get("chunk_number"),
                score=s.get("score", 0.0)
            )
            for s in cached_sources
        ]