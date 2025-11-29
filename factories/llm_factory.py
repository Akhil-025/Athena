"""
LLM Factory - Handles initialization of different LLM providers.
Uses Factory Pattern to encapsulate LLM creation logic.
"""
import os
import logging
from typing import Optional, Tuple
from config import get_config

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating LLM instances"""
    
    @staticmethod
    def create_local_llm():
        """
        Create local LLM instance based on config.
        
        Returns:
            LLM instance or None if initialization fails
        """
        config = get_config()
        engine = config.local_model_engine.lower()
        
        if engine == "ollama":
            return LLMFactory._create_ollama_llm()
        elif engine == "llama-cpp":
            return LLMFactory._create_llamacpp_llm()
        else:
            logger.warning(f"Unknown local LLM engine: {engine}")
            return None
    
    @staticmethod
    def _create_ollama_llm():
        """Create Ollama LLM instance"""
        try:
            from llm_wrappers.llm_ollama import OllamaLLM
        except ImportError:
            logger.warning("Ollama wrapper not found (llm_wrappers/llm_ollama.py)")
            return None
        
        config = get_config()
        
        try:
            llm = OllamaLLM(model=config.ollama_model)
            logger.info(f"✅ Initialized Ollama: {config.ollama_model}")
            return llm
        except Exception as e:
            logger.warning(f"Ollama initialization failed: {e}")
            return None
    
    @staticmethod
    def _create_llamacpp_llm():
        """Create llama-cpp LLM instance"""
        from llm_wrappers.llm_local import LocalLLM
        config = get_config()
        
        if not config.local_model_path:
            logger.warning("llama-cpp: model_path not configured")
            return None
        
        try:
            llm = LocalLLM(
                model_path=config.local_model_path,
                max_tokens=config.max_tokens,
                n_ctx=config.n_ctx,
                temperature=config.temperature,
            )
            logger.info(f"✅ Initialized llama-cpp: {config.local_model_path}")
            return llm
        except Exception as e:
            logger.warning(f"llama-cpp initialization failed: {e}")
            return None
    
    @staticmethod
    def create_cloud_llm(api_key: Optional[str] = None):
        """
        Create cloud LLM instance.
        
        Args:
            api_key: Optional API key (will use env var if not provided)
            
        Returns:
            CloudLLM instance or None if initialization fails
        """
        from llm_wrappers.llm_cloud import CloudLLM
        config = get_config()
        
        # Get API key from parameter or environment
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        
        if not api_key:
            logger.warning("GOOGLE_API_KEY not set; cloud LLM disabled")
            return None
        
        try:
            llm = CloudLLM(
                api_key=api_key,
                model=config.cloud_model,
                max_output_tokens=config.max_tokens
            )
            logger.info(f"✅ Initialized Cloud LLM: {config.cloud_model}")
            return llm
        except Exception as e:
            logger.warning(f"Cloud LLM initialization failed: {e}")
            return None
    
    @staticmethod
    def create_llms(api_key: Optional[str] = None) -> Tuple[Optional[any], Optional[any]]:
        """
        Create both local and cloud LLMs.
        
        Args:
            api_key: Optional API key for cloud LLM
            
        Returns:
            Tuple of (local_llm, cloud_llm) - either can be None
        """
        local_llm = LLMFactory.create_local_llm()
        cloud_llm = LLMFactory.create_cloud_llm(api_key)
        
        # Log summary
        if local_llm and cloud_llm:
            logger.info("🎉 Both local and cloud LLMs available")
        elif local_llm:
            logger.info("💻 Only local LLM available")
        elif cloud_llm:
            logger.info("☁️ Only cloud LLM available")
        else:
            logger.warning("⚠️ No LLMs available!")
        
        return local_llm, cloud_llm