import os
import sys
import logging
import json
from pathlib import Path
from local_rag import create_rag_system
from pdf_processor import get_pdf_files_recursive, get_organization_structure
from dotenv import load_dotenv
from utils.sanitize import prepare_context_for_cloud
from utils.llm_cache import question_hash, load_cached_answer, save_cached_answer
from llm_wrappers.llm_local import LocalLLM
from llm_wrappers.llm_cloud import CloudLLM

try:
    from llm_wrappers.llm_ollama import OllamaLLM
except Exception:
    OllamaLLM = None

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('athena_prep.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

CONFIG = json.load(open(Path(__file__).parent / "config.json"))

class AIIntegration:
    def __init__(self, api_key: str = None):
        """Initialize AI integration with local and cloud options."""
        self.client = None
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        
        # Initialize local LLM
        lm_cfg = CONFIG.get("local_model", {})
        engine = lm_cfg.get("default_engine", "ollama").lower()

        self.local_llm = None

        if engine == "ollama":
            if OllamaLLM is None:
                logger.warning("❌ Ollama wrapper missing. Make sure llm_wrappers/llm_ollama.py exists.")
            else:
                try:
                    self.local_llm = OllamaLLM(model=lm_cfg.get("ollama_model", "mistral"))
                    logger.info("✅ Local LLM (Ollama) initialized: %s", lm_cfg.get("ollama_model", "mistral"))
                except Exception as e:
                    logger.warning(f"❌ Ollama init failed: {e}")
                    self.local_llm = None

        elif engine == "llama-cpp":
            # initialize llama-cpp wrapper if requested
            try:
                self.local_llm = LocalLLM(
                    model_path=lm_cfg.get("model_path", lm_cfg.get("local_model_path", "")),
                    max_tokens=lm_cfg.get("max_tokens",512),
                    n_ctx=lm_cfg.get("n_ctx",2048),
                    temperature=lm_cfg.get("temperature",0.0)
                )
                logger.info("✅ Local LLM (llama-cpp) initialized")
            except Exception as e:
                logger.warning(f"❌ Local LLM (llama-cpp) not available: {e}")
                self.local_llm = None
        else:
            logger.info("ℹ️ No local engine configured; set local_model.default_engine in config.json")
            self.local_llm = None
        
        # Initialize cloud LLM if API key provided
        if self.api_key:
            try:
                self.cloud_llm = CloudLLM(
                    api_key=self.api_key, 
                    model="gemini-1.5-pro",
                    max_output_tokens=lm_cfg.get("max_tokens",512)
                )
                logger.info("✅ Cloud LLM (Gemini) initialized")
            except Exception as e:
                logger.warning(f"❌ Cloud LLM init failed: {e}")
                self.cloud_llm = None
        else:
            self.cloud_llm = None
            logger.warning("❌ GOOGLE_API_KEY not set. Cloud AI will be disabled.")
    
    def generate_answer(self, question: str, context: str, use_cloud: bool = False) -> str:
        """Generate AI answer using local or cloud LLM."""
        if use_cloud and self.cloud_llm:
            logger.info("🤖 Using Cloud LLM for answer generation")
            # Prepare sanitized context for cloud
            safe_chunks = [{"text": context[:2000], "source": "user_documents"}]  # Truncate for safety
            safe_ctx = prepare_context_for_cloud(
                safe_chunks,
                max_chunks=CONFIG["sanitization"]["max_chunks_sent_to_cloud"],
                max_chars=CONFIG["sanitization"]["max_chunk_chars_sent_to_cloud"]
            )
            ctx_text = "\n\n".join([f"Source {i+1} ({c['source']}):\n{c['text']}" for i,c in enumerate(safe_ctx)])
            
            prompt = f"""You are Athena — an expert AI study partner.
                        Provide clear, simple explanations suitable for engineering students.
                        Answer the question using ONLY the provided context.

CONTEXT:
{ctx_text}

QUESTION: {question}

ANSWER:"""
            
            result = self.cloud_llm.generate(prompt, timeout=CONFIG.get("llm_timeout_seconds",60))
            return result["text"]
        
        elif self.local_llm:
            logger.info("🤖 Using Local LLM for answer generation")
            prompt = f"""You are an expert engineering tutor. Use the context to answer the question.

CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""
            
            result = self.local_llm.generate(prompt, timeout=CONFIG.get("llm_timeout_seconds",60))
            return result["text"]
        else:
        # prefer local_llm if available (Ollama or llama-cpp)
            if self.local_llm:
                logger.info("🤖 Generating with local LLM")
                result = self.local_llm.generate(prompt, timeout=CONFIG.get("llm_timeout_seconds",120))
                return result.get("text", str(result))
            else:
                return "❌ No AI provider available locally. Enable Ollama or configure a local GGML model, or use cloud mode."

class AthenaApp:
    def __init__(self, data_dir: str = "./data", gemini_api_key: str = None):
        self.data_dir = data_dir
        self.rag = None
        self.ai = AIIntegration(gemini_api_key)
        self.setup_data_directory()
    
    def setup_data_directory(self):
        """Ensure data directory exists with sample structure."""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            print(f"📁 Created data directory: {self.data_dir}")
            self._create_sample_structure()
            return True
        return True
    
    def _create_sample_structure(self):
        """Create sample folder structure for guidance."""
        sample_structure = {
            "CAD_CAM": ["2D_Transformations", "CNC_Programming", "CAD_Algorithms"],
            "Machine_Design": ["Shafts", "Bearings", "Gears"],
            "Thermodynamics": ["Heat_Transfer", "Cycles"]
        }
        
        for subject, modules in sample_structure.items():
            subject_path = os.path.join(self.data_dir, subject)
            os.makedirs(subject_path, exist_ok=True)
            
            for module in modules:
                module_path = os.path.join(subject_path, module)
                os.makedirs(module_path, exist_ok=True)
        
        print("📂 Created sample folder structure:")
        for subject, modules in sample_structure.items():
            print(f"   ├── {subject}/")
            for module in modules:
                print(f"   │   ├── {module}/")
        print("\n💡 Add your PDF files to the appropriate subject/module folders")
    
    def auto_answer_question(self, question: str, subject_filter: str = None, module_filter: str = None, use_cloud: bool = False) -> str:
        """Automatically answer questions using RAG + AI with local/cloud choice."""
        print(f"   🔍 Searching through documents... ({'Cloud' if use_cloud else 'Local'} mode)")
        
        # Search for relevant content
        results = self.rag.search(question, n_results=8, subject_filter=subject_filter, module_filter=module_filter)
        
        if results['total_results'] == 0:
            return "❌ No relevant information found in your documents to answer this question."
        
        # Build comprehensive context
        context = self.build_context_prompt(question, results)
        
        # Check cache first
        context_ids = [m.get("file_name", "") + f":{i}" for i, m in enumerate(results['metadatas'])]
        qh = question_hash(question, context_ids)
        cached = load_cached_answer(qh)
        if cached:
            print("   💾 Using cached answer")
            return cached.get("answer", "Cached answer unavailable")
        
        # Generate AI answer
        if self.ai.local_llm or (use_cloud and self.ai.cloud_llm):
            print(f"   🤖 Generating AI answer from your documents...")
            answer = self.ai.generate_answer(question, context, use_cloud=use_cloud)
            
            # Cache the result
            save_cached_answer(qh, {"answer": answer, "sources": [m.get("file_name", "unknown") for m in results['metadatas']]})
            return answer
        else:
            # Fallback: show organized context
            formatted_results = self.format_search_results(results)
            out = f"{formatted_results}\n💡 **Context ready for manual analysis**"
            save_cached_answer(qh, {"answer": out, "sources": [m.get("file_name", "unknown") for m in results['metadatas']]})
            return out
    
    def initialize_rag(self):
        """Initialize Athena."""
        try:
            print("🚀 Initializing Athena...")
            self.rag = create_rag_system(self.data_dir)
            
            # Show detailed statistics
            org_info = self.rag.get_organization_info()
            stats = org_info['database_stats']
            file_structure = org_info['file_structure']
            
            pdf_files = get_pdf_files_recursive(self.data_dir)
            
            print(f"\n📊 System Status:")
            print(f"   • PDF Files: {len(pdf_files)}")
            print(f"   • Knowledge Chunks: {stats['total_chunks']}")
            print(f"   • Subjects: {len(stats['subjects'])}")
            print(f"   • Database: {stats['persist_directory']}")
            print(f"   • Local LLM: {'✅ Available' if self.ai.local_llm else '❌ Unavailable'}")
            print(f"   • Cloud LLM: {'✅ Available' if self.ai.cloud_llm else '❌ Unavailable'}")
            
            if stats['subjects']:
                print(f"\n📚 Loaded Subjects:")
                for subject in stats['subjects']:
                    subject_files = [f for f in pdf_files if f['subject'] == subject]
                    modules = set(f['module'] for f in subject_files)
                    print(f"   • {subject}: {len(subject_files)} files in {len(modules)} modules")
            
            if stats['total_chunks'] == 0:
                print("\n❌ No documents loaded. Please add PDF files to the appropriate folders.")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG system: {e}")
            print(f"❌ Error initializing system: {e}")
            return False
    
    def format_search_results(self, results: dict) -> str:
        """Format search results for display with organizational info."""
        if not results or results['total_results'] == 0:
            filters_text = ""
            if results['filters']['subject']:
                filters_text = f" (filtered by: {results['filters']['subject']}"
                if results['filters']['module']:
                    filters_text += f" → {results['filters']['module']}"
                filters_text += ")"
            return f"❌ No relevant information found in the documents{filters_text}."
        
        formatted = f"🔍 Found {results['total_results']} relevant sections"
        
        # Show active filters
        if results['filters']['subject'] or results['filters']['module']:
            filters = []
            if results['filters']['subject']:
                filters.append(f"Subject: {results['filters']['subject']}")
            if results['filters']['module']:
                filters.append(f"Module: {results['filters']['module']}")
            formatted += f" [Filtered: {', '.join(filters)}]"
        
        formatted += ":\n\n"
        
        for i, (doc, metadata, distance) in enumerate(zip(
            results['documents'], 
            results['metadatas'], 
            results['distances']
        ), 1):
            similarity = (1 - distance) * 100
            formatted += f"{i}. 📚 {metadata['subject']} → {metadata['module']}\n"
            formatted += f"   📄 {metadata['file_name']} (Page {metadata['page_number']})\n"
            formatted += f"   📏 Relevance: {similarity:.1f}%\n"
            formatted += f"   📝 Content: {doc[:200]}...\n\n"
        
        return formatted
    
    def build_context_prompt(self, question: str, results: dict) -> str:
        """Build a comprehensive context prompt for LLMs."""
        if not results or results['total_results'] == 0:
            return f"Question: {question}\n\nNo relevant context found."
        
        context = "Based on the following engineering documents, please answer the question accurately and comprehensively.\n\n"
        context += "RELEVANT DOCUMENT EXCERPTS:\n"
        
        for i, (doc, metadata) in enumerate(zip(results['documents'], results['metadatas']), 1):
            context += f"\n--- Excerpt {i} from {metadata['subject']} → {metadata['module']} ---\n"
            context += f"Source: {metadata['file_name']} (Page {metadata['page_number']})\n"
            context += f"Content: {doc}\n"
        
        context += f"\nQUESTION: {question}\n"
        context += "ANSWER:"
        
        return context
    
    def show_organization(self):
        """Display the current organizational structure."""
        org_info = self.rag.get_organization_info()
        file_structure = org_info['file_structure']
        
        print("\n📁 CURRENT DOCUMENT ORGANIZATION:")
        print("=" * 60)
        
        if not file_structure:
            print("No documents found in the data directory.")
            return
        
        for subject, modules in file_structure.items():
            print(f"\n📂 {subject}/")
            for module, files in modules.items():
                print(f"   ├── {module}/")
                for file in files:
                    print(f"   │   ├── {file}")
            print(f"   └── ...")
        
        print(f"\n📊 Total: {len(file_structure)} subjects, {sum(len(modules) for modules in file_structure.values())} modules")
    
    def interactive_session(self):
        """Run interactive Q&A session with local/cloud AI options."""
        print("\n" + "="*80)
        print("🧠 ATHENA — YOUR AI STUDY PARTNER")
        print("="*80)
        print("💡 I understand PDFs, pyqs, notes & textbooks.")
        print("📚 Using all documents in your organized library")
        print(f"🤖 Local LLM: {'✅ ENABLED' if self.ai.local_llm else '❌ DISABLED'}")
        print(f"☁️  Cloud LLM: {'✅ ENABLED' if self.ai.cloud_llm else '❌ DISABLED'}")
        print("\n🔧 Available Commands:")
        print("   • Ask any question - I'll search and answer automatically")
        print("   • 'local' - Use local AI for next question")
        print("   • 'cloud' - Use cloud AI for next question") 
        print("   • 'subjects' - Show all loaded subjects and modules")
        print("   • 'filter subject:NAME' - Focus on specific subject")
        print("   • 'filter module:NAME' - Focus on specific module") 
        print("   • 'clear filters' - Search all documents")
        print("   • 'show sources' - Toggle source visibility on/off")
        print("   • 'stats' - Show system information")
        print("   • 'quit' - End the session")
        print("="*80)
        
        current_filters = {'subject': None, 'module': None}
        show_sources = True
        use_cloud = CONFIG.get("use_cloud_by_default", False)
        
        while True:
            try:
                # Show current status
                filter_display = ""
                if current_filters['subject']:
                    filter_display = f" [Focus: {current_filters['subject']}"
                    if current_filters['module']:
                        filter_display += f" → {current_filters['module']}"
                    filter_display += "]"
                
                mode_display = "☁️ CLOUD" if use_cloud else "💻 LOCAL"
                user_input = input(f"\n❓ Ask anything [{mode_display}]{filter_display}: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n📚 Good luck with your exam preparation! 🍀")
                    break
                
                elif user_input.lower() == 'stats':
                    stats = self.rag.get_collection_stats()
                    pdf_files = get_pdf_files_recursive(self.data_dir)
                    print(f"\n📊 System Statistics:")
                    print(f"   • PDF Files: {len(pdf_files)}")
                    print(f"   • Knowledge Chunks: {stats['total_chunks']}")
                    print(f"   • Subjects: {len(stats['subjects'])}")
                    print(f"   • Modules: {len(stats['modules'])}")
                    print(f"   • Current Mode: {'Cloud' if use_cloud else 'Local'}")
                    continue
                
                elif user_input.lower() == 'subjects':
                    self.show_organization()
                    continue
                
                elif user_input.lower() == 'local':
                    use_cloud = False
                    print("✅ Now using LOCAL AI mode")
                    continue
                
                elif user_input.lower() == 'cloud':
                    if self.ai.cloud_llm:
                        use_cloud = True
                        print("✅ Now using CLOUD AI mode")
                    else:
                        print("❌ Cloud AI not available. Set GOOGLE_API_KEY to enable.")
                    continue
                
                elif user_input.lower().startswith('filter subject:'):
                    subject_name = user_input[15:].strip()
                    current_filters['subject'] = subject_name if subject_name else None
                    print(f"✅ Now focusing on: {subject_name}")
                    continue
                
                elif user_input.lower().startswith('filter module:'):
                    module_name = user_input[14:].strip()
                    current_filters['module'] = module_name if module_name else None
                    print(f"✅ Now focusing on: {module_name}")
                    continue
                
                elif user_input.lower() == 'clear filters':
                    current_filters = {'subject': None, 'module': None}
                    print("✅ Now searching all documents")
                    continue
                
                elif user_input.lower() == 'show sources':
                    show_sources = not show_sources
                    print(f"✅ Source visibility: {'ON' if show_sources else 'OFF'}")
                    continue
                
                elif not user_input:
                    continue
                
                # AUTO-ANSWER with local/cloud choice
                print("\n" + "🔍" + "─" * 78)
                print(f"🤖 Thinking... ({'Cloud' if use_cloud else 'Local'})")
                
                # Perform search with filters
                results = self.rag.search(
                    user_input, 
                    n_results=8,
                    subject_filter=current_filters['subject'],
                    module_filter=current_filters['module']
                )
                
                # Generate answer
                if results['total_results'] > 0:
                    context_prompt = self.build_context_prompt(user_input, results)
                    
                    answer = self.ai.generate_answer(user_input, context_prompt, use_cloud=use_cloud)
                    print("\n" + "=" * 80)
                    print(f"🎯 ANSWER FROM YOUR DOCUMENTS ({'CLOUD' if use_cloud else 'LOCAL'}):")
                    print("=" * 80)
                    print(answer)
                    
                    if show_sources:
                        print("\n" + "📚 SOURCES USED:")
                        print("-" * 40)
                        print(self.format_search_results(results))
                    
                else:
                    print("\n❌ No relevant information found in your documents.")
                    if current_filters['subject'] or current_filters['module']:
                        print("💡 Try 'clear filters' to search all documents")
                
                print("🔍" + "─" * 78)
                
            except KeyboardInterrupt:
                print("\n\n⏹️ Session interrupted. Goodbye!")
                break
            except Exception as e:
                logger.error(f"Error during interaction: {e}")
                print(f"❌ An error occurred: {e}")

def main():
    """Main application entry point."""
    # Check for Gemini API key
    gemini_api_key = os.getenv('GOOGLE_API_KEY')
    
    app = AthenaApp(gemini_api_key=gemini_api_key)
    
    # Check if data directory has files
    pdf_files = get_pdf_files_recursive("./data")
    if not pdf_files:
        print("❌ No PDF files found in './data' directory.")
        print("💡 Please organize your PDF files like this:")
        print("   data/")
        print("   ├── CAD_CAM/")
        print("   │   ├── 2D_Transformations/")
        print("   │   │   └── transformation_problems.pdf")
        print("   │   └── CNC_Programming/")
        print("   │       └── g_code_examples.pdf")
        print("   └── Machine_Design/")
        print("       └── Shafts/")
        print("           └── shaft_design.pdf")
        return
    
    # Show file organization
    print("📁 Detected File Organization:")
    subjects = {}
    for file_info in pdf_files:
        subject = file_info['subject']
        if subject not in subjects:
            subjects[subject] = set()
        subjects[subject].add(file_info['module'])
    
    for subject, modules in subjects.items():
        print(f"   📂 {subject}/")
        for module in modules:
            module_files = [f for f in pdf_files if f['subject'] == subject and f['module'] == module]
            print(f"      ├── {module}/ ({len(module_files)} files)")
    
    # Initialize RAG system
    if not app.initialize_rag():
        return
    
    # Start interactive session
    app.interactive_session()

if __name__ == "__main__":
    main()