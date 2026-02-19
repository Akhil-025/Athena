"""
Command Handler - Processes user commands in interactive session.
Separates command logic from the main interactive loop.
FIXED: Added comprehensive type hints
"""
import logging
from typing import Optional, Dict, Any, TYPE_CHECKING
from services import ContextAssembler, QueryService
from config import get_config
from exceptions import QueryError, LLMError, RAGError

# ADDED: Import protocols for type checking
if TYPE_CHECKING:
    from protocols import RAGProtocol

logger = logging.getLogger(__name__)


class CommandResult:
    """Result of a command execution"""
    
    def __init__(self, continue_loop: bool = True, message: Optional[str] = None) -> None:
        """
        Initialize command result.
        
        Args:
            continue_loop: Whether to continue the interactive loop
            message: Optional message to display to user
        """
        self.continue_loop: bool = continue_loop
        self.message: Optional[str] = message


class CommandHandler:
    """Handles interactive session commands"""
    
    def __init__(self, query_service: QueryService, rag: 'RAGProtocol') -> None:
        """
        Initialize command handler.
        
        Args:
            query_service: QueryService instance for executing queries
            rag: RAG instance implementing RAGProtocol
        """
        self.query_service: QueryService = query_service
        self.rag: RAGProtocol = rag
        self.config = get_config()
        self.filters: Dict[str, Optional[str]] = {"subject": None, "module": None}
        self.use_cloud: bool = self.config.use_cloud_by_default
    
    def handle_command(self, user_input: str) -> CommandResult:
        """
        Process user input and return result.
        
        Args:
            user_input: Raw user input string
            
        Returns:
            CommandResult with continue flag and optional message
        """
        inp: str = user_input.strip().lower()
        
        # Exit commands
        if inp in ("quit", "exit", "q"):
            return CommandResult(continue_loop=False, message="Goodbye! 👋")
        
        # Empty input
        if not inp:
            return CommandResult(continue_loop=True)
        
        # Command routing
        if inp == "stats":
            return self._handle_stats()
        elif inp == "local":
            return self._handle_mode_switch(use_cloud=False)
        elif inp == "cloud":
            return self._handle_mode_switch(use_cloud=True)
        elif inp.startswith("filter subject:"):
            return self._handle_subject_filter(user_input)
        elif inp.startswith("filter module:"):
            return self._handle_module_filter(user_input)
        elif inp == "help":
            return self._handle_help()
        elif inp in ("filter clear", "clear filter", "clear filters"):
            return self._handle_filter_clear()
        else:
            # It's a question
            return self._handle_question(user_input.strip())
    
    def _handle_stats(self) -> CommandResult:
        """
        Show database statistics.
        
        Returns:
            CommandResult with stats message
        """
        stats: Dict[str, Any] = self.rag.get_collection_stats()
        
        subjects: list = stats.get('subjects', [])
        subject_list: str = ', '.join(subjects) if subjects else 'None'
        
        message: str = (
            f"📊 Database Stats:\n"
            f"   • Chunks: {stats.get('total_chunks', 0)}\n"
            f"   • Subjects: {len(subjects)}\n"
            f"   • Subjects: {subject_list}"
        )
        return CommandResult(continue_loop=True, message=message)
    
    def _handle_filter_clear(self) -> CommandResult:
        self.filters["subject"] = None
        self.filters["module"] = None
        return CommandResult(continue_loop=True, message="✅ All filters cleared.")
    
    def _handle_mode_switch(self, use_cloud: bool) -> CommandResult:
        """
        Switch between local and cloud mode.
        
        Args:
            use_cloud: Whether to use cloud LLM
            
        Returns:
            CommandResult with confirmation message
        """
        self.use_cloud = use_cloud
        mode: str = "CLOUD" if use_cloud else "LOCAL"
        return CommandResult(continue_loop=True, message=f"✅ Switched to {mode} mode.")
    
    def _handle_subject_filter(self, user_input: str) -> CommandResult:
        """
        Set subject filter.
        
        Args:
            user_input: Raw user input with filter command
            
        Returns:
            CommandResult with confirmation message
        """
        subject: str = user_input.split(":", 1)[1].strip()
        self.filters["subject"] = subject if subject else None
        return CommandResult(
            continue_loop=True,
            message=f"✅ Subject filter: {subject or 'cleared'}"
        )
    
    def _handle_module_filter(self, user_input: str) -> CommandResult:
        """
        Set module filter.
        
        Args:
            user_input: Raw user input with filter command
            
        Returns:
            CommandResult with confirmation message
        """
        module: str = user_input.split(":", 1)[1].strip()
        self.filters["module"] = module if module else None
        return CommandResult(
            continue_loop=True,
            message=f"✅ Module filter: {module or 'cleared'}"
        )
    
    def _handle_help(self) -> CommandResult:
        """
        Show help message.
        
        Returns:
            CommandResult with help text
        """
        message: str = (
            "\n📖 Available commands:\n"
            "   • Type your question to get an answer\n"
            "   • 'stats' - Show database statistics\n"
            "   • 'local' - Switch to local LLM\n"
            "   • 'cloud' - Switch to cloud LLM\n"
            "   • 'filter subject: <name>' - Filter by subject\n"
            "   • 'filter module: <name>' - Filter by module\n"
            "   • 'help' - Show this help\n"
            "   • 'quit' or 'exit' - Exit the program\n"
            "   • 'filter clear' - Clear all filters\n"
        )
        return CommandResult(continue_loop=True, message=message)
    
    def _handle_question(self, question: str) -> CommandResult:
        """
        Process a question and generate answer.
        
        Args:
            question: User's question
            
        Returns:
            CommandResult with answer and sources
        """
        print("🔍 Searching...")
        
        try:
            # Execute query using query service
            from models import QueryResult
            result: QueryResult = self.query_service.execute_query(
                question=question,
                use_cloud=self.use_cloud,
                subject_filter=self.filters["subject"],
                module_filter=self.filters["module"]
            )
            
            # Format response
            message: str = "\n" + "="*60 + "\n"
            message += "ANSWER:\n\n"
            message += result.answer + "\n"
            
            # Add sources if enabled
            if self.config.show_sources_on_answer and result.sources:
                message += "\n" + "-"*60 + "\n"
                message += "SOURCES:\n\n"
                message += ContextAssembler.format_sources_summary(result.sources)
            
            message += "\n" + "="*60
            
            return CommandResult(continue_loop=True, message=message)
        
        except LLMError as e:
            logger.error(f"LLM error: {e}")
            return CommandResult(
                continue_loop=True,
                message=f"\n❌ LLM Error: {e}\n\nThe language model failed to generate an answer. "
                        f"Try switching modes ('local' or 'cloud') or check your configuration."
            )
        
        except RAGError as e:
            logger.error(f"RAG error: {e}")
            return CommandResult(
                continue_loop=True,
                message=f"\n❌ Search Error: {e}\n\nFailed to search the knowledge base. "
                        f"Check that documents are properly indexed."
            )
        
        except QueryError as e:
            logger.error(f"Query error: {e}")
            return CommandResult(
                continue_loop=True,
                message=f"\n❌ Query Error: {e}\n\nFailed to process your question. "
                        f"Try rephrasing or type 'help' for assistance."
            )
        
        except Exception as e:
            logger.exception(f"Unexpected error processing question: {e}")
            return CommandResult(
                continue_loop=True,
                message=f"\n❌ Unexpected Error: {e}\n\nAn unexpected error occurred. "
                        f"Type 'quit' to exit or try a different question."
            )
    
    def get_prompt(self) -> str:
        """
        Get the input prompt string.
        
        Returns:
            Formatted prompt string
        """
        mode_display: str = "☁️ CLOUD" if self.use_cloud else "💻 LOCAL"
        return f"\n❓ [{mode_display}] Ask: "