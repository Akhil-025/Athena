"""
Context assembly service - formats RAG search results into context strings.
Consolidates all context formatting logic in one place.

Features:
- Smart truncation with token awareness
- Configurable formatting strategies
- Performance optimizations
- Comprehensive error handling
"""
from typing import List, Optional, Protocol
from dataclasses import dataclass
from enum import Enum
import logging

from models import SourceDocument, SearchResults


logger = logging.getLogger(__name__)


class FormattingStrategy(Enum):
    """Context formatting strategies for different LLM types"""
    DETAILED = "detailed"  # Full headers with metadata
    COMPACT = "compact"    # Minimal headers
    PLAIN = "plain"        # No headers, just content
    NUMBERED = "numbered"  # Numbered citations for cloud LLMs


@dataclass
class ContextConfig:
    """Configuration for context assembly"""
    max_sources: int = 5
    max_chars_per_source: int = 2000
    include_headers: bool = True
    strategy: FormattingStrategy = FormattingStrategy.DETAILED
    separator: str = "\n\n"
    truncation_suffix: str = "..."
    
    @classmethod
    def for_local_llm(cls) -> 'ContextConfig':
        """Optimized config for local LLMs (more context, simpler format)"""
        return cls(
            max_sources=5,
            max_chars_per_source=3000,
            strategy=FormattingStrategy.COMPACT
        )
    
    @classmethod
    def for_cloud_llm(cls) -> 'ContextConfig':
        """Optimized config for cloud LLMs (fewer sources, richer format)"""
        return cls(
            max_sources=3,
            max_chars_per_source=2000,
            strategy=FormattingStrategy.NUMBERED
        )


class ISourceFormatter(Protocol):
    """Interface for source formatting strategies"""
    def format_source(self, source: SourceDocument, index: int) -> str:
        """Format a single source with optional header"""
        ...


class DetailedFormatter:
    """Detailed formatting with full metadata"""
    
    @staticmethod
    def format_source(source: SourceDocument, index: int) -> str:
        subject_module = DetailedFormatter._format_subject_module(source)
        header = (
            f"--- Excerpt {index}: {source.file_name} "
            f"| {subject_module} "
            f"(Page {source.page_number}"
            f"{f', Chunk {source.chunk_number}' if source.chunk_number else ''}"
            f"{f', Relevance: {source.score:.2f}' if source.score else ''}) ---"
        )
        return f"{header}\n{source.text}"
    
    @staticmethod
    def _format_subject_module(source: SourceDocument) -> str:
        """Build subject→module path or return 'General'"""
        if not source.subject:
            return "General"
        
        if source.module:
            return f"{source.subject} → {source.module}"
        return source.subject


class CompactFormatter:
    """Compact formatting with minimal headers"""
    
    @staticmethod
    def format_source(source: SourceDocument, index: int) -> str:
        header = f"[{index}] {source.file_name} (p.{source.page_number})"
        return f"{header}\n{source.text}"


class PlainFormatter:
    """Plain text, no headers"""
    
    @staticmethod
    def format_source(source: SourceDocument, index: int) -> str:
        return source.text


class NumberedFormatter:
    """Numbered citations for cloud LLMs"""
    
    @staticmethod
    def format_source(source: SourceDocument, index: int) -> str:
        citation = f"[Source {index}: {source.file_name}, Page {source.page_number}]"
        return f"{citation}\n{source.text}"


