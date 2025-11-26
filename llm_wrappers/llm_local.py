# llm_wrappers/llm_local.py

import os
import time
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

try:
    from llama_cpp import Llama
except Exception:
    Llama = None
    logger.debug("⚠️ llama-cpp-python not available")


class LocalLLM:
    """
    llama.cpp wrapper that supports:
    - consistent "text/error/meta" return
    - robust extraction across all llama-cpp versions
    """

    def __init__(self, model_path: str, max_tokens: int = 512, n_ctx: int = 4096, temperature: float = 0.0):
        if Llama is None:
            raise RuntimeError("llama-cpp-python not installed.")

        model_path = Path(model_path).expanduser()
        if not model_path.exists():
            raise FileNotFoundError(f"Local model not found: {model_path}")

        self.model = Llama(model_path=str(model_path), n_ctx=n_ctx)
        self.max_tokens = max_tokens
        self.temperature = temperature

    # -----------------------------------------------
    # Extract text from all llama-cpp response shapes
    # -----------------------------------------------
    def _extract(self, resp):
        try:
            if isinstance(resp, dict):
                if "choices" in resp and resp["choices"]:
                    c0 = resp["choices"][0]
                    if isinstance(c0, dict) and "text" in c0:
                        return c0["text"]
                if "text" in resp:
                    return resp["text"]
            return str(resp)
        except:
            return str(resp)

    # -----------------------------------------------
    # Generate
    # -----------------------------------------------
    def generate(self, prompt: str, timeout: int = 60) -> Dict[str, Any]:
        start = time.time()

        try:
            out = self.model.create(
                prompt=prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            text = self._extract(out) or ""

            return {
                "text": text,
                "error": None,
                "meta": {"duration": time.time() - start}
            }

        except Exception as e:
            logger.exception("Local LLM crashed")
            return {"text": "", "error": str(e), "meta": {}}
