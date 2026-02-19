"""
main.py — Entry point for the Athena RAG system.

Responsibilities:
  • Application bootstrap and dependency wiring
  • LLM provider management  (AIIntegration)
  • Interactive session orchestration (AthenaApp)
  • CLI parsing and logging setup
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from config import ConfigManager, get_config, paths
from exceptions import LLMError
from factories import LLMFactory
from handlers import CommandHandler
from local_rag import MergedLocalRAG
from models import SourceDocument
from pdf_processor import get_pdf_files_recursive
from services.prompt_builder import PromptBuilder
from services.query_service import QueryService


load_dotenv()

logger = logging.getLogger(__name__)

__all__ = ["AIIntegration", "AthenaApp", "main"]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SAMPLE_STRUCTURE: Dict[str, List[str]] = {
    "CAD_CAM": ["2D_Transformations", "CNC_Programming", "CAD_Algorithms"],
    "Machine_Design": ["Shafts", "Bearings", "Gears"],
    "Thermodynamics": ["Heat_Transfer", "Cycles"],
}

_EXIT_OK = 0
_EXIT_ERR = 1


# ---------------------------------------------------------------------------
# LLM gateway
# ---------------------------------------------------------------------------

class AIIntegration:
    """
    Manages LLM provider selection and answer generation.

    Uses :class:`LLMFactory` for construction; callers choose
    local vs. cloud at query time.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """
        Args:
            api_key: Optional API key for cloud LLM provider.
        """
        self.config: ConfigManager = get_config()
        self.local_llm, self.cloud_llm = LLMFactory.create_llms(api_key)

    # -- properties ------------------------------------------------------

    @property
    def has_local(self) -> bool:
        """Whether a local LLM backend is loaded."""
        return self.local_llm is not None

    @property
    def has_cloud(self) -> bool:
        """Whether a cloud LLM backend is configured."""
        return self.cloud_llm is not None

    # -- public ----------------------------------------------------------

    def generate_answer(
        self,
        question: str,
        sources: List[SourceDocument],
        use_cloud: bool = False,
    ) -> str:
        """
        Generate an answer using the appropriate LLM.

        Args:
            question:  The user's question.
            sources:   Retrieved context documents.
            use_cloud: Prefer the cloud LLM when ``True``.

        Returns:
            Generated answer text.

        Raises:
            LLMError: If no LLM is available or generation fails.
        """
        llm = self._select_llm(use_cloud)

        if use_cloud:
            builder = PromptBuilder.for_cloud_llm()
        else:
            builder = PromptBuilder.for_local_llm()

        prompt = builder.build(
            question=question,
            sources=sources
        )

        try:
            result = llm.generate(
                prompt=prompt,
                timeout=self.config.llm_timeout_seconds,
            )
            return self._extract_text(result)

        except LLMError:
            raise
        except Exception as exc:
            logger.exception("LLM generation failed")
            raise LLMError(f"LLM generation failed: {exc}") from exc

    # -- private ---------------------------------------------------------

    def _select_llm(self, use_cloud: bool) -> Any:
        """Return the requested backend or raise :class:`LLMError`."""
        if use_cloud and self.cloud_llm is not None:
            logger.info("Using cloud LLM")
            return self.cloud_llm

        if self.local_llm is not None:
            if use_cloud:
                logger.warning(
                    "Cloud LLM requested but unavailable — falling back to local"
                )
            else:
                logger.info("Using local LLM")
            return self.local_llm

        raise LLMError(
            "No LLM available.  Enable a local or cloud provider in configuration."
        )

    @staticmethod
    def _extract_text(result: Any) -> str:
        """
        Normalise an LLM response to a plain string.

        Handles both dict-style ``{"text": ..., "error": ...}`` responses
        and direct string returns.
        """
        if not isinstance(result, dict):
            return str(result)

        error = result.get("error")
        if error:
            raise LLMError(f"LLM returned an error: {error}")

        text = result.get("text")
        if text:
            return str(text)

        # Last resort — stringify the whole dict
        logger.warning("LLM response has no 'text' key: %s", result)
        return str(result)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class AthenaApp:
    """
    Top-level orchestrator for the Athena RAG system.

    Typical lifecycle::

        app = AthenaApp(data_dir="./data")
        app.initialize()            # RAG + LLM + query service
        app.interactive_session()   # REPL
    """

    def __init__(
        self,
        data_dir: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
    ) -> None:
        """
        Args:
            data_dir:       Root directory for documents (falls back to config).
            gemini_api_key: Optional Gemini API key (overrides env var).
        """
        self.config: ConfigManager = get_config()
        self.data_dir: Path = Path(data_dir or self.config.data_dir).resolve()
        self.gemini_api_key: Optional[str] = gemini_api_key

        # Populated by initialize()
        self.rag: Optional[MergedLocalRAG] = None
        self.ai: Optional[AIIntegration] = None
        self.query_service: Optional[QueryService] = None

    # -- public API ------------------------------------------------------

    def initialize(self) -> None:
        """
        Create the data directory, RAG backend, LLM gateway, and query
        service.

        Raises:
            FileNotFoundError: If data dir contains no supported files.
            RuntimeError:      If RAG or LLM initialisation fails.
        """
        self._ensure_data_directory()

        files = get_pdf_files_recursive(str(self.data_dir))
        if not files:
            raise FileNotFoundError(
                f"No supported files in {self.data_dir}.  "
                "Add documents and re-run."
            )

        logger.info("Found %d file(s) in %s", len(files), self.data_dir)

        self._initialize_rag()
        self.ai = AIIntegration(self.gemini_api_key)
        self.query_service = QueryService(self.rag, self.ai)

        logger.info("Athena initialised — ready for queries")

    def interactive_session(self) -> None:
        """
        Run the interactive Q&A loop.

        Raises:
            RuntimeError: If :meth:`initialize` has not been called.
        """
        self._require_initialized()

        print("\n\U0001f9e0 ATHENA — Interactive mode (type 'help' for commands)\n")

        handler = CommandHandler(self.query_service, self.rag)  # type: ignore[arg-type]

        while True:
            try:
                user_input = input(handler.get_prompt())
                result = handler.handle_command(user_input)

                if result.message:
                    print(result.message)

                if not result.continue_loop:
                    break

            except (KeyboardInterrupt, EOFError):
                print("\n\nInterrupted — goodbye!")
                break

    # -- private ---------------------------------------------------------

    def _require_initialized(self) -> None:
        """Guard that prevents use before :meth:`initialize`."""
        if self.rag is None or self.query_service is None:
            raise RuntimeError(
                "Call initialize() before starting an interactive session."
            )

    def _ensure_data_directory(self) -> None:
        """Create ``data_dir`` and sample sub-folders when missing."""
        if self.data_dir.exists():
            return

        logger.info("Creating data directory: %s", self.data_dir)
        for subject, modules in _SAMPLE_STRUCTURE.items():
            for module in modules:
                (self.data_dir / subject / module).mkdir(
                    parents=True, exist_ok=True
                )

        logger.info(
            "Sample folder structure created under %s — "
            "add documents and re-run",
            self.data_dir,
        )

    def _initialize_rag(self) -> None:
        """Create the RAG backend and conditionally ingest documents."""
        self.rag = MergedLocalRAG(
            persist_directory=self.config.chroma_persist_dir,
            model_name=self.config.embedding_model,
            embed_batch_size=self.config.embed_batch_size,
            enable_bm25=self.config.enable_bm25,
        )

        stats = self.rag.get_collection_stats()
        total: int = stats.get("total_chunks", 0)

        if total == 0 or self.config.reload_on_start:
            reason = "reload_on_start=True" if total else "empty database"
            logger.info("Ingesting documents (%s)", reason)
            self.rag.ingest_directory(str(self.data_dir), rebuild_bm25=True)
        else:
            logger.info(
                "Existing database contains %d chunks — skipping ingestion",
                total,
            )


# ---------------------------------------------------------------------------
# Logging bootstrap  (only when executed as a script, never on import)
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    """Set up root logger with console + rotating file handler."""
    log_file = Path(paths.get_log_file("athena_prep"))
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(log_file), encoding="utf-8"),
        ],
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Athena — RAG-powered study assistant",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Root directory containing documents (default: from config)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Google Gemini API key (overrides GOOGLE_API_KEY env var)",
    )
    return parser


def main() -> int:
    """
    Entry point.

    Returns:
        ``0`` on clean exit, ``1`` on error.
    """
    _configure_logging()
    args = _build_parser().parse_args()

    api_key: Optional[str] = args.api_key or os.getenv("GOOGLE_API_KEY")

    app = AthenaApp(
        data_dir=args.data_dir,
        gemini_api_key=api_key,
    )

    try:
        app.initialize()
    except FileNotFoundError as exc:
        logger.warning("%s", exc)
        print(f"\n{exc}")
        return _EXIT_ERR
    except Exception:
        logger.exception("Failed to initialise Athena")
        return _EXIT_ERR

    app.interactive_session()
    return _EXIT_OK


if __name__ == "__main__":
    sys.exit(main())