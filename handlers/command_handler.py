"""
Command Handler - Processes user commands in interactive session.
Separates command logic from the main interactive loop.
"""
import logging
from typing import Optional, Dict, Any
from services import ContextAssembler, QueryService
from config import get_config

logger = logging.getLogger(__name__)


class CommandResult:
    """Result of a command execution"""
    def __init__(self, continue_loop: bool = True, message: str = None):
        self.continue_loop = continue_loop
        self.message = message


class CommandHandler:
    """Handles interactive session commands"""
    
    def __init__(self, query_service: QueryService, rag):
        self.query_service = query_service
        self.rag = rag
        self.config = get_config()
        self.filters = {"subject": None, "module": None}
        self.use_cloud = self.config.use_cloud_by_default
    
    def handle_command(self, user_input: str) -> CommandResult:
        """
        Process user input and return result.
        
        Args:
            user_input: Raw user input string
            
        Returns:
            CommandResult with continue flag and optional message
        """
        inp = user_input.strip().lower()
        
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
        else:
            # It's a question
            return self._handle_question(user_input.strip())
    
    def _handle_stats(self) -> CommandResult:
        """Show database statistics"""
        stats = self.rag.get_collection_stats()
        message = (
            f"📊 Database Stats:\n"
            f"   • Chunks: {stats.get('total_chunks', 0)}\n"
            f"   • Subjects: {len(stats.get('subjects', []))}\n"
            f"   • Subjects: {', '.join(stats.get('subjects', []))}"
        )
        return CommandResult(continue_loop=True, message=message)
    
    def _handle_mode_switch(self, use_cloud: bool) -> CommandResult:
        """Switch between local and cloud mode"""
        self.use_cloud = use_cloud
        mode = "CLOUD" if use_cloud else "LOCAL"
        return CommandResult(continue_loop=True, message=f"✅ Switched to {mode} mode.")
    
    def _handle_subject_filter(self, user_input: str) -> CommandResult:
        """Set subject filter"""
        subject = user_input.split(":", 1)[1].strip()
        self.filters["subject"] = subject if subject else None
        return CommandResult(
            continue_loop=True,
            message=f"✅ Subject filter: {subject or 'cleared'}"
        )
    
    def _handle_module_filter(self, user_input: str) -> CommandResult:
        """Set module filter"""
        module = user_input.split(":", 1)[1].strip()
        self.filters["module"] = module if module else None
        return CommandResult(
            continue_loop=True,
            message=f"✅ Module filter: {module or 'cleared'}"
        )
    
    def _handle_help(self) -> CommandResult:
        """Show help message"""
        message = (
            "\n📖 Available commands:\n"
            "   • Type your question to get an answer\n"
            "   • 'stats' - Show database statistics\n"
            "   • 'local' - Switch to local LLM\n"
            "   • 'cloud' - Switch to cloud LLM\n"
            "   • 'filter subject: <name>' - Filter by subject\n"
            "   • 'filter module: <name>' - Filter by module\n"
            "   • 'help' - Show this help\n"
            "   • 'quit' or 'exit' - Exit the program"
        )
        return CommandResult(continue_loop=True, message=message)
    
    def _handle_question(self, question: str) -> CommandResult:
        """Process a question and generate answer"""
        print("🔍 Searching...")
        
        try:
            # Execute query using query service
            result = self.query_service.execute_query(
                question=question,
                use_cloud=self.use_cloud,
                subject_filter=self.filters["subject"],
                module_filter=self.filters["module"]
            )
            
            # Format response
            message = "\n" + "="*60 + "\n"
            message += "ANSWER:\n\n"
            message += result.answer + "\n"
            
            # Add sources if enabled
            if self.config.show_sources_on_answer and result.sources:
                message += "\n" + "-"*60 + "\n"
                message += "SOURCES:\n\n"
                message += ContextAssembler.format_sources_summary(result.sources)
            
            message += "\n" + "="*60
            
            return CommandResult(continue_loop=True, message=message)
            
        except Exception as e:
            logger.exception(f"Error processing question: {e}")
            return CommandResult(
                continue_loop=True,
                message=f"\n❌ Error: {e}\nTry again or type 'quit' to exit."
            )
    
    def get_prompt(self) -> str:
        """Get the input prompt string"""
        mode_display = "☁️ CLOUD" if self.use_cloud else "💻 LOCAL"
        return f"\n❓ [{mode_display}] Ask: "