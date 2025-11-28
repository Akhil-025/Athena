# config/__init__.py

"""
Centralized configuration management for Athena RAG system.
Loads config.json once and provides type-safe access to all settings.
"""
import json
import os
from pathlib import Path
from typing import Any, Optional
import logging

from . import manager  # manager.py contains all default constants
from . import paths

logger = logging.getLogger(__name__)


class ConfigManager:
    """Singleton configuration manager"""

    _instance: Optional['ConfigManager'] = None
    _config: dict = {}

    def __init__(self):
        if ConfigManager._instance is not None:
            raise RuntimeError("Use ConfigManager.get_instance() instead")
        self._load_config()

    @classmethod
    def get_instance(cls) -> 'ConfigManager':
        """Get or create the singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_config(self):
        """Load configuration from config.json with validation"""
        try:
            if not paths.CONFIG_FILE.exists():
                logger.warning(f"Config file not found: {paths.CONFIG_FILE}")
                logger.warning("Using default configuration values")
                self._config = {}
                return

            with open(paths.CONFIG_FILE, 'r', encoding='utf-8') as f:
                self._config = json.load(f)

            logger.info(f"✅ Configuration loaded from {paths.CONFIG_FILE}")
            self._validate_config()

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise ValueError(f"Failed to parse config.json: {e}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    def _validate_config(self):
        """Validate critical configuration values"""
        if self.use_cloud_by_default and not os.getenv("GOOGLE_API_KEY"):
            logger.warning("Cloud mode enabled but GOOGLE_API_KEY not set")

        if self.local_model_path:
            model_path = Path(self.local_model_path)
            if not model_path.exists():
                logger.warning(f"Local model path not found: {model_path}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get raw config value with optional default"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    # === Search Configuration ===
    @property
    def default_search_results(self) -> int:
        return self.get('default_search_results', manager.DEFAULT_SEARCH_RESULTS)

    @property
    def semantic_weight(self) -> float:
        return self.get('semantic_weight', manager.DEFAULT_SEMANTIC_WEIGHT)

    # === PDF Processing ===
    @property
    def chunk_size(self) -> int:
        return self.get('chunk_size', manager.DEFAULT_CHUNK_SIZE)

    @property
    def chunk_overlap(self) -> int:
        return self.get('chunk_overlap', manager.DEFAULT_CHUNK_OVERLAP)

    # === Embedding ===
    @property
    def embedding_model(self) -> str:
        return self.get('embedding_model', manager.DEFAULT_EMBEDDING_MODEL)

    @property
    def embed_batch_size(self) -> int:
        return self.get('embed_batch_size', manager.DEFAULT_EMBED_BATCH_SIZE)

    # === LLM Configuration ===
    @property
    def use_cloud_by_default(self) -> bool:
        return self.get('use_cloud_by_default', manager.DEFAULT_USE_CLOUD)

    @property
    def llm_timeout_seconds(self) -> int:
        return self.get('llm_timeout_seconds', manager.DEFAULT_LLM_TIMEOUT)

    @property
    def max_tokens(self) -> int:
        return self.get('local_model.max_tokens', manager.DEFAULT_MAX_TOKENS)

    @property
    def n_ctx(self) -> int:
        return self.get('local_model.n_ctx', manager.DEFAULT_N_CTX)

    @property
    def temperature(self) -> float:
        return self.get('local_model.temperature', manager.DEFAULT_TEMPERATURE)

    @property
    def local_model_engine(self) -> str:
        return self.get('local_model.default_engine', 'ollama')

    @property
    def ollama_model(self) -> str:
        return self.get('local_model.ollama_model', 'mistral')

    @property
    def local_model_path(self) -> Optional[str]:
        return self.get('local_model.model_path') or self.get('local_model.local_model_path')

    @property
    def cloud_model(self) -> str:
        return self.get('cloud_model', 'gemini-1.5-pro')

    # === Cloud Sanitization ===
    @property
    def max_chunk_chars_cloud(self) -> int:
        return self.get('sanitization.max_chunk_chars_sent_to_cloud',
                        manager.DEFAULT_MAX_CHUNK_CHARS_CLOUD)

    @property
    def max_chunks_cloud(self) -> int:
        return self.get('sanitization.max_chunks_sent_to_cloud',
                        manager.DEFAULT_MAX_CHUNKS_CLOUD)

    @property
    def remove_pii(self) -> bool:
        return self.get('sanitization.remove_pii', True)

    # === Database ===
    @property
    def chroma_persist_dir(self) -> str:
        return self.get('chroma_persist_dir', str(paths.CHROMA_DB_DIR))

    @property
    def enable_bm25(self) -> bool:
        return self.get('enable_bm25', manager.DEFAULT_ENABLE_BM25)

    @property
    def reload_on_start(self) -> bool:
        return self.get('reload_on_start', manager.DEFAULT_RELOAD_ON_START)

    # === Server Configuration ===
    @property
    def server_host(self) -> str:
        return self.get('server.host', manager.DEFAULT_SERVER_HOST)

    @property
    def server_port(self) -> int:
        return self.get('server.port', manager.DEFAULT_SERVER_PORT)

    @property
    def server_debug(self) -> bool:
        return self.get('server.debug', manager.DEFAULT_SERVER_DEBUG)

    @property
    def api_key_for_admin(self) -> Optional[str]:
        return self.get('server.api_key_for_admin') or os.getenv('ATHENA_ADMIN_KEY')

    # === Feature Flags ===
    @property
    def show_sources_on_answer(self) -> bool:
        return self.get('show_sources_on_answer', manager.DEFAULT_SHOW_SOURCES)

    # === Paths (delegated to paths module) ===
    @property
    def data_dir(self) -> Path:
        return paths.DATA_DIR

    @property
    def cache_dir(self) -> Path:
        return paths.CACHE_DIR

    @property
    def logs_dir(self) -> Path:
        return paths.LOGS_DIR


# Convenience function
def get_config() -> ConfigManager:
    """Get the global config instance"""
    return ConfigManager.get_instance()
