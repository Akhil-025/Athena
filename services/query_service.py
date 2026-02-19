"""
Query service - orchestrates the complete query pipeline.

Features:
- Robust error handling with automatic fallback
- Smart caching with versioning
- Query optimization (source selection, answer quality validation)
- Comprehensive observability (logging, metrics)
- Async-ready architecture
"""
import logging
import time
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from models import QueryResult, SearchResults, SourceDocument
from services.prompt_builder import PromptBuilder
from services.context_assembler import ContextAssembler
from utils.llm_cache import question_hash, load_cached_answer, save_cached_answer
from exceptions import QueryError, LLMError, RAGError
from config import get_config


logger = logging.getLogger(__name__)


class AnswerQuality(Enum):
    """Answer quality assessment"""
    HIGH = "high"           # Detailed, confident answer
    MEDIUM = "medium"       # Adequate answer
    LOW = "low"             # Vague or minimal answer
    INSUFFICIENT = "insufficient"  # Explicit "don't know"


@dataclass
class QueryMetrics:
    """Metrics for query execution"""
    search_time_ms: float = 0
    generation_time_ms: float = 0
    total_time_ms: float = 0
    sources_found: int = 0
    sources_used: int = 0
    cache_hit: bool = False
    fallback_triggered: bool = False
    answer_quality: Optional[AnswerQuality] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'search_time_ms': self.search_time_ms,
            'generation_time_ms': self.generation_time_ms,
            'total_time_ms': self.total_time_ms,
            'sources_found': self.sources_found,
            'sources_used': self.sources_used,
            'cache_hit': self.cache_hit,
            'fallback_triggered': self.fallback_triggered,
            'answer_quality': self.answer_quality.value if self.answer_quality else None
        }


@dataclass
class QueryContext:
    """Context for query execution"""
    question: str
    use_cloud: bool
    subject_filter: Optional[str] = None
    module_filter: Optional[str] = None
    n_results: Optional[int] = None
    force_refresh: bool = False  # Bypass cache
    include_metrics: bool = True
    
    # Runtime data
    sources: list[SourceDocument] = field(default_factory=list)
    search_results: Optional[SearchResults] = None
    cache_key: Optional[str] = None
    metrics: QueryMetrics = field(default_factory=QueryMetrics)


class AnswerQualityAssessor:
    """Assesses the quality of generated answers"""
    
    # Patterns indicating insufficient answers
    INSUFFICIENT_PATTERNS = [
        "i don't",
        "i cannot",
        "i'm not sure",
        "not in the context",
        "no information",
        "cannot find",
        "not mentioned",
        "does not cover",
        "insufficient information"
    ]
    
    MIN_WORD_COUNT = 15  # Minimum words for quality answer
    
    @classmethod
    def assess(cls, answer: str) -> AnswerQuality:
        """
        Assess answer quality.
        
        Args:
            answer: Generated answer text
            
        Returns:
            AnswerQuality enum value
        """
        answer_lower = answer.lower().strip()
        word_count = len(answer.split())
        
        # Check for explicit "don't know" patterns
        if any(pattern in answer_lower for pattern in cls.INSUFFICIENT_PATTERNS):
            return AnswerQuality.INSUFFICIENT
        
        # Check word count
        if word_count < cls.MIN_WORD_COUNT:
            return AnswerQuality.LOW
        
        # Assess based on length and structure
        if word_count > 100 and '\n' in answer:
            return AnswerQuality.HIGH
        elif word_count > 50:
            return AnswerQuality.MEDIUM
        else:
            return AnswerQuality.LOW


