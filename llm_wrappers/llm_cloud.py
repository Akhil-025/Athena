# /llm_wrappers/llm_cloud.py
import os, logging, time
from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except Exception:
    genai = None
    logger.debug("google.generativeai not available; cloud disabled")

class CloudLLM:
    def __init__(self, api_key: str, model: str = "gemini-1.5-pro", max_output_tokens: int = 512):
        if genai is None:
            raise RuntimeError("google.generativeai not installed. Install with: pip install google-generativeai")
        genai.configure(api_key=api_key)
        self.model = model
        self.max_output_tokens = max_output_tokens

    def generate(self, prompt: str, timeout: int = 30):
        start = time.time()
        try:
            # Use the models.generate API - adapt fields to SDK version you have
            res = genai.models.generate(model=self.model, prompt=prompt, max_output_tokens=self.max_output_tokens, timeout=timeout)
            text = getattr(res, "output_text", None) or (res.get("output_text") if isinstance(res, dict) else str(res))
            duration = time.time() - start
            logger.info("CloudLLM.generate finished in %.2fs", duration)
            return {"text": text, "meta": {"duration": duration}}
        except Exception as e:
            logger.exception("Cloud LLM error")
            return {"text": f"Error: cloud LLM failed: {e}", "meta": {}}