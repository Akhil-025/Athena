# main.py 

import os
import sys
import logging
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

from config import get_config, paths
from local_rag import MergedLocalRAG
from pdf_processor import get_pdf_files_recursive
from models import SourceDocument
from services import QueryService
from factories import LLMFactory
from handlers import CommandHandler

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(paths.get_log_file("athena_prep"), encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

config = get_config()


class AIIntegration:
    """
    AI Integration - Manages LLM providers and answer generation.
    Uses Factory Pattern for LLM initialization.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize AI integration with LLM providers.
        
        Args:
            api_key: Optional API key for cloud LLM
        """
        self.config = get_config()
        
        # Use factory to create LLMs
        self.local_llm, self.cloud_llm = LLMFactory.create_llms(api_key)
    
    def generate_answer(
        self,
        question: str,
        sources: list[SourceDocument],
        use_cloud: bool = False
    ) -> str:
        """
        Generate answer using appropriate LLM.
        
        Args:
            question: The user's question
            sources: List of SourceDocument objects with context
            use_cloud: Whether to use cloud LLM
            
        Returns:
            Generated answer text
        """
        from services import PromptBuilder
        
        # Select LLM
        if use_cloud and self.cloud_llm:
            llm = self.cloud_llm
            logger.info("Using cloud LLM")
        elif self.local_llm:
            llm = self.local_llm
            logger.info("Using local LLM")
        else:
            return "❌ No LLM available. Enable local or cloud LLM."
        
        # Build prompt using PromptBuilder service
        prompt = PromptBuilder.build_prompt(
            question=question,
            sources=sources,
            use_cloud=use_cloud
        )
        
        # Generate response
        try:
            result = llm.generate(
                prompt=prompt,
                timeout=self.config.llm_timeout_seconds
            )
            
            # Extract text from response
            if isinstance(result, dict):
                return result.get("text", str(result))
            else:
                return str(result)
                
        except Exception as e:
            logger.exception(f"LLM generation failed: {e}")
            return f"❌ Error generating answer: {str(e)}"
    
    def has_local_llm(self) -> bool:
        """Check if local LLM is available"""
        return self.local_llm is not None
    
    def has_cloud_llm(self) -> bool:
        """Check if cloud LLM is available"""
        return self.cloud_llm is not None


class AthenaApp:
    """Main application class for Athena RAG system"""
    
    def __init__(self, data_dir: str = "./data", gemini_api_key: Optional[str] = None):
        """
        Initialize Athena application.
        
        Args:
            data_dir: Directory containing PDF documents
            gemini_api_key: Optional API key for Gemini
        """
        self.data_dir = data_dir
        self.rag = None
        self.ai = AIIntegration(gemini_api_key)
        self.query_service = None
        self.setup_data_directory()

    def setup_data_directory(self) -> bool:
        """Create data directory if it doesn't exist"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
            logger.info("Created data directory: %s", self.data_dir)
            self._create_sample_structure()
        return True

    def _create_sample_structure(self):
        """Create sample folder structure"""
        sample_structure = {
            "CAD_CAM": ["2D_Transformations", "CNC_Programming", "CAD_Algorithms"],
            "Machine_Design": ["Shafts", "Bearings", "Gears"],
            "Thermodynamics": ["Heat_Transfer", "Cycles"]
        }
        for subject, modules in sample_structure.items():
            for module in modules:
                os.makedirs(os.path.join(self.data_dir, subject, module), exist_ok=True)

        logger.info("Sample folder structure created under %s", self.data_dir)
        print("📂 Sample folders created. Add PDFs and re-run.")

    def initialize_rag(self) -> bool:
        """
        Initialize RAG system with vector database and query service.
        
        Returns:
            True if initialization successful
        """
        logger.info("Initializing RAG...")
        
        self.rag = MergedLocalRAG(
            persist_directory=config.chroma_persist_dir,
            model_name=config.embedding_model,
            embed_batch_size=config.embed_batch_size,
            enable_bm25=config.enable_bm25
        )

        # Initialize query service
        self.query_service = QueryService(self.rag, self.ai)

        stats = self.rag.get_collection_stats()

        if stats.get("total_chunks", 0) == 0 or config.reload_on_start:
            logger.info("No chunks found or reload requested — ingesting directory")
            self.rag.ingest_directory(self.data_dir, rebuild_bm25=True)
        else:
            logger.info("Using existing DB with %d chunks", stats.get("total_chunks", 0))

        return True

    def interactive_session(self):
        """
        Interactive Q&A session.
        Uses CommandHandler to process all user input - FIXED VERSION!
        """
        if not self.rag:
            self.initialize_rag()
        
        print("\n🧠 ATHENA — Interactive mode (type 'quit' to exit)\n")
        
        # Create command handler - delegates ALL command logic
        handler = CommandHandler(self.query_service, self.rag)
        
        # Main loop - just input → handle → display
        while True:
            try:
                # Get user input
                user_input = input(handler.get_prompt())
                
                # Process command using handler
                result = handler.handle_command(user_input)
                
                # Display result message if any
                if result.message:
                    print(result.message)
                
                # Check if should continue
                if not result.continue_loop:
                    break
                    
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Goodbye!")
                break
            except Exception as e:
                logger.exception(f"Unexpected error: {e}")
                print(f"\n❌ Unexpected error: {e}")
                print("Type 'quit' to exit or continue asking questions.")


def main():
    """Main entry point"""
    gemini_key = os.getenv("GOOGLE_API_KEY")
    app = AthenaApp(gemini_api_key=gemini_key)

    pdfs = get_pdf_files_recursive(app.data_dir)
    if not pdfs:
        print("📁 No PDFs found in data/. Add files and rerun.")
        return

    app.initialize_rag()
    app.interactive_session()


if __name__ == "__main__":
    main()