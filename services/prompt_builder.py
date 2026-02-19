"""
Prompt building service - handles all LLM prompt construction.

Features:
- Template-based prompts with variable substitution
- Multi-modal prompt strategies (chat, instruct, completion)
- Token budget awareness
- Dynamic prompt optimization
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

from models import SourceDocument
from services.context_assembler import ContextAssembler, ContextConfig, FormattingStrategy
from config import get_config


logger = logging.getLogger(__name__)


class PromptMode(Enum):
    """Prompt modes for different LLM types"""
    LOCAL_INSTRUCT = "local_instruct"      # Local instruct-tuned models
    LOCAL_CHAT = "local_chat"              # Local chat models
    CLOUD_ADVANCED = "cloud_advanced"      # GPT-4, Claude, etc.
    CLOUD_BASIC = "cloud_basic"            # Gemini, GPT-3.5


@dataclass
class PromptTemplate:
    """Template for building prompts with variable substitution"""
    system_prompt: str
    user_template: str
    context_prefix: str = "CONTEXT FROM YOUR DOCUMENTS:"
    context_suffix: str = "END OF CONTEXT"
    answer_prefix: str = "ANSWER:"
    
    def render(
        self,
        question: str,
        context: str,
        **kwargs: Any
    ) -> str:
        """
        Render the template with provided variables.
        
        Args:
            question: User's question
            context: Assembled context
            **kwargs: Additional variables for template substitution
        """
        variables = {
            'question': question,
            'context': context,
            'context_prefix': self.context_prefix,
            'context_suffix': self.context_suffix,
            'answer_prefix': self.answer_prefix,
            **kwargs
        }
        
        prompt_parts = []
        
        if self.system_prompt:
            prompt_parts.append(self.system_prompt.format(**variables))
        
        prompt_parts.append(self.user_template.format(**variables))
        
        return "\n\n".join(prompt_parts)


class PromptTemplateLibrary:
    """Library of pre-defined prompt templates"""
    
    LOCAL_INSTRUCT = PromptTemplate(
        system_prompt=(
            "You are a precise academic assistant. Answer ONLY using the provided context. "
            "If information is missing, state: 'The provided documents do not cover this topic.' "
            "Be specific and cite sources."
        ),
        user_template=(
            "=== {context_prefix} ===\n"
            "{context}\n"
            "=== {context_suffix} ===\n\n"
            "Question: {question}\n\n"
            "{answer_prefix}"
        )
    )
    
    LOCAL_CHAT = PromptTemplate(
        system_prompt=(
            "You are a helpful study assistant. Use only the context provided to answer questions. "
            "If you don't know based on the context, say so clearly."
        ),
        user_template=(
            "Here's the relevant content from the student's documents:\n\n"
            "{context}\n\n"
            "Based on this, please answer: {question}"
        )
    )
    
    CLOUD_ADVANCED = PromptTemplate(
        system_prompt=(
            "You are Athena, an expert academic study assistant with deep knowledge "
            "across multiple subjects. Your role is to provide clear, accurate answers "
            "based STRICTLY on the provided context.\n\n"
            "Guidelines:\n"
            "- Answer using ONLY the provided sources\n"
            "- Structure answers with clear sections if appropriate\n"
            "- Show derivations/steps for mathematical or technical questions\n"
            "- Cite sources explicitly (file name, page number)\n"
            "- If information is insufficient, state this clearly—do not guess\n"
            "- Use markdown formatting for clarity"
        ),
        user_template=(
            "## Context from Student's Documents\n\n"
            "{context}\n\n"
            "## Student's Question\n"
            "{question}\n\n"
            "## Your Answer\n"
            "Please provide a comprehensive answer based solely on the context above:"
        )
    )
    
    CLOUD_BASIC = PromptTemplate(
        system_prompt=(
            "Answer the question using only the provided context. "
            "Cite your sources. If the answer isn't in the context, say so."
        ),
        user_template=(
            "CONTEXT:\n{context}\n\n"
            "QUESTION: {question}\n\n"
            "ANSWER:"
        )
    )
    
    @classmethod
    def get_template(cls, mode: PromptMode) -> PromptTemplate:
        """Get template for specified mode"""
        return {
            PromptMode.LOCAL_INSTRUCT: cls.LOCAL_INSTRUCT,
            PromptMode.LOCAL_CHAT: cls.LOCAL_CHAT,
            PromptMode.CLOUD_ADVANCED: cls.CLOUD_ADVANCED,
            PromptMode.CLOUD_BASIC: cls.CLOUD_BASIC,
        }[mode]


class PromptBuilder:
    """Builds optimized prompts for different LLM types"""
    
    def __init__(
        self,
        mode: Optional[PromptMode] = None,
        template: Optional[PromptTemplate] = None,
        context_config: Optional[ContextConfig] = None
    ):
        """
        Initialize prompt builder.
        
        Args:
            mode: Prompt mode (determines template if template not provided)
            template: Custom template (overrides mode)
            context_config: Context assembly configuration
        """
        if template:
            self.template = template
        elif mode:
            self.template = PromptTemplateLibrary.get_template(mode)
        else:
            # Default to cloud advanced
            self.template = PromptTemplateLibrary.CLOUD_ADVANCED
        
        self.context_config = context_config or ContextConfig()
        self.context_assembler = ContextAssembler(self.context_config)
    
    def build(
        self,
        question: str,
        sources: List[SourceDocument],
        **template_vars: Any
    ) -> str:
        """
        Build complete prompt from question and sources.
        
        Args:
            question: User's question
            sources: List of source documents
            **template_vars: Additional variables for template
            
        Returns:
            Complete prompt string
        """
        if not sources:
            logger.warning("Building prompt with no sources")
            context = "No relevant information found in documents."
        else:
            context = self.context_assembler.assemble(sources)
        
        prompt = self.template.render(
            question=question,
            context=context,
            **template_vars
        )
        
        logger.debug(
            f"Built prompt: {len(prompt)} chars, "
            f"{len(sources)} sources, "
            f"template={self.template.__class__.__name__}"
        )
        
        return prompt
    
    def build_with_token_budget(
        self,
        question: str,
        sources: List[SourceDocument],
        max_tokens: int,
        tokens_per_char: float = 0.25,  # Rough estimate
        **template_vars: Any
    ) -> str:
        """
        Build prompt that fits within token budget.
        Dynamically reduces sources/context to fit.
        
        Args:
            question: User's question
            sources: List of source documents
            max_tokens: Maximum token budget
            tokens_per_char: Estimated tokens per character
            **template_vars: Additional template variables
            
        Returns:
            Prompt that fits within token budget
        """
        # Reserve tokens for template overhead and question
        overhead = len(self.template.system_prompt) + len(question) + 200
        available_chars = int((max_tokens - overhead * tokens_per_char) / tokens_per_char)
        
        if available_chars < 500:
            logger.warning(f"Very tight token budget: {max_tokens} tokens")
            available_chars = 500  # Minimum viable context
        
        # Calculate chars per source
        num_sources = min(len(sources), self.context_config.max_sources)
        chars_per_source = available_chars // num_sources if num_sources > 0 else available_chars
        
        # Build with constraints
        logger.info(
            f"Token budget: {max_tokens} tokens → {num_sources} sources × {chars_per_source} chars"
        )
        
        return self.build(
            question=question,
            sources=sources[:num_sources],
            **template_vars
        )
    
    @classmethod
    def for_local_llm(cls, chat_mode: bool = False) -> 'PromptBuilder':
        """Factory: Create builder optimized for local LLMs"""
        mode = PromptMode.LOCAL_CHAT if chat_mode else PromptMode.LOCAL_INSTRUCT
        config = ContextConfig.for_local_llm()
        return cls(mode=mode, context_config=config)
    
    @classmethod
    def for_cloud_llm(cls, advanced: bool = True) -> 'PromptBuilder':
        """Factory: Create builder optimized for cloud LLMs"""
        mode = PromptMode.CLOUD_ADVANCED if advanced else PromptMode.CLOUD_BASIC
        config = ContextConfig.for_cloud_llm()
        # Use numbered citations for cloud
        config.strategy = FormattingStrategy.NUMBERED
        return cls(mode=mode, context_config=config)


# Backwards compatibility
def build_local_prompt(question: str, context: str) -> str:
    """Legacy function - use PromptBuilder instead"""
    template = PromptTemplateLibrary.LOCAL_INSTRUCT
    return template.render(question=question, context=context)


def build_cloud_prompt(question: str, sources: List[SourceDocument]) -> str:
    """Legacy function - use PromptBuilder instead"""
    builder = PromptBuilder.for_cloud_llm()
    return builder.build(question, sources)