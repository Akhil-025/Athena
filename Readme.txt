# Athena — Your AI Study Partner  
Reads PDFs, Solves Questions, and Explains Anything

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![RAG](https://img.shields.io/badge/RAG-ChromaDB-green)
![LLM](https://img.shields.io/badge/AI-Ollama%2Fllama.cpp%2FGemini-purple)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow)

Athena is a private, local-first AI study assistant that reads your learning materials, finds answers, and explains concepts clearly using Retrieval-Augmented Generation (RAG).  
Currently optimized for **PDFs**, with planned support for **DOCX, PPTX, EPUB, MD, TXT, scanned PDFs, and LaTeX**.

---

## ✨ Features

- 📚 **Reads your documents** and answers from them (local offline RAG)
- 🤖 **AI Solver** for PYQ-style questions from PDFs
- 💻 **Local AI support** (Ollama or llama.cpp) with **optional Gemini cloud**
- 🔒 **Privacy-first** — documents never leave your system unless you choose cloud mode
- 🧠 **Adaptive caching** to speed repeated questions
- 🌐 **Multiple interfaces**: CLI, REST API, and Web UI
- 🧹 **PII sanitization** for cloud mode (email/phone removal)

---

## 🚀 Installation (Windows Example)

### 1) Clone repository
```bash
git clone https://github.com/<your-username>/athena.git
cd athena
2) Create & activate virtual environment
powershell
Copy code
python -m venv athena_env
athena_env\Scripts\activate
3) Install dependencies
powershell
Copy code
pip install -r requirements.txt
4) (Optional) Enable cloud AI
Create a .env file:

ini
Copy code
GOOGLE_API_KEY=your_api_key_here
5) Add your PDFs
Place as:

php-template
Copy code
data/<SUBJECT>/<MODULE>/<yourfile.pdf>
6) Run Athena (choose any):
Mode	Command
CLI	run_cli.bat
Web UI	run_ui.bat
REST API	run_api.bat
Auto PYQ Solver	run_autosolver.bat

🗃 Folder Layout
bash
Copy code
Athena/
├── config.json
├── main.py
├── auto_solver.py
├── flask_api_server.py
├── llm_wrappers/
├── utils/
├── frontend/
├── data/            # your private files (gitignored)
├── models/          # local GGML models (optional)
├── .env             # API keys (gitignored)
└── run_*.bat
🧩 Supported Formats
Format	Status	Planned Features
PDF (text)	✅	Chunking + semantic retrieval
DOCX	🔜	Paragraph extraction
PPTX	🔜	Bullet + slide text
TXT / MD	🔜	Heading-aware chunking
EPUB	🔜	Chapter extraction
Scanned PDFs	🔜	OCR (Tesseract + ocrmypdf)
LaTeX / research	🔜	Citation + equation indexing

📌 Full roadmap here → ROADMAP.md

🔐 Privacy
Your documents never leave your machine in local mode.

No analytics, tracking, telemetry.

Sanitization removes emails & phone numbers before cloud fallback.

👨‍💻 Contributing
PRs welcome! Open an issue before large feature proposals.

📜 License
Released under the MIT License. See LICENSE.

📎 Example Uploaded File
File saved in session:
sandbox:/mnt/data/a.txt

