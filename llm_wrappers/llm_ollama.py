# llm_wrappers/llm_ollama.py

import subprocess
import shutil
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class OllamaLLM:
    """
    Universal Ollama wrapper.
    Supports:
    - `ollama run model`  (preferred)
    - fallback: `ollama generate model --prompt`
    - Uniform return shape
    """

    def __init__(self, model: str = "mistral"):
        self.model = model

        if shutil.which("ollama") is None:
            raise RuntimeError("Ollama CLI not installed or not on PATH.")

    def _run_ollama(self, prompt: str, timeout: int):
        """Primary method: ollama run"""
        p = subprocess.Popen(
            ["ollama", "run", self.model],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        out, err = p.communicate(prompt, timeout=timeout)
        return p.returncode, out.strip(), err.strip()

    def _generate_ollama(self, prompt: str, timeout: int):
        """Fallback: ollama generate"""
        p = subprocess.run(
            ["ollama", "generate", self.model, "--prompt", prompt],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=timeout
        )
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()

    # -----------------------------------------------------
    # Generate
    # -----------------------------------------------------
    def generate(self, prompt: str, timeout: int = 120) -> Dict[str, Any]:
        if not isinstance(prompt, str):
            prompt = str(prompt)

        prompt = prompt.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")

        # ---- TRY RUN FIRST ----
        try:
            rc, out, err = self._run_ollama(prompt, timeout)
            if rc == 0:
                return {"text": out, "error": None, "meta": {"rc": rc}}
            else:
                logger.warning(f"Ollama run failed: {err}")
        except subprocess.TimeoutExpired:
            logger.error("❌ Ollama run timed out")
            return {"text": "", "error": "Ollama timed out", "meta": {}}
        except Exception as e:
            logger.warning(f"Ollama run crashed: {e}")

        # ---- FALLBACK: ollama generate ----
        try:
            rc, out, err = self._generate_ollama(prompt, timeout)
            if rc == 0:
                return {"text": out, "error": None, "meta": {"rc": rc}}
            else:
                return {"text": "", "error": err, "meta": {"rc": rc}}
        except Exception as e:
            logger.exception("Ollama generate crashed")
            return {"text": "", "error": str(e), "meta": {}}