class CacheManager:
    """Manages query result caching with versioning"""
    
    CACHE_VERSION = "v2"  # Increment when cache format changes
    
    @classmethod
    def generate_key(
        cls,
        question: str,
        sources: list[SourceDocument],
        use_cloud: bool
    ) -> str:
        """Generate cache key from query parameters"""
        context_ids = [
            f"{s.file_name}:{s.page_number}:{s.chunk_number or 0}"
            for s in sources
        ]
        mode = "cloud" if use_cloud else "local"
        base_key = f"{cls.CACHE_VERSION}:{mode}:{question}"
        return question_hash(base_key, context_ids)
    
    @classmethod
    def load(cls, cache_key: str) -> Optional[Dict[str, Any]]:
        """Load from cache with version checking"""
        try:
            cached = load_cached_answer(cache_key)
            if cached and cached.get("version") == cls.CACHE_VERSION:
                return cached
            elif cached:
                logger.debug(f"Cache version mismatch, ignoring cached result")
            return None
        except Exception as e:
            logger.warning(f"Cache load failed: {e}")
            return None
    
    @classmethod
    def save(
        cls,
        cache_key: str,
        answer: str,
        sources: list[SourceDocument],
        use_cloud: bool,
        quality: AnswerQuality
    ) -> bool:
        """Save to cache with metadata"""
        try:
            payload = {
                "version": cls.CACHE_VERSION,
                "answer": answer,
                "sources": [s.to_dict() for s in sources],
                "mode": "cloud" if use_cloud else "local",
                "quality": quality.value,
                "timestamp": time.time()
            }
            save_cached_answer(cache_key, payload)
            logger.debug(f"Saved to cache: {cache_key[:16]}... (quality={quality.value})")
            return True
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")
            return False
    
    @classmethod
    def reconstruct_sources(
        cls,
        cached_data: Dict[str, Any],
        fallback_sources: list[SourceDocument]
    ) -> list[SourceDocument]:
        """Reconstruct SourceDocument objects from cached data"""
        cached_sources = cached_data.get("sources", [])
        
        if not cached_sources or not isinstance(cached_sources[0], dict):
            return fallback_sources
        
        try:
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
        except Exception as e:
            logger.warning(f"Failed to reconstruct cached sources: {e}")
            return fallback_sources


