# flask_api_server.py - FIXED: Proper exception handling

import os
import logging
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from dotenv import load_dotenv
from typing import Dict, Any, Tuple

from config import get_config, paths
from exceptions import QueryError, LLMError, RAGError  # ADDED

load_dotenv()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(paths.get_log_file("athena_api"), encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

config = get_config()

# Import Athena app
try:
    from main import AthenaApp
except Exception as e:
    logger.exception("Failed to import AthenaApp from main.py: %s", e)
    raise

# Flask app
app = Flask(__name__)
CORS(app)

# Instantiate Athena system
SYSTEM = AthenaApp(
    data_dir=str(config.data_dir),
    gemini_api_key=os.getenv("GOOGLE_API_KEY")
)

# Initialize RAG at startup
try:
    logger.info("Initializing RAG at server start...")
    SYSTEM.initialize_rag()
    logger.info("RAG initialized successfully")
    logger.info(f"Query service available: {SYSTEM.query_service is not None}")
except Exception as e:
    logger.warning("RAG failed at startup: %s", e)


def _validate_json_request(required: list, payload: dict):
    """Validate required fields in JSON request"""
    missing = [k for k in required if k not in payload or payload.get(k) in (None, "")]
    if missing:
        abort(400, description=f"Missing required fields: {', '.join(missing)}")


@app.route("/api/ask", methods=["POST"])
def ask_question() -> Tuple[Dict[str, Any], int]:
    """
    Answer a question using RAG.
    FIXED: Proper exception handling with specific HTTP status codes
    
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
        use_cloud = bool(data.get("use_cloud", config.use_cloud_by_default))
        subject = data.get("subject")
        module = data.get("module")

        logger.info("API /api/ask - len=%d use_cloud=%s subject=%s module=%s",
                    len(question), use_cloud, subject, module)

        # Ensure RAG and query service are initialized
        if SYSTEM.rag is None or SYSTEM.query_service is None:
            logger.info("Query service not initialized; initializing now")
            if not SYSTEM.initialize_rag():
                return jsonify({"error": "RAG initialization failed"}), 500

        if not SYSTEM.query_service:
            return jsonify({"error": "Query service not available"}), 500

        # Execute query using the service - FIXED: Catch specific exceptions
        try:
            result = SYSTEM.query_service.execute_query(
                question=question,
                use_cloud=use_cloud,
                subject_filter=subject,
                module_filter=module
            )
        except LLMError as e:
            # FIXED: Return 503 Service Unavailable for LLM errors
            logger.error(f"LLM error: {e}")
            return jsonify({
                "error": "LLM service unavailable",
                "message": str(e),
                "type": "LLMError"
            }), 503
        
        except RAGError as e:
            # FIXED: Return 500 for RAG system errors
            logger.error(f"RAG error: {e}")
            return jsonify({
                "error": "Search system error",
                "message": str(e),
                "type": "RAGError"
            }), 500
        
        except QueryError as e:
            # FIXED: Return 400 for bad query errors
            logger.error(f"Query error: {e}")
            return jsonify({
                "error": "Query execution failed",
                "message": str(e),
                "type": "QueryError"
            }), 400

        # Return standardized response
        return jsonify({
            "answer": result.answer,
            "cached": result.cached,
            "mode": result.mode,
            "sources": [s.to_dict() for s in result.sources],
            "total_sources": result.total_sources
        }), 200

    except ValueError as e:
        # FIXED: Return 400 for validation errors
        logger.warning(f"Validation error: {e}")
        return jsonify({
            "error": "Invalid request",
            "message": str(e)
        }), 400
    
    except Exception as e:
        # FIXED: Log and return 500 for unexpected errors
        logger.exception("Unexpected error in /api/ask")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@app.route("/api/stats", methods=["GET"])
def get_stats() -> Tuple[Dict[str, Any], int]:
    """Get database statistics"""
    try:
        if SYSTEM.rag is None:
            return jsonify({"error": "RAG not initialized"}), 500

        stats = SYSTEM.rag.get_collection_stats()
        return jsonify({"status": "ok", "stats": stats}), 200

    except Exception as e:
        logger.exception("Error /api/stats")
        return jsonify({"error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health_check() -> Tuple[Dict[str, Any], int]:
    """Health check endpoint"""
    try:
        total_chunks = None
        if SYSTEM.rag:
            try:
                total_chunks = SYSTEM.rag.get_collection_stats().get("total_chunks")
            except Exception:
                total_chunks = None

        return jsonify({
            "status": "healthy",
            "local_llm": SYSTEM.ai.has_local_llm(),
            "cloud_llm": SYSTEM.ai.has_cloud_llm(),
            "total_chunks": total_chunks,
            "query_service_available": SYSTEM.query_service is not None
        }), 200

    except Exception:
        return jsonify({"status": "unhealthy"}), 500


@app.route("/api/reload", methods=["POST"])
def reload_index() -> Tuple[Dict[str, Any], int]:
    """
    Re-ingest documents with optional admin key.
    """
    try:
        admin_key = config.api_key_for_admin

        if admin_key:
            data = request.get_json(silent=True) or {}
            if data.get("api_key") != admin_key:
                return jsonify({"error": "invalid api_key"}), 403

        logger.info("Rebuilding DB via /api/reload")
        SYSTEM.rag.clear_database()
        SYSTEM.rag.ingest_directory(str(config.data_dir), rebuild_bm25=True)

        return jsonify({
            "status": "reloaded",
            "total_chunks": SYSTEM.rag.get_collection_stats().get("total_chunks")
        }), 200

    except Exception as e:
        logger.exception("Error /api/reload")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    host = config.server_host
    port = config.server_port
    debug = config.server_debug

    logger.info("Starting Athena API server on %s:%s", host, port)
    app.run(host=host, port=port, debug=debug)