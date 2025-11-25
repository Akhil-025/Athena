# llm_wrappers/llm_ollama.py
import subprocess
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class OllamaLLM:
    """
    Ollama wrapper compatible with a wide range of Ollama versions.
    Sends the prompt via stdin (text mode, UTF-8).
    """

    def __init__(self, model: str = "mistral"):
        self.model = model
        try:
            # Quick sanity check that ollama is available
            subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        except FileNotFoundError:
            raise RuntimeError("Ollama CLI not found. Install Ollama and ensure `ollama` is on PATH.")

    def generate(self, prompt: str, timeout: int = 120) -> Dict[str, Any]:
        """
        Run `ollama run <model>` and pipe prompt through stdin.
        Ensures utf-8 text mode so Windows pipe encoding issues don't occur.
        """
        try:
            # ensure prompt is a plain str and limited to reasonable size if needed
            if not isinstance(prompt, str):
                prompt = str(prompt)
            # Normalize encoding issues by ensuring it's valid UTF-8 string
            prompt = prompt.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")

            proc = subprocess.Popen(
                ["ollama", "run", self.model],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,               # use text mode (str)
                encoding="utf-8",        # explicit UTF-8 encoding for pipes
                errors="ignore"
            )

            out, err = proc.communicate(prompt, timeout=timeout)
            out = (out or "").strip()
            err = (err or "").strip()

            if proc.returncode != 0:
                logger.warning("Ollama returned code %s; stderr: %s", proc.returncode, err)
                return {"text": f"Ollama Error (rc={proc.returncode}): {err}", "meta": {"rc": proc.returncode}}

            return {"text": out, "meta": {"rc": 0}}
        except subprocess.TimeoutExpired:
            proc.kill()
            logger.exception("Ollama timed out")
            return {"text": "Error: Ollama generation timed out", "meta": {"rc": -1}}
        except Exception as e:
            logger.exception("Ollama generation error")
            return {"text": f"Error: Ollama generation failed: {e}", "meta": {}}
