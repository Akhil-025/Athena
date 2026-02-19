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
    
    LOCAL_SYSTEM_PROMPT = (
        "You are a precise academic assistant. Answer ONLY using the provided context excerpts. "
        "If the context does not contain enough information to answer, say exactly: "
        "'The provided documents do not cover this topic.' "
        "Do not add outside knowledge. Be specific and cite the source name."
    )

    CLOUD_SYSTEM_PROMPT = (
        "You are Athena, an expert academic study assistant. "
        "Answer the question using ONLY the context provided below. "
        "Structure your answer clearly. If derivations or steps are needed, show them. "
        "If the answer is not in the context, say so explicitly — do not guess. "
        "Always mention which source (file name, page) your answer comes from."
    )

    @staticmethod
    def build_local_prompt(question: str, context: str) -> str:
        return (
            f"{PromptBuilder.LOCAL_SYSTEM_PROMPT}\n\n"
            f"=== CONTEXT FROM YOUR DOCUMENTS ===\n{context}\n"
            f"=== END CONTEXT ===\n\n"
            f"Question: {question}\n\n"
            f"Answer (based only on the above context):"
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