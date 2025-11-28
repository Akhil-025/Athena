"""
Default configuration values for Athena RAG system.
These are fallbacks when values aren't specified in config.json.
"""

# Search defaults
DEFAULT_SEARCH_RESULTS = 8
DEFAULT_SEMANTIC_WEIGHT = 0.7

# PDF Processing defaults
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 150

# Embedding defaults
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_EMBED_BATCH_SIZE = 32

# LLM defaults
DEFAULT_LLM_TIMEOUT = 240
DEFAULT_MAX_TOKENS = 2048
DEFAULT_N_CTX = 8192
DEFAULT_TEMPERATURE = 0.15

# Server defaults
DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 5000
DEFAULT_SERVER_DEBUG = False

# Cloud sanitization defaults
DEFAULT_MAX_CHUNK_CHARS_CLOUD = 1500
DEFAULT_MAX_CHUNKS_CLOUD = 2

# Feature flags
DEFAULT_ENABLE_BM25 = True
DEFAULT_RELOAD_ON_START = False
DEFAULT_SHOW_SOURCES = True
DEFAULT_USE_CLOUD = False