class ContextAssembler:
    """Assembles context from search results for LLM prompts"""
    
    # Strategy registry
    _FORMATTERS = {
        FormattingStrategy.DETAILED: DetailedFormatter(),
        FormattingStrategy.COMPACT: CompactFormatter(),
        FormattingStrategy.PLAIN: PlainFormatter(),
        FormattingStrategy.NUMBERED: NumberedFormatter(),
    }
    
    def __init__(self, config: Optional[ContextConfig] = None):
        """
        Initialize context assembler with configuration.
        
        Args:
            config: Optional configuration, uses defaults if None
        """
        self.config = config or ContextConfig()
        self._formatter = self._FORMATTERS[self.config.strategy]
    
    def assemble(
        self, 
        sources: List[SourceDocument],
        max_sources: Optional[int] = None,
        max_chars_per_source: Optional[int] = None
    ) -> str:
        """
        Assemble multiple sources into a formatted context string.
        
        Args:
            sources: List of SourceDocument objects
            max_sources: Override config max_sources
            max_chars_per_source: Override config max_chars_per_source
            
        Returns:
            Formatted context string ready for LLM
        """
        if not sources:
            logger.warning("No sources provided for context assembly")
            return "No relevant context available."
        
        # Apply limits
        max_sources = max_sources or self.config.max_sources
        max_chars = max_chars_per_source or self.config.max_chars_per_source
        
        limited_sources = sources[:max_sources]
        truncated_sources = self._truncate_sources(limited_sources, max_chars)
        
        # Format each source
        formatted_parts = []
        for i, source in enumerate(truncated_sources, start=1):
            try:
                formatted = self._formatter.format_source(source, i)
                formatted_parts.append(formatted)
            except Exception as e:
                logger.error(f"Failed to format source {i}: {e}", exc_info=True)
                # Include fallback representation
                formatted_parts.append(f"[Source {i}: Error formatting - {source.file_name}]")
        
        context = self.config.separator.join(formatted_parts)
        
        logger.debug(
            f"Assembled context: {len(truncated_sources)} sources, "
            f"{len(context)} chars, strategy={self.config.strategy.value}"
        )
        
        return context
    
    def _truncate_sources(
        self, 
        sources: List[SourceDocument], 
        max_chars: int
    ) -> List[SourceDocument]:
        """
        Intelligently truncate source texts to max_chars.
        Tries to break at sentence boundaries when possible.
        """
        truncated = []
        
        for source in sources:
            if len(source.text) <= max_chars:
                truncated.append(source)
            else:
                # Try to truncate at sentence boundary
                truncated_text = self._smart_truncate(source.text, max_chars)
                
                # Create new source with truncated text
                truncated_source = SourceDocument(
                    text=truncated_text,
                    file_name=source.file_name,
                    file_path=source.file_path,
                    page_number=source.page_number,
                    subject=source.subject,
                    module=source.module,
                    chunk_number=source.chunk_number,
                    score=source.score
                )
                truncated.append(truncated_source)
        
        return truncated
    
    def _smart_truncate(self, text: str, max_chars: int) -> str:
        """
        Truncate text at sentence boundary when possible.
        Falls back to word boundary, then hard truncation.
        """
        if len(text) <= max_chars:
            return text
        
        # Try sentence boundary (. ! ?)
        truncate_point = max_chars - len(self.config.truncation_suffix)
        last_sentence = max(
            text.rfind('. ', 0, truncate_point),
            text.rfind('! ', 0, truncate_point),
            text.rfind('? ', 0, truncate_point)
        )
        
        if last_sentence > max_chars * 0.7:  # At least 70% of desired length
            return text[:last_sentence + 1].rstrip() + self.config.truncation_suffix
        
        # Try word boundary
        last_space = text.rfind(' ', 0, truncate_point)
        if last_space > 0:
            return text[:last_space].rstrip() + self.config.truncation_suffix
        
        # Hard truncation as last resort
        return text[:truncate_point].rstrip() + self.config.truncation_suffix
    
    @classmethod
    def from_search_results(
        cls,
        search_results: SearchResults,
        config: Optional[ContextConfig] = None
    ) -> str:
        """
        Convenience method to assemble context directly from SearchResults.
        
        Args:
            search_results: SearchResults object from RAG
            config: Optional configuration
            
        Returns:
            Formatted context string
        """
        assembler = cls(config)
        sources = search_results.to_source_documents()
        return assembler.assemble(sources)
    
    @staticmethod
    def format_sources_summary(
        sources: List[SourceDocument], 
        max_snippet_length: int = 150,
        include_scores: bool = True
    ) -> str:
        """
        Format a human-readable summary of sources (for display/logging).
        
        Args:
            sources: List of SourceDocument objects
            max_snippet_length: Max characters to show from each source
            include_scores: Whether to show relevance scores
            
        Returns:
            Formatted summary string with emoji indicators
        """
        if not sources:
            return "❌ No results found."
        
        # Calculate statistics
        avg_score = sum(s.score for s in sources if s.score) / len(sources) if sources else 0
        
        lines = [
            f"🔍 Found {len(sources)} relevant sections "
            f"(avg relevance: {avg_score:.2%})" if include_scores else 
            f"🔍 Found {len(sources)} relevant sections:"
        ]
        
        for i, source in enumerate(sources, start=1):
            subject = source.subject or "Unknown"
            module = source.module or "General"
            
            # Smart snippet with ellipsis
            snippet = source.text[:max_snippet_length].replace("\n", " ").strip()
            if len(source.text) > max_snippet_length:
                snippet += "..."
            
            # Relevance indicator
            score_indicator = ""
            if include_scores and source.score:
                if source.score > 0.8:
                    score_indicator = "🟢"
                elif source.score > 0.6:
                    score_indicator = "🟡"
                else:
                    score_indicator = "🔴"
                score_indicator += f" {source.score:.1%}"
            
            lines.append(
                f"\n{i}. {subject} → {module} | {source.file_name} (Page {source.page_number})"
                f"{' ' + score_indicator if score_indicator else ''}\n"
                f"   {snippet}"
            )
        
        return "\n".join(lines)


# Backwards compatibility helpers
def format_source_header(source: SourceDocument, index: int) -> str:
    """Legacy helper - use DetailedFormatter.format_source instead"""
    return DetailedFormatter.format_source(source, index).split('\n')[0]


def assemble_context(
    sources: List[SourceDocument], 
    include_headers: bool = True
) -> str:
    """Legacy helper - use ContextAssembler.assemble instead"""
    config = ContextConfig(
        strategy=FormattingStrategy.DETAILED if include_headers else FormattingStrategy.PLAIN
    )
    assembler = ContextAssembler(config)
    return assembler.assemble(sources)