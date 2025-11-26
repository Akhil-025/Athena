# main.py 
import os
import sys
import logging
import json
from pathlib import Path
from dotenv import load_dotenv

# Use the merged RAG implementation
from local_rag import MergedLocalRAG

from pdf_processor import get_pdf_files_recursive, get_organization_structure
from utils.sanitize import prepare_context_for_cloud
from utils.llm_cache import question_hash, load_cached_answer, save_cached_answer
from llm_wrappers.llm_local import LocalLLM
from llm_wrappers.llm_cloud import CloudLLM

try:
    from llm_wrappers.llm_ollama import OllamaLLM
except Exception:
    OllamaLLM = None

load_dotenv()

# Configure logging once
LOGFILE = "athena_prep.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOGFILE, encoding="utf-8")]
)
logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config.json"
CONFIG = json.load(open(CONFIG_PATH))

class AIIntegration:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        lm_cfg = CONFIG.get("local_model", {})
        engine = lm_cfg.get("default_engine", "ollama").lower()
        self.local_llm = None
        self.cloud_llm = None

        # Local LLM selection
        if engine == "ollama":
            if OllamaLLM is None:
                logger.warning("Ollama wrapper not found (llm_wrappers/llm_ollama.py).")
            else:
                try:
                    self.local_llm = OllamaLLM(model=lm_cfg.get("ollama_model", "mistral"))
                    logger.info("Initialized Ollama local LLM.")
                except Exception as e:
                    logger.warning("Ollama initialization failed: %s", e)
                    self.local_llm = None

        elif engine == "llama-cpp":
            try:
                self.local_llm = LocalLLM(
                    model_path=lm_cfg.get("model_path", lm_cfg.get("local_model_path", "")),
                    max_tokens=lm_cfg.get("max_tokens", 512),
                    n_ctx=lm_cfg.get("n_ctx", 2048),
                    temperature=lm_cfg.get("temperature", 0.0),
                )
                logger.info("Initialized llama-cpp local LLM.")
            except Exception as e:
                logger.warning("llama-cpp init failed: %s", e)
                self.local_llm = None
        else:
            logger.info("No local LLM configured in config.json (local_model.default_engine)")

        # Cloud LLM
        if self.api_key:
            try:
                self.cloud_llm = CloudLLM(api_key=self.api_key, model=CONFIG.get("cloud_model","gemini-1.5-pro"),
                                          max_output_tokens=lm_cfg.get("max_tokens", 512))
                logger.info("Cloud LLM initialized.")
            except Exception as e:
                logger.warning("Cloud LLM init failed: %s", e)
                self.cloud_llm = None
        else:
            logger.warning("GOOGLE_API_KEY not set; cloud LLM disabled.")

    def generate_answer(self, question: str, context: str, use_cloud: bool = False) -> str:
        """Return LLM response text; prefer cloud if requested and available."""
        if use_cloud and self.cloud_llm:
            logger.info("Using cloud LLM")
            safe_chunks = [{"text": context[:2000], "source": "user_documents"}]
            safe_ctx = prepare_context_for_cloud(
                safe_chunks,
                max_chunks=CONFIG["sanitization"]["max_chunks_sent_to_cloud"],
                max_chars=CONFIG["sanitization"]["max_chunk_chars_sent_to_cloud"]
            )
            ctx_text = "\n\n".join([f"Source {i+1} ({c['source']}):\n{c['text']}" for i, c in enumerate(safe_ctx)])
            prompt = f"You are Athena — an expert AI study partner.\nAnswer using ONLY the provided context.\n\nCONTEXT:\n{ctx_text}\n\nQUESTION: {question}\n\nANSWER:"
            res = self.cloud_llm.generate(prompt, timeout=CONFIG.get("llm_timeout_seconds", 60))
            return res.get("text", str(res))

        if self.local_llm:
            logger.info("Using local LLM")
            prompt = f"You are an expert engineering tutor. Use the context to answer.\n\nCONTEXT:\n{context}\n\nQUESTION: {question}\n\nANSWER:"
            res = self.local_llm.generate(prompt, timeout=CONFIG.get("llm_timeout_seconds", 60))
            return res.get("text", str(res))

        return "❌ No LLM available. Enable local or cloud LLM."

class AthenaApp:
    def __init__(self, data_dir: str = "./data", gemini_api_key: str = None):
        self.data_dir = data_dir
        # Use improved merged rag with BM25 available by default (toggle in config)
        self.rag = None
        self.ai = AIIntegration(gemini_api_key)
        self.setup_data_directory()

    def setup_data_directory(self):
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
            logger.info("Created data directory: %s", self.data_dir)
            self._create_sample_structure()
        return True

    def _create_sample_structure(self):
        sample_structure = {
            "CAD_CAM": ["2D_Transformations", "CNC_Programming", "CAD_Algorithms"],
            "Machine_Design": ["Shafts", "Bearings", "Gears"],
            "Thermodynamics": ["Heat_Transfer", "Cycles"]
        }
        for subject, modules in sample_structure.items():
            for module in modules:
                os.makedirs(os.path.join(self.data_dir, subject, module), exist_ok=True)
        logger.info("Sample folder structure created under %s", self.data_dir)
        print("📂 Sample folders created. Add PDFs to these folders and re-run.")

    def initialize_rag(self):
        logger.info("Initializing RAG...")
        # instantiate MergedLocalRAG from merged_rag.py
        persist = CONFIG.get("chroma_persist_dir", "./chroma_db")
        enable_bm25 = CONFIG.get("enable_bm25", True)
        batch_size = CONFIG.get("embed_batch_size", 32)
        self.rag = MergedLocalRAG(persist_directory=persist,
                                  model_name=CONFIG.get("embedding_model", "all-MiniLM-L6-v2"),
                                  embed_batch_size=batch_size,
                                  enable_bm25=enable_bm25)
        # ingest if empty or reload requested
        stats = self.rag.get_collection_stats()
        if stats.get("total_chunks", 0) == 0 or CONFIG.get("reload_on_start", False):
            logger.info("No chunks found or reload requested — ingesting directory")
            self.rag.ingest_directory(self.data_dir, rebuild_bm25=True)
        else:
            logger.info("Using existing DB with %d chunks", stats.get("total_chunks", 0))
        return True

    def auto_answer_question(self, question: str, subject_filter: str = None, module_filter: str = None, use_cloud: bool = False) -> str:
        print("🔍 Searching documents...")
        results = self.rag.search(question, n_results=8, subject_filter=subject_filter, module_filter=module_filter)
        if results.get("total_results", 0) == 0:
            return "❌ No relevant information found in your documents."

        context = self.build_context_prompt(question, results)
        # caching
        context_ids = [m.get("file_name", "") + f":{i}" for i, m in enumerate(results["metadatas"])]
        qh = question_hash(question, context_ids)
        cached = load_cached_answer(qh)
        if cached:
            logger.info("Using cached answer")
            return cached.get("answer", "Cached result unavailable")

        answer = self.ai.generate_answer(question, context, use_cloud=use_cloud)
        save_cached_answer(qh, {"answer": answer, "sources": [m.get("file_name", "unknown") for m in results["metadatas"]]})
        return answer

    def build_context_prompt(self, question: str, results: dict) -> str:
        if not results or results.get("total_results", 0) == 0:
            return f"Question: {question}\n\nNo relevant context found."

        ctx = []
        for i, (doc, md) in enumerate(zip(results["documents"], results["metadatas"]), 1):
            header = f"--- Excerpt {i}: {md.get('file_name','unknown')} | {md.get('subject','?')} → {md.get('module','?')} (Page {md.get('page_number','?')}) ---"
            ctx.append(f"{header}\n{doc}")
        prompt = "Based on the excerpts below, answer the question succinctly and clearly.\n\n" + "\n\n".join(ctx)
        prompt += f"\n\nQUESTION: {question}\nANSWER:"
        return prompt

    def format_search_results(self, results: dict) -> str:
        if not results or results.get("total_results", 0) == 0:
            return "❌ No results found."
        lines = [f"🔍 Found {results['total_results']} relevant sections:"]
        # handle both hybrid and semantic-only responses
        docs = results.get("documents", [])
        mds = results.get("metadatas", [])
        # distances may be semantic-only; fallback to scores if present
        distances = results.get("distances") or []
        for i, (d, md) in enumerate(zip(docs, mds), 1):
            subjects = md.get("subject", "Unknown")
            module = md.get("module", "General")
            fname = md.get("file_name", "unknown")
            page = md.get("page_number", "?")
            snippet = d[:200].replace("\n", " ")
            lines.append(f"{i}. {subjects} → {module} | {fname} (Page {page})\n   {snippet}...")
        return "\n\n".join(lines)

    # interactive_session and main() logic kept similar to your original but leaner
    def interactive_session(self):
        if not self.rag:
            self.initialize_rag()
        print("\n🧠 ATHENA — Interactive mode (type 'quit' to exit)\n")
        current_filters = {"subject": None, "module": None}
        use_cloud = CONFIG.get("use_cloud_by_default", False)

        while True:
            try:
                mode_display = "☁️ CLOUD" if use_cloud else "💻 LOCAL"
                inp = input(f"\n❓ [{mode_display}] Ask: ").strip()
                if inp.lower() in ("quit", "exit", "q"):
                    break
                if inp.lower() == "stats":
                    stats = self.rag.get_collection_stats()
                    print(f"Chunks: {stats.get('total_chunks',0)} | Subjects: {len(stats.get('subjects',[]))}")
                    continue
                if inp.lower() == "local":
                    use_cloud = False
                    print("Switched to LOCAL mode.")
                    continue
                if inp.lower() == "cloud":
                    use_cloud = True
                    print("Switched to CLOUD mode.")
                    continue
                if inp.lower().startswith("filter subject:"):
                    current_filters["subject"] = inp.split(":",1)[1].strip()
                    print("Applied subject filter.")
                    continue
                if inp.lower().startswith("filter module:"):
                    current_filters["module"] = inp.split(":",1)[1].strip()
                    print("Applied module filter.")
                    continue
                if not inp:
                    continue

                results = self.rag.search(inp, n_results=8, subject_filter=current_filters["subject"], module_filter=current_filters["module"])
                if results.get("total_results",0) == 0:
                    print("❌ No relevant sections found.")
                    continue
                context = self.build_context_prompt(inp, results)
                answer = self.ai.generate_answer(inp, context, use_cloud=use_cloud)
                print("\n" + "="*60)
                print("ANSWER:\n")
                print(answer)
                if CONFIG.get("show_sources_on_answer", True):
                    print("\nSOURCES:\n")
                    print(self.format_search_results(results))
                print("="*60)
            except KeyboardInterrupt:
                print("\nInterrupted. Goodbye.")
                break
            except Exception as e:
                logger.exception("Error during interactive loop: %s", e)
                print("An error occurred:", e)

def main():
    gemini_key = os.getenv("GOOGLE_API_KEY")
    app = AthenaApp(gemini_api_key=gemini_key)
    # ensure PDFs exist
    pdfs = get_pdf_files_recursive(app.data_dir)
    if not pdfs:
        print("No PDFs found in data/. Add files and re-run.")
        return
    app.initialize_rag()
    app.interactive_session()

if __name__ == "__main__":
    main()
