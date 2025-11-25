# /flask_api_server.py
from flask import Flask, request, jsonify
from main import AthenaApp
import os
import logging
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize the system
system = AthenaApp(gemini_api_key=os.getenv('GOOGLE_API_KEY'))

@app.route('/api/ask', methods=['POST'])
def ask_question():
    try:
        data = request.json or {}
        question = data.get('question', '').strip()
        use_cloud = bool(data.get('use_cloud', False))
        
        if not question:
            return jsonify({"error": "Question is required"}), 400
        
        # Use the enhanced answer_question method
        answer = system.auto_answer_question(question, use_cloud=use_cloud)
        
        return jsonify({
            "answer": answer,
            "mode": "cloud" if use_cloud else "local"
        })
        
    except Exception as e:
        logging.exception("Error in ask_question")
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        stats = system.rag.get_collection_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "mode": "local-first"})

if __name__ == '__main__':
    print("🚀 Starting Athena API Server...")
    print("💡 Server running at http://127.0.0.1:5000")
    print("🔧 Endpoints:")
    print("   POST /api/ask - Ask questions (include 'use_cloud': true/false in JSON)")
    print("   GET  /api/stats - Get system statistics")
    print("   GET  /api/health - Health check")
    
    app.run(host='127.0.0.1', port=5000, debug=False)