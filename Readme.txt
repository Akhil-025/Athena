🌟 Athena — The Perfect Academic Assistant
Your personal AI that reads, understands, and explains everything you study.








Athena is a private, local-first AI study companion built for students, engineers, researchers, and lifelong learners.
It reads your PDFs, understands your subjects, retrieves relevant knowledge, and gives clear, exam-ready explanations — all directly from your own study materials.

Athena works like the perfect mentor:
calm, patient, precise, and always available.

No cloud required. No data leaks. No limits.

✨ Features
🎓 Academic Intelligence

Learns your subjects and modules automatically

Reads PDFs: textbooks, class notes, hand-written scans (OCR soon)

Answers questions using deep semantic retrieval

Writes explanations like a top professor

🤖 AI Problem Solver

PYQ solver (derivations, theory, numericals)

Step-by-step reasoning

Comparison tables, summaries, breakdowns

Formula extraction + explanation

💻 Local AI — Fast & Private

Works fully offline

Supports:

Ollama

llama.cpp

GGUF/GGML models

No internet needed unless you choose cloud mode

☁️ Cloud Optional (Gemini)

Cloud mode only when you enable it

PII sanitization removes emails/phone numbers

Hybrid local + cloud fallback with confidence threshold

⚡ Performance Engine

Efficient chunking

ChromaDB vector search

Smart caching system

Editable config.json for power users

🌐 Multiple Interfaces

🖥️ Modern Web UI

🔗 REST API (/api/ask, /api/stats, /api/stream)

🖤 Command-line mode

🤖 Auto PYQ solver mode

🚀 Installation (Windows Example)
1) Clone repository
git clone https://github.com/<your-username>/athena.git
cd athena

2) Create & activate virtual environment
python -m venv athena_env
athena_env\Scripts\activate

3) Install backend dependencies
pip install -r requirements.txt

4) (Optional) Enable cloud features

Create .env:

GOOGLE_API_KEY=your_api_key_here

5) Add your study materials

Organize as:

data/<SUBJECT>/<MODULE>/<file.pdf>


Example:

data/CADCAM/Module07/notes.pdf
data/Thermo/Module03/entropy.pdf
data/Math/Module01/linear_algebra.pdf

6) Run Athena
Mode	Command
Web UI	run_ui.bat
CLI assistant	run_cli.bat
REST API server	run_api.bat
Auto PYQ solver	run_autosolver.bat
📸 Screenshots (Recommended)

Replace these with real screenshots once your UI is ready.

🔍 Search from your PDFs

🧠 AI Explanations

📚 Source-linked citations

🗃 Folder Structure
Athena/
├── config.json
├── main.py
├── flask_api_server.py
├── auto_solver.py
├── rag_engine/
├── llm_wrappers/
├── utils/
├── frontend/
│   ├── src/
│   ├── package.json
│   ├── tailwind.config.js
│   └── README.md
├── data/            # your PDFs (gitignored)
├── models/          # LLM models (gitignored)
├── .env             # cloud keys (gitignored)
└── run_*.bat

🧩 Supported File Types
Format	Status	Notes
PDF (text)	✅	Fully supported
DOCX	🔜	Extract paragraphs & headings
PPTX	🔜	Extract bullet points & slide text
TXT / MD	🔜	Heading-aware chunking
EPUB	🔜	Extract chapters
Scanned PDFs	🔜	OCR: Tesseract + OCRmyPDF
LaTeX	🔜	Index formulas + references
🔐 Privacy & Security

Your documents NEVER leave your machine in local mode

No telemetry, no analytics, no tracking

Sanitization removes emails, phone numbers, and PII before cloud fallback

You control when cloud mode is active

Athena is built for privacy-conscious students and researchers.

🧠 Vision

Athena aims to become the perfect academic assistant:

A study partner

A research helper

A solver

A tutor

A librarian

A subject expert

A revision coach

Your entire academic life — centralized, searchable, and understandable.

🤝 Contributing

Pull requests and feature suggestions are welcome!
Please open an issue before proposing major architectural changes.

📜 License

Licensed under the MIT License.