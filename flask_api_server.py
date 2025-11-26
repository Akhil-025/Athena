import os
import logging
import json
from pathlib import Path
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

# logging
LOGFILE = "athena_api.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOGFILE, encoding="utf-8")]
)
logger = logging.getLogger(__name__)

# Load config
CONFIG_PATH = Path(__file__).parent / "config.json"
if not CONFIG_PATH.exists():
    logger.error("config.json not found at %s", CONFIG_PATH)
    raise SystemExit("Missing config.json")
CONFIG = json.load(open(CONFIG_PATH))

# Import your metadata + RAG app
try:
    from main import AthenaApp
except Exception as e:
    logger.exception("Failed to import AthenaApp from main.py: %s", e)
    raise

# Flask app
app = Flask(__name__)
CORS(app)  # enable cross-origin

# Instantiate Athena system
SYSTEM = AthenaApp(gemini_api_key=os.getenv("GOOGLE_API_KEY"))

# Initialize RAG at startup
try:
    logger.info("Initializing RAG at server start...")
    SYSTEM.initialize_rag()
    logger.info("RAG initialized successfully")
except Exception as e:
    logger.warning("RAG failed at startup: %s", e)


def _validate_json_request(required: list, payload: dict):
    missing = [k for k in required if k not in payload or payload.get(k) in (None, "")]
    if missing:
        abort(400, description=f"Missing required fields: {', '.join(missing)}")


@app.route("/api/ask", methods=["POST"])
def ask_question():
    """
    POST body JSON:
    {
      "question": "string",
      "use_cloud": false,
      "subject": "...",
      "module": "..."
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        _validate_json_request(["question"], data)

        question = data["question"].strip()
        use_cloud = bool(data.get("use_cloud", CONFIG.get("use_cloud_by_default", False)))
        subject = data.get("subject")
        module = data.get("module")

        logger.info("API /api/ask - len=%d use_cloud=%s subject=%s module=%s",
                    len(question), use_cloud, subject, module)

        # RAG search
        rag = SYSTEM.rag
        if rag is None:
            logger.info("RAG not initialized; initializing now")
            if not SYSTEM.initialize_rag():
                return jsonify({"error": "RAG initialization failed"}), 500

        results = rag.search(
            question,
            n_results=8,
            subject_filter=subject,
            module_filter=module
        )

        if results.get("total_results", 0) == 0:
            return jsonify({
                "answer": None,
                "cached": False,
                "sources": [],
                "message": "No relevant information found"
            }), 200

        # Build context prompt
        context_prompt = SYSTEM.build_context_prompt(question, results)

        # Cache logic
        from utils.llm_cache import question_hash, load_cached_answer, save_cached_answer

        context_ids = [
            m.get("file_name", "") + f":{i}"
            for i, m in enumerate(results["metadatas"])
        ]
        qh = question_hash(question, context_ids)

        cached = load_cached_answer(qh)
        if cached:
            logger.info("Returning cached answer for %s", qh)
            return jsonify({
                "answer": cached.get("answer"),
                "cached": True,
                "mode": cached.get("mode", "local"),
                "sources": cached.get("sources", [])  # full objects stored now
            }), 200

        # Generate LLM answer
        answer = SYSTEM.ai.generate_answer(question, context_prompt, use_cloud=use_cloud)

        # Build YOUR SOURCE OBJECTS for frontend
        source_objects = [
            {
                "file_name": m.get("file_name"),
                "file_path": m.get("file_path"),
                "page": m.get("page_number"),
                "text": doc,
                "score": m.get("score", 0)
            }
            for doc, m in zip(results["documents"], results["metadatas"])
        ]

        # Save to cache (store full source objects)
        save_cached_answer(
            qh,
            {
                "answer": answer,
                "sources": source_objects,
                "mode": "cloud" if use_cloud else "local"
            }
        )

        # Return final payload
        return jsonify({
            "answer": answer,
            "cached": False,
            "mode": "cloud" if use_cloud else "local",
            "sources": source_objects
        }), 200

    except Exception as e:
        logger.exception("Error in /api/ask")
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats", methods=["GET"])
def get_stats():
    try:
        rag = SYSTEM.rag
        if rag is None:
            return jsonify({"error": "RAG not initialized"}), 500

        stats = rag.get_collection_stats()
        return jsonify({"status": "ok", "stats": stats}), 200

    except Exception as e:
        logger.exception("Error /api/stats")
        return jsonify({"error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health_check():
    try:
        rag = SYSTEM.rag
        total_chunks = None
        if rag:
            try:
                total_chunks = rag.get_collection_stats().get("total_chunks")
            except Exception:
                total_chunks = None

        return jsonify({
            "status": "healthy",
            "local_llm": bool(SYSTEM.ai.local_llm),
            "cloud_llm": bool(SYSTEM.ai.cloud_llm),
            "total_chunks": total_chunks,
            "mode": "local-first"
        }), 200

    except Exception:
        return jsonify({"status": "unhealthy"}), 500


@app.route("/api/reload", methods=["POST"])
def reload_index():
    """
    Re-ingest documents with optional admin key.
    """
    try:
        admin_key = CONFIG.get("server", {}).get("api_key_for_admin") or os.getenv("ATHENA_ADMIN_KEY")

        if admin_key:
            data = request.get_json(silent=True) or {}
            if data.get("api_key") != admin_key:
                return jsonify({"error": "invalid api_key"}), 403

        logger.info("Rebuilding DB via /api/reload")
        SYSTEM.rag.clear_database()
        SYSTEM.rag.ingest_directory("./data", rebuild_bm25=True)

        return jsonify({
            "status": "reloaded",
            "total_chunks": SYSTEM.rag.get_collection_stats().get("total_chunks")
        }), 200

    except Exception as e:
        logger.exception("Error /api/reload")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    host = CONFIG.get("server", {}).get("host", "127.0.0.1")
    port = CONFIG.get("server", {}).get("port", 5000)
    debug = CONFIG.get("server", {}).get("debug", False)

    logger.info("Starting Athena API server on %s:%s", host, port)
    app.run(host=host, port=port, debug=debug)
