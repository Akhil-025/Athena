# /llm_wrappers/llm_local.py
import os
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from llama_cpp import Llama
except Exception as e:
    Llama = None
    logger.debug("llama-cpp-python not available: %s", e)

class LocalLLM:
    def __init__(self, model_path: str, max_tokens: int = 512, n_ctx: int = 2048, temperature: float = 0.0):
        if Llama is None:
            raise RuntimeError("llama-cpp-python not installed. Install with: pip install llama-cpp-python")
        model_path = str(Path(model_path).expanduser())
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Local model not found at {model_path}")
        self.model = Llama(model_path=model_path, n_ctx=n_ctx)
        self.max_tokens = max_tokens
        self.temperature = temperature

    def generate(self, prompt: str, timeout: int = 60):
        start = time.time()
        try:
            resp = self.model.create(prompt=prompt, max_tokens=self.max_tokens, temperature=self.temperature, timeout=timeout)
            text = (resp.get("choices") or [{}])[0].get("text", "") if isinstance(resp, dict) else str(resp)
            duration = time.time() - start
            logger.info("LocalLLM.generate finished in %.2fs", duration)
            return {"text": text, "meta": {"duration": duration}}
        except Exception as e:
            logger.exception("Local LLM generation failed")
            return {"text": f"Error: local LLM failed: {e}", "meta": {}}