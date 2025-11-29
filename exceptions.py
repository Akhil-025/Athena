"""
Custom exceptions for Athena RAG system.
Provides structured error handling across all modules.
"""


class AthenaError(Exception):
    """Base exception for all Athena errors"""
    pass


class ConfigError(AthenaError):
    """Configuration-related errors"""
    pass


class RAGError(AthenaError):
    """RAG system errors (search, indexing, etc.)"""
    pass


class LLMError(AthenaError):
    """LLM generation errors"""
    pass


class QueryError(AthenaError):
    """Query execution errors"""
    pass


class DocumentProcessingError(AthenaError):
    """PDF processing and document handling errors"""
    pass


class CacheError(AthenaError):
    """Caching-related errors"""
    pass