class QueryService:
    """
    Orchestrates the complete query pipeline:
    1. Search for relevant documents
    2. Check cache
    3. Generate answer (with fallback)
    4. Assess quality
    5. Save to cache
    """
    
    def __init__(self, rag, ai_integration):
        """
        Initialize query service.
        
        Args:
            rag: RAG instance (MergedLocalRAG)
            ai_integration: AI integration instance (AIIntegration)
        """
        self.rag = rag
        self.ai = ai_integration
        self.config = get_config()
        self.cache = CacheManager()
        self.quality_assessor = AnswerQualityAssessor()
    
    def execute(
        self,
        question: str,
        use_cloud: bool = False,
        subject_filter: Optional[str] = None,
        module_filter: Optional[str] = None,
        n_results: Optional[int] = None,
        force_refresh: bool = False
    ) -> QueryResult:
        """
        Execute complete query with error handling and fallback.
        
        Args:
            question: User's question
            use_cloud: Use cloud LLM
            subject_filter: Optional subject filter
            module_filter: Optional module filter
            n_results: Number of results to retrieve
            force_refresh: Bypass cache
            
        Returns:
            QueryResult with answer, sources, and metrics
            
        Raises:
            QueryError: If query fails completely
        """
        start_time = time.time()
        
        ctx = QueryContext(
            question=question,
            use_cloud=use_cloud,
            subject_filter=subject_filter,
            module_filter=module_filter,
            n_results=n_results or self.config.default_search_results,
            force_refresh=force_refresh
        )
        
        try:
            # Pipeline stages
            self._execute_search(ctx)
            
            if not force_refresh:
                cached_result = self._try_cache(ctx)
                if cached_result:
                    ctx.metrics.total_time_ms = (time.time() - start_time) * 1000
                    return cached_result
            
            answer = self._generate_answer(ctx)
            quality = self.quality_assessor.assess(answer)
            ctx.metrics.answer_quality = quality
            
            # Try fallback if quality is poor
            if quality in (AnswerQuality.LOW, AnswerQuality.INSUFFICIENT):
                answer = self._try_fallback(ctx, answer, quality)
            
            # Save to cache
            if ctx.cache_key:
                self.cache.save(
                    ctx.cache_key,
                    answer,
                    ctx.sources,
                    ctx.use_cloud,
                    ctx.metrics.answer_quality
                )
            
            ctx.metrics.total_time_ms = (time.time() - start_time) * 1000
            
            return self._build_result(ctx, answer)
            
        except (RAGError, LLMError) as e:
            logger.error(f"Query failed: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in query execution: {e}")
            raise QueryError(f"Query execution failed: {e}") from e
    
    def _execute_search(self, ctx: QueryContext) -> None:
        """Execute RAG search"""
        logger.info(f"🔍 Searching: {ctx.question[:100]}")
        search_start = time.time()
        
        try:
            rag_response = self.rag.search(
                ctx.question,
                n_results=ctx.n_results,
                subject_filter=ctx.subject_filter,
                module_filter=ctx.module_filter
            )
            
            ctx.search_results = SearchResults.from_rag_response(rag_response)
            ctx.sources = ctx.search_results.to_source_documents()
            ctx.metrics.sources_found = len(ctx.sources)
            ctx.metrics.search_time_ms = (time.time() - search_start) * 1000
            
            logger.info(f"✅ Found {len(ctx.sources)} sources in {ctx.metrics.search_time_ms:.0f}ms")
            
        except Exception as e:
            logger.exception(f"Search failed: {e}")
            raise RAGError(f"Failed to search documents: {e}") from e
    
    def _try_cache(self, ctx: QueryContext) -> Optional[QueryResult]:
        """Try to load from cache"""
        ctx.cache_key = self.cache.generate_key(
            ctx.question,
            ctx.sources,
            ctx.use_cloud
        )
        
        cached = self.cache.load(ctx.cache_key)
        if not cached:
            return None
        
        logger.info("✅ Cache hit")
        ctx.metrics.cache_hit = True
        
        sources = self.cache.reconstruct_sources(cached, ctx.sources)
        
        return QueryResult(
            question=ctx.question,
            answer=cached.get("answer", ""),
            sources=sources,
            cached=True,
            mode=cached.get("mode", "unknown"),
            total_sources=len(sources),
            metrics=ctx.metrics.to_dict() if ctx.include_metrics else None
        )
    
    def _generate_answer(self, ctx: QueryContext) -> str:
        """Generate answer using AI"""
        if not ctx.sources:
            return "❌ No relevant information found in your documents."
        
        logger.info(f"🤖 Generating answer (cloud={ctx.use_cloud})")
        gen_start = time.time()
        
        try:
            # Determine how many sources to use
            max_sources = (
                self.config.max_chunks_cloud if ctx.use_cloud 
                else self.config.max_chunks_local
            )
            sources_to_use = ctx.sources[:max_sources]
            ctx.metrics.sources_used = len(sources_to_use)
            
            answer = self.ai.generate_answer(
                ctx.question,
                sources_to_use,
                use_cloud=ctx.use_cloud
            )
            
            ctx.metrics.generation_time_ms = (time.time() - gen_start) * 1000
            
            logger.info(
                f"✅ Generated in {ctx.metrics.generation_time_ms:.0f}ms "
                f"({len(answer)} chars)"
            )
            
            return answer
            
        except LLMError as e:
            logger.error(f"LLM generation failed: {e}")
            raise LLMError(
                f"Failed to generate answer for '{ctx.question[:50]}...': {e}"
            ) from e
    
    def _try_fallback(
        self,
        ctx: QueryContext,
        current_answer: str,
        current_quality: AnswerQuality
    ) -> str:
        """Try fallback strategy if answer quality is poor"""
        # Only fallback from local to cloud
        if ctx.use_cloud or not self.ai.has_cloud_llm():
            logger.info(
                f"No fallback available (cloud={ctx.use_cloud}, "
                f"has_cloud={self.ai.has_cloud_llm()})"
            )
            return current_answer
        
        logger.info(
            f"Answer quality {current_quality.value}, trying cloud fallback"
        )
        
        try:
            fallback_answer = self.ai.generate_answer(
                ctx.question,
                ctx.sources,
                use_cloud=True
            )
            
            fallback_quality = self.quality_assessor.assess(fallback_answer)
            
            # Use fallback if it's better
            if fallback_quality.value < current_quality.value:  # Lower enum = better
                logger.info(
                    f"✅ Fallback improved quality: "
                    f"{current_quality.value} → {fallback_quality.value}"
                )
                ctx.metrics.fallback_triggered = True
                ctx.metrics.answer_quality = fallback_quality
                ctx.use_cloud = True  # Update mode for result
                return fallback_answer
            else:
                logger.info(
                    f"Fallback didn't improve quality "
                    f"({fallback_quality.value}), keeping original"
                )
                return current_answer
                
        except LLMError as e:
            logger.warning(f"Fallback failed: {e}")
            return current_answer
    
    def _build_result(self, ctx: QueryContext, answer: str) -> QueryResult:
        """Build final QueryResult"""
        return QueryResult(
            question=ctx.question,
            answer=answer,
            sources=ctx.sources,
            cached=False,
            mode="cloud" if ctx.use_cloud else "local",
            total_sources=len(ctx.sources),
            metrics=ctx.metrics.to_dict() if ctx.include_metrics else None
        )
    
    # Backwards compatibility
    def execute_query(self, *args, **kwargs) -> QueryResult:
        """Alias for execute() - backwards compatibility"""
        return self.execute(*args, **kwargs)