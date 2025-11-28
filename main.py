# main.py 
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

from config import get_config, paths   
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
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        engine = config.local_model_engine.lower()
        self.local_llm = None
        self.cloud_llm = None

        # Local LLM selection
        if engine == "ollama":
            if OllamaLLM is None:
                logger.warning("Ollama wrapper not found (llm_wrappers/llm_ollama.py).")
            else:
                try:
                    self.local_llm = OllamaLLM(model=config.ollama_model)
                    logger.info("Initialized Ollama local LLM.")
                except Exception as e:
                    logger.warning("Ollama initialization failed: %s", e)
                    self.local_llm = None

        elif engine == "llama-cpp":
            try:
                self.local_llm = LocalLLM(
                    model_path=config.local_model_path,
                    max_tokens=config.max_tokens,
                    n_ctx=config.n_ctx,
                    temperature=config.temperature,
                )
                logger.info("Initialized llama-cpp local LLM.")
            except Exception as e:
                logger.warning("llama-cpp init failed: %s", e)
                self.local_llm = None
        else:
            logger.info("⚠️ No valid local LLM configured.")

        # Cloud LLM setup
        if self.api_key:
            try:
                self.cloud_llm = CloudLLM(
                    api_key=self.api_key,
                    model=config.cloud_model,
                    max_output_tokens=config.max_tokens
                )
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
                max_chunks=config.max_chunks_cloud,
                max_chars=config.max_chunk_chars_cloud
            )

            ctx_text = "\n\n".join([f"Source {i+1} ({c['source']}):\n{c['text']}" 
                                    for i, c in enumerate(safe_ctx)])

            prompt = (
                f"You are Athena — an expert AI study partner.\n"
                f"Use ONLY the provided context.\n\n"
                f"CONTEXT:\n{ctx_text}\n\n"
                f"QUESTION: {question}\n\nANSWER:"
            )

            res = self.cloud_llm.generate(prompt, timeout=config.llm_timeout)
            return res.get("text", str(res))

        if self.local_llm:
            logger.info("Using local LLM")
            prompt = (
                f"You are an expert engineering tutor.\n"
                f"Use the context to answer.\n\n"
                f"CONTEXT:\n{context}\n\nQUESTION: {question}\n\nANSWER:"
            )
            res = self.local_llm.generate(prompt, timeout=config.llm_timeout)
            return res.get("text", str(res))

        return "❌ No LLM available. Enable local or cloud LLM."


class AthenaApp:
    def __init__(self, data_dir: str = "./data", gemini_api_key: str = None):
        self.data_dir = data_dir
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
        sample_structure = config.sample_structure
        for subject, modules in sample_structure.items():
            for module in modules:
                os.makedirs(os.path.join(self.data_dir, subject, module), exist_ok=True)

        logger.info("Sample folder structure created under %s", self.data_dir)
        print("📂 Sample folders created. Add PDFs and re-run.")

    def initialize_rag(self):
        logger.info("Initializing RAG...")

        self.rag = MergedLocalRAG(
            persist_directory=config.chroma_persist_dir,
            model_name=config.embedding_model,
            embed_batch_size=config.embed_batch_size,
            enable_bm25=config.enable_bm25
        )

        stats = self.rag.get_collection_stats()

        if stats.get("total_chunks", 0) == 0 or config.reload_on_start:
            logger.info("No chunks found or reload requested — ingesting directory")
            self.rag.ingest_directory(self.data_dir, rebuild_bm25=True)
        else:
            logger.info("Using existing DB with %d chunks", stats.get("total_chunks", 0))

        return True

    def auto_answer_question(self, question: str, subject_filter: str = None, module_filter: str = None, use_cloud: bool = False) -> str:
        results = self.rag.search(question, subject_filter=subject_filter, module_filter=module_filter)

        if results.get("total_results", 0) == 0:
            return "❌ No relevant information found."

        context = self.build_context_prompt(question, results)

        # Caching
        context_ids = [m.get("file_name", "") + f":{i}" for i, m in enumerate(results["metadatas"])]
        qh = question_hash(question, context_ids)

        cached = load_cached_answer(qh)
        if cached:
            logger.info("Using cached answer")
            return cached.get("answer")

        answer = self.ai.generate_answer(question, context, use_cloud=use_cloud)
        save_cached_answer(qh, {
            "answer": answer,
            "sources": [m.get("file_name", "unknown") for m in results["metadatas"]]
        })

        return answer


    def build_context_prompt(self, question: str, results: dict) -> str:
        if results.get("total_results", 0) == 0:
            return f"Question: {question}\n\nNo relevant context found."

        ctx = []
        for i, (doc, md) in enumerate(zip(results["documents"], results["metadatas"]), 1):
            header = (
                f"--- Excerpt {i}: {md.get('file_name','unknown')} | {md.get('subject','?')} "
                f"→ {md.get('module','?')} (Page {md.get('page_number','?')}) ---"
            )
            ctx.append(f"{header}\n{doc}")

        return (
            "Answer based on the excerpts below.\n\n"
            + "\n\n".join(ctx)
            + f"\n\nQUESTION: {question}\nANSWER:"
        )


    def format_search_results(self, results: dict) -> str:
        if results.get("total_results", 0) == 0:
            return "❌ No results found."

        lines = [f"🔍 Found {results['total_results']} relevant sections:"]
        docs = results.get("documents", [])
        mds = results.get("metadatas", [])

        for i, (d, md) in enumerate(zip(docs, mds), 1):
            snippet = d[:200].replace("\n", " ")
            lines.append(
                f"{i}. {md.get('subject','Unknown')} → {md.get('module','General')} | "
                f"{md.get('file_name','unknown')} (Page {md.get('page_number','?')})\n   {snippet}..."
            )

        return "\n\n".join(lines)


    def interactive_session(self):
        if not self.rag:
            self.initialize_rag()

        print("\n🧠 ATHENA — Interactive mode (type 'quit' to exit)\n")

        current_filters = {"subject": None, "module": None}
        use_cloud = config.use_cloud_default

        while True:
            try:
                mode_display = "☁️ CLOUD" if use_cloud else "💻 LOCAL"
                inp = input(f"\n❓ [{mode_display}] Ask: ").strip()

                if inp.lower() in ("quit", "exit", "q"):
                    break

                if inp == "":
                    continue

                results = self.rag.search(inp, subject_filter=current_filters["subject"], module_filter=current_filters["module"])
                if results.get("total_results", 0) == 0:
                    print("❌ No relevant sections found.")
                    continue

                context = self.build_context_prompt(inp, results)
                answer = self.ai.generate_answer(inp, context, use_cloud=use_cloud)

                print("\n" + "=" * 60)
                print("ANSWER:\n")
                print(answer)

                if config.show_sources:
                    print("\nSOURCES:\n")
                    print(self.format_search_results(results))

                print("=" * 60)

            except KeyboardInterrupt:
                print("\nInterrupted. Goodbye.")
                break

            except Exception as e:
                logger.exception("Error during interactive loop: %s", e)
                print("⚠️ Error:", e)


def main():
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
