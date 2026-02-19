"""
Command Handler - Processes user commands in interactive session.
Separates command logic from the main interactive loop.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, TYPE_CHECKING
from config import get_config, ConfigManager
from exceptions import QueryError, LLMError, RAGError
from models import QueryResult
from services import ContextAssembler, QueryService

if TYPE_CHECKING:
    from protocols import RAGProtocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result wrapper
# ---------------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a command execution."""

    continue_loop: bool = True
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class CommandHandler:
    """Handles interactive session commands."""

    # Commands that map directly to a handler (no argument parsing needed).
    # Populated in __init__ so each instance binds to its own methods.
    _simple_commands: Dict[str, Callable[[], CommandResult]]

    def __init__(self, query_service: QueryService, rag: "RAGProtocol") -> None:
        self.query_service: QueryService = query_service
        self.rag: "RAGProtocol" = rag
        self.config: ConfigManager = get_config()
        self.filters: Dict[str, Optional[str]] = {"subject": None, "module": None}
        self.use_cloud: bool = self.config.use_cloud_by_default

        # ---- dispatch table for zero-arg commands ----
        self._simple_commands = {
            "stats":          self._handle_stats,
            "local":          lambda: self._handle_mode_switch(use_cloud=False),
            "cloud":          lambda: self._handle_mode_switch(use_cloud=True),
            "help":           self._handle_help,
            "filter clear":   self._handle_filter_clear,
            "clear filter":   self._handle_filter_clear,
            "clear filters":  self._handle_filter_clear,
            "status":         self._handle_status,
        }

        # ---- dispatch table for prefix commands (need the raw input) ----
        self._prefix_commands: Dict[str, Callable[[str], CommandResult]] = {
            "filter subject:": lambda raw: self._handle_filter("subject", raw),
            "filter module:":  lambda raw: self._handle_filter("module", raw),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_command(self, user_input: str) -> CommandResult:
        """Process user input and return a result."""
        stripped: str = user_input.strip()
        lowered: str = stripped.lower()

        # Exit
        if lowered in ("quit", "exit", "q"):
            return CommandResult(continue_loop=False, message="Goodbye! 👋")

        # Empty
        if not lowered:
            return CommandResult()

        # Simple (exact-match) commands
        if lowered in self._simple_commands:
            return self._simple_commands[lowered]()

        # Prefix commands
        for prefix, handler in self._prefix_commands.items():
            if lowered.startswith(prefix):
                return handler(stripped)

        # Anything else is a question
        return self._handle_question(stripped)

    def get_prompt(self) -> str:
        """Return the formatted input prompt string."""
        mode: str = "☁️  CLOUD" if self.use_cloud else "💻 LOCAL"
        parts: list[str] = [mode]

        active = self._active_filter_parts()
        if active:
            parts.append(" | ".join(active))

        return f"\n❓ [{' · '.join(parts)}] Ask: "

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def _handle_stats(self) -> CommandResult:
        stats: Dict[str, Any] = self.rag.get_collection_stats()
        subjects: list[str] = stats.get("subjects", [])
        subject_list: str = ", ".join(subjects) if subjects else "None"

        message = (
            f"📊 Database Stats:\n"
            f"   • Chunks:   {stats.get('total_chunks', 0)}\n"
            f"   • Subjects: {len(subjects)} — {subject_list}"
        )
        return CommandResult(message=message)

    def _handle_status(self) -> CommandResult:
        """Show current mode and active filters."""
        mode: str = "CLOUD" if self.use_cloud else "LOCAL"
        active = self._active_filter_parts()
        filter_text: str = ", ".join(active) if active else "none"

        message = (
            f"ℹ️  Current state:\n"
            f"   • Mode:    {mode}\n"
            f"   • Filters: {filter_text}"
        )
        return CommandResult(message=message)

    def _handle_mode_switch(self, *, use_cloud: bool) -> CommandResult:
        self.use_cloud = use_cloud
        mode: str = "CLOUD" if use_cloud else "LOCAL"
        return CommandResult(message=f"✅ Switched to {mode} mode.")

    # ---- unified filter handler ----

    def _handle_filter(self, key: str, raw_input: str) -> CommandResult:
        """
        Set or clear a single filter.

        Args:
            key: Filter name ("subject" or "module").
            raw_input: Original (non-lowered) user input so casing is preserved.
        """
        value: str = raw_input.split(":", 1)[1].strip()
        self.filters[key] = value or None
        return CommandResult(
            message=f"✅ {key.title()} filter: {value or 'cleared'}"
        )

    def _handle_filter_clear(self) -> CommandResult:
        self.filters = {k: None for k in self.filters}
        return CommandResult(message="✅ All filters cleared.")

    def _handle_help(self) -> CommandResult:
        message = (
            "\n📖 Available commands:\n"
            "   • Type your question to get an answer\n"
            "   • 'stats'                  — Database statistics\n"
            "   • 'status'                 — Current mode & filters\n"
            "   • 'local' / 'cloud'        — Switch LLM mode\n"
            "   • 'filter subject: <name>' — Filter by subject\n"
            "   • 'filter module: <name>'  — Filter by module\n"
            "   • 'filter clear'           — Clear all filters\n"
            "   • 'help'                   — This help text\n"
            "   • 'quit' / 'exit'          — Exit the program\n"
        )
        return CommandResult(message=message)

    def _handle_question(self, question: str) -> CommandResult:
        """Process a question and generate an answer."""
        try:
            result: QueryResult = self.query_service.execute_query(
                question=question,
                use_cloud=self.use_cloud,
                subject_filter=self.filters["subject"],
                module_filter=self.filters["module"],
            )
            message = self._format_answer(result)
            return CommandResult(message=message)

        except LLMError as e:
            logger.error("LLM error: %s", e)
            return CommandResult(message=(
                f"\n❌ LLM Error: {e}\n\n"
                "The language model failed.  "
                "Try switching modes ('local' / 'cloud') or check your configuration."
            ))

        except RAGError as e:
            logger.error("RAG error: %s", e)
            return CommandResult(message=(
                f"\n❌ Search Error: {e}\n\n"
                "Failed to search the knowledge base.  "
                "Check that documents are properly indexed."
            ))

        except QueryError as e:
            logger.error("Query error: %s", e)
            return CommandResult(message=(
                f"\n❌ Query Error: {e}\n\n"
                "Failed to process your question.  "
                "Try rephrasing or type 'help' for assistance."
            ))

        except Exception:
            logger.exception("Unexpected error processing question")
            return CommandResult(message=(
                "\n❌ Unexpected error — see logs for details.\n"
                "Type 'quit' to exit or try a different question."
            ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _format_answer(self, result: QueryResult) -> str:
        """Build the formatted answer + optional sources block."""
        sep = "=" * 60
        lines: list[str] = [
            "",
            sep,
            "🔍 ANSWER:\n",
            result.answer,
        ]

        if self.config.show_sources_on_answer and result.sources:
            lines += [
                "",
                "-" * 60,
                "📚 SOURCES:\n",
                ContextAssembler.format_sources_summary(result.sources),
            ]

        lines.append(sep)
        return "\n".join(lines)

    def _active_filter_parts(self) -> list[str]:
        """Return human-readable strings for every active filter."""
        return [
            f"{k}={v}" for k, v in self.filters.items() if v is not None
        ]