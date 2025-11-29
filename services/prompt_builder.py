"""
Prompt building service - handles all LLM prompt construction.
Consolidates prompt logic for both local and cloud LLMs.
"""
from typing import List
from models import SourceDocument
from services.context_assembler import ContextAssembler
from config import get_config


class PromptBuilder:
    """Builds prompts for different LLM types and use cases"""
    
    # System personas for different LLM types
    LOCAL_SYSTEM_PROMPT = (
        "You are an expert engineering tutor. Use the provided context "
        "to answer the question accurately and concisely. If the context "
        "doesn't contain enough information, say so."
    )
    
    CLOUD_SYSTEM_PROMPT = (
        "You are Athena — an expert AI study partner. "
        "Answer the question using ONLY the provided context. "
        "Be clear, accurate, and helpful."
    )
    
    @staticmethod
    def build_local_prompt(question: str, context: str) -> str:
        """
        Build prompt for local LLM (Ollama, llama-cpp).
        Local models typically prefer simpler, more direct prompts.
        
        Args:
            question: The user's question
            context: Formatted context from search results
            
        Returns:
            Complete prompt string
        """
        return (
            f"{PromptBuilder.LOCAL_SYSTEM_PROMPT}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"QUESTION: {question}\n\n"
            f"ANSWER:"
        )
    
    @staticmethod
    def build_cloud_prompt(question: str, sources: List[SourceDocument]) -> str:
        """
        Build prompt for cloud LLM (Gemini, GPT, etc.).
        Cloud models can handle more structured, detailed prompts.
        
        Args:
            question: The user's question
            sources: List of sanitized SourceDocument objects
            
        Returns:
            Complete prompt string
        """
        # Format sources with numbered citations
        context_parts = []
        for i, source in enumerate(sources, start=1):
            context_parts.append(
                f"Source {i} ({source.file_name}):\n{source.text}"
            )
        
        context = "\n\n".join(context_parts)
        
        return (
            f"{PromptBuilder.CLOUD_SYSTEM_PROMPT}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"QUESTION: {question}\n\n"
            f"ANSWER:"
        )
    
    @staticmethod
    def build_prompt(question: str, 
                    sources: List[SourceDocument],
                    use_cloud: bool = False) -> str:
        """
        Build appropriate prompt based on LLM type.
        
        Args:
            question: The user's question
            sources: List of SourceDocument objects
            use_cloud: Whether using cloud or local LLM
            
        Returns:
            Complete prompt string
        """
        if use_cloud:
            # Cloud models get sanitized sources
            config = get_config()
            max_sources = config.max_chunks_cloud
            max_chars = config.max_chunk_chars_cloud
            
            # Truncate sources for cloud
            sanitized_sources = []
            for source in sources[:max_sources]:
                sanitized = SourceDocument(
                    text=source.text[:max_chars],
                    file_name=source.file_name,
                    file_path=source.file_path,
                    page_number=source.page_number,
                    subject=source.subject,
                    module=source.module,
                    score=source.score
                )
                sanitized_sources.append(sanitized)
            
            return PromptBuilder.build_cloud_prompt(question, sanitized_sources)
        else:
            # Local models get full context assembled
            context = ContextAssembler.assemble_context(sources)
            return PromptBuilder.build_local_prompt(question, context)
    
    @staticmethod
    def build_context_only(sources: List[SourceDocument]) -> str:
        """
        Build just the context portion (useful for caching/debugging).
        
        Args:
            sources: List of SourceDocument objects
            
        Returns:
            Formatted context string
        """
        return ContextAssembler.assemble_context(sources)