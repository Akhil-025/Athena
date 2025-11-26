# llm_wrappers/llm_cloud.py

import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except Exception:
    genai = None
    logger.debug("⚠️ google.generativeai not available; CloudLLM disabled")


class CloudLLM:
    """
    Stable, retry-capable wrapper for Gemini 1.5.
    Returns uniform structure:
        {"text": str, "error": Optional[str], "meta": dict}
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-1.5-pro",
        max_output_tokens: int = 512,
        retries: int = 3
    ):
        if genai is None:
            raise RuntimeError("google-generativeai not installed. pip install google-generativeai")

        if not api_key:
            raise RuntimeError("CloudLLM needs an API key.")

        genai.configure(api_key=api_key)
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.retries = retries

    # -----------------------------------------------------------
    # Extract text from ANY Gemini SDK response (all versions)
    # -----------------------------------------------------------
    def _extract_text(self, r: Any) -> str:
        if r is None:
            return ""

        # v0.3 onwards
        if hasattr(r, "text"):
            return r.text or ""

        if hasattr(r, "output_text"):
            return r.output_text or ""

        # Dict-like
        if isinstance(r, dict):

            if "output_text" in r:
                return r["output_text"]

            if "candidates" in r:
                cands = r["candidates"]
                if cands and isinstance(cands, list):
                    c0 = cands[0]
                    for k in ("content", "text", "output_text"):
                        if isinstance(c0, dict) and k in c0:
                            return c0[k] or ""
                    return str(c0)

            if "content" in r:
                return r["content"]

        # Last fallback
        return str(r)

    # -----------------------------------------------------------
    # Generate response
    # -----------------------------------------------------------
    def generate(self, prompt: str, timeout: int = 60) -> Dict[str, Any]:
        if genai is None:
            return {"text": "", "error": "Gemini SDK missing", "meta": {}}

        start = time.time()
        last_err = None

        for attempt in range(1, self.retries + 1):
            try:
                if hasattr(genai.models, "generate"):
                    res = genai.models.generate(
                        model=self.model,
                        prompt=prompt,
                        max_output_tokens=self.max_output_tokens,
                        timeout=timeout
                    )
                else:
                    # legacy fallback
                    res = genai.generate_text(
                        model=self.model,
                        prompt=prompt,
                        max_output_tokens=self.max_output_tokens
                    )

                text = self._extract_text(res)
                return {
                    "text": text,
                    "error": None,
                    "meta": {
                        "duration": time.time() - start,
                        "attempt": attempt
                    }
                }

            except Exception as e:
                last_err = str(e)
                logger.warning(f"CloudLLM attempt {attempt} failed: {e}")
                time.sleep(min(2 ** attempt, 8))
                continue

        # All retries failed
        return {
            "text": "",
            "error": last_err,
            "meta": {
                "duration": time.time() - start,
                "attempt": self.retries
            }
        }
