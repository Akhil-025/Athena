
---

## 📌 **ROADMAP.md**

```markdown
# Athena — Roadmap

## 🎯 Goal
A multimodal, private, local-first RAG assistant that understands all study materials — text, scanned content, equations, presentations, and research papers.

---

### 🏁 Phase 1 — Stabilization (Current)
- Improve PDF text parsing
- Optimize chunking & metadata tags
- Caching & PII sanitization
- Local-first LLM with cloud fallback
- CLI + API + UI integration

---

### 📚 Phase 2 — Multi-Format Import
| Format | Library                  |
|--------|--------------------------|
| DOCX   | python-docx              |
| PPTX   | python-pptx              |
| TXT/MD | md2text + custom parsing |
| EPUB   | ebooklib                 |

- Heading + paragraph aware chunking
- Auto-subject/module classification

---

### 🔎 Phase 3 — OCR & Visual Understanding
|       Feature           |            Tools            |
|-------------------------|-----------------------------|
| OCR for scanned PDFs    | pymupdf, ocrmypdf           |
| Equation OCR            | pix2text / MathPix          |
| Figure/table extraction | camelot, tabula, pdfplumber |

- Store extracted tables & figures as references

---

### 📑 Phase 4 — Research & LaTeX Support
- GROBID / ScienceParse integration
- Metadata extraction (authors, DOI)
- Equation recognition & LaTeX output
- Citation extraction for RAG context

---

### 🧠 Phase 5 — Learning Intelligence
- Automatic concept summaries
- Topic-based quiz generation
- One-click “explain like I’m 5 / exam version”
- Export answers to PDF/Word/Markdown

---

### 🌐 Phase 6 — Deployment & Scaling
- Shared local server instance (LAN mode)
- GPU acceleration (CUDA + llama.cpp)
- Model health scoring and fallback logic

---

### 📌 Future Optional Features
- Voice question input
- Handwritten notes transcription
- Study planner AI + spaced repetition
- Team mode for shared RAG knowledge

---

🛠 Contributions & ideas always welcome!
