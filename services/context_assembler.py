"""
Context assembly service - formats RAG search results into context strings.
Consolidates all context formatting logic in one place.
"""
from typing import List
from models import SourceDocument, SearchResults


class ContextAssembler:
    """Assembles context from search results for LLM prompts"""
    
    @staticmethod
    def format_source_header(source: SourceDocument, index: int) -> str:
        """
        Format header for a single source excerpt.
        
        Example: "--- Excerpt 1: document.pdf | CAD → 2D_Transformations (Page 5) ---"
        """
        subject_module = ""
        if source.subject:
            subject_module = f"{source.subject}"
            if source.module:
                subject_module += f" → {source.module}"
        
        return (
            f"--- Excerpt {index}: {source.file_name} "
            f"| {subject_module or 'General'} "
            f"(Page {source.page_number}) ---"
        )
    
    @staticmethod
    def assemble_context(sources: List[SourceDocument], 
                        include_headers: bool = True) -> str:
        """
        Assemble multiple sources into a formatted context string.
        
        Args:
            sources: List of SourceDocument objects
            include_headers: Whether to include source headers
            
        Returns:
            Formatted context string ready for LLM
        """
        if not sources:
            return "No relevant context available."
        
        context_parts = []
        
        for i, source in enumerate(sources, start=1):
            if include_headers:
                header = ContextAssembler.format_source_header(source, i)
                context_parts.append(f"{header}\n{source.text}")
            else:
                context_parts.append(source.text)
        
        return "\n\n".join(context_parts)
    
    @staticmethod
    def assemble_from_search_results(search_results: SearchResults) -> str:
        """
        Convenience method to assemble context directly from SearchResults.
        
        Args:
            search_results: SearchResults object from RAG
            
        Returns:
            Formatted context string
        """
        sources = search_results.to_source_documents()
        return ContextAssembler.assemble_context(sources)
    
    @staticmethod
    def format_sources_summary(sources: List[SourceDocument], 
                              max_snippet_length: int = 200) -> str:
        """
        Format a human-readable summary of sources (for display/logging).
        
        Args:
            sources: List of SourceDocument objects
            max_snippet_length: Max characters to show from each source
            
        Returns:
            Formatted summary string
        """
        if not sources:
            return "❌ No results found."
        
        lines = [f"🔍 Found {len(sources)} relevant sections:"]
        
        for i, source in enumerate(sources, start=1):
            subject = source.subject or "Unknown"
            module = source.module or "General"
            snippet = source.text[:max_snippet_length].replace("\n", " ")
            
            lines.append(
                f"{i}. {subject} → {module} | {source.file_name} (Page {source.page_number})\n"
                f"   {snippet}{'...' if len(source.text) > max_snippet_length else ''}"
            )
        
        return "\n\n".join(lines)