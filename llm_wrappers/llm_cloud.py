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
        self.model_name = model
        self.max_output_tokens = max_output_tokens
        self.retries = retries
        
        # Initialize the GenerativeModel instance
        self.model = genai.GenerativeModel(
            model_name=model,
            generation_config={
                "max_output_tokens": max_output_tokens,
                "temperature": 0.15
            }
        )
        
        logger.info(f"CloudLLM initialized: {model}")

    # -----------------------------------------------------------
    # Extract text from ANY Gemini SDK response (all versions)
    # -----------------------------------------------------------
    def _extract_text(self, r: Any) -> str:
        if r is None:
            return ""

        # v0.3+ (current SDK version)
        if hasattr(r, "text"):
            try:
                return r.text or ""
            except Exception:
                pass

        # Try parts
        if hasattr(r, "parts"):
            try:
                return ''.join(part.text for part in r.parts if hasattr(part, 'text'))
            except Exception:
                pass
        
        # Try candidates
        if hasattr(r, "candidates"):
            try:
                if r.candidates and len(r.candidates) > 0:
                    candidate = r.candidates[0]
                    if hasattr(candidate, "content"):
                        content = candidate.content
                        if hasattr(content, "parts"):
                            return ''.join(part.text for part in content.parts if hasattr(part, 'text'))
            except Exception:
                pass

        # Dict-like fallback
        if isinstance(r, dict):
            if "text" in r:
                return r["text"]
            if "output_text" in r:
                return r["output_text"]
            if "candidates" in r:
                cands = r["candidates"]
                if cands and isinstance(cands, list):
                    c0 = cands[0]
                    if isinstance(c0, dict):
                        if "content" in c0:
                            return str(c0["content"])
                        if "text" in c0:
                            return c0["text"]

        # Last fallback
        return str(r)

    # -----------------------------------------------------------
    # Generate response
    # -----------------------------------------------------------
    def generate(self, prompt: str, timeout: int = 60) -> Dict[str, Any]:
        """
        Generate a response using Gemini API.
        
        Args:
            prompt: The prompt text
            timeout: Timeout in seconds (not strictly enforced by SDK)
            
        Returns:
            Dict with keys: text, error, meta
        """
        if genai is None:
            return {"text": "", "error": "Gemini SDK missing", "meta": {}}

        start = time.time()
        last_err = None

        for attempt in range(1, self.retries + 1):
            try:
                # Use the correct SDK method
                response = self.model.generate_content(prompt)
                
                # Extract text from response
                text = self._extract_text(response)
                
                return {
                    "text": text,
                    "error": None,
                    "meta": {
                        "duration": time.time() - start,
                        "attempt": attempt,
                        "model": self.model_name
                    }
                }

            except Exception as e:
                last_err = str(e)
                logger.warning(f"CloudLLM attempt {attempt} failed: {e}")
                
                if attempt < self.retries:
                    wait_time = min(2 ** attempt, 8)
                    time.sleep(wait_time)
                continue

        # All retries failed
        logger.error(f"CloudLLM failed after {self.retries} attempts: {last_err}")
        return {
            "text": "",
            "error": last_err,
            "meta": {
                "duration": time.time() - start,
                "attempt": self.retries
            }
        }