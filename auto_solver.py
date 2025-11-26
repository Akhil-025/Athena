# auto_solver.py 

import os
import time
import json
from pathlib import Path
import logging

from main import AthenaApp
from pdf_processor import get_pdf_files_recursive

logger = logging.getLogger(__name__)
CONFIG = json.load(open(Path(__file__).parent / "config.json"))
USE_CLOUD_DEFAULT = CONFIG.get("use_cloud_by_default", False)

class PYQAutoSolver:
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.app = AthenaApp(data_dir)
        self.use_cloud = USE_CLOUD_DEFAULT

    def set_cloud_mode(self, use_cloud: bool):
        self.use_cloud = use_cloud
        print("Auto-solver mode:", "CLOUD" if use_cloud else "LOCAL")

    def extract_questions_from_pdf(self):
        print("Scanning indexed documents for likely questions...")
        # small curated patterns to find question-like lines
        patterns = ["Explain", "What is", "Describe", "Write", "Calculate", "Construct", "Formulate"]
        all_qs = []
        # ensure RAG initialized
        self.app.initialize_rag()
        # naive approach: search for common keywords across indexed chunks
        for pattern in ["Explain", "What is", "Write", "Formulate", "Construct"]:
            results = self.app.rag.search(pattern, n_results=20)
            for doc_text in results.get("documents", []):
                qs = self._extract_complete_questions(doc_text)
                all_qs.extend(qs)
            time.sleep(0.5)
        unique = list(dict.fromkeys(all_qs))  # keep order, deduplicate
        print(f"Found {len(unique)} candidate questions")
        return unique

    def _extract_complete_questions(self, text: str):
        lines = text.split(".")
        cand = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if any(line.lower().startswith(k.lower()) for k in ["explain", "what is", "describe", "write", "construct", "formulate", "calculate"]):
                cand.append(line if line.endswith("?") or len(line) > 30 else line)
        return [c for c in cand if len(c) > 20]

    def solve_all_questions(self):
        print("Starting auto-solver...")
        if not self.app.initialize_rag():
            print("Failed to initialize RAG")
            return
        questions = self.extract_questions_from_pdf()
        if not questions:
            print("No questions found")
            return
        for i, q in enumerate(questions, 1):
            print(f"\nQUESTION {i}/{len(questions)}: {q}")
            try:
                ans = self.app.auto_answer_question(q, use_cloud=self.use_cloud)
                print("ANSWER:\n", ans[:1000])
                self._save_answer(i, q, ans)
            except Exception as e:
                logger.exception("Error while solving: %s", e)
                self._save_answer(i, q, f"ERROR: {e}")
            time.sleep(1)

    def _save_answer(self, q_num: int, question: str, answer: str):
        out = "solutions.txt"
        with open(out, "a", encoding="utf-8") as f:
            f.write("\n" + "="*80 + "\n")
            f.write(f"QUESTION {q_num}:\n{question}\n")
            f.write("-"*80 + "\n")
            f.write(f"ANSWER:\n{answer}\n")
            f.write("="*80 + "\n")
        logger.info("Saved answer %d to %s", q_num, out)

    def solve_specific_categories(self):
        categories = {
            "2D Transformations": ["Triangle.*reflect.*line", "transformation matrix", "reflection about line"],
            "CAD Algorithms": ["Z-buffer algorithm", "Bezier", "B-spline"],
            "CAM Concepts": ["Adaptive Control", "Concurrent engineering", "Design for Assembly"],
            "CNC Programming": ["G81", "G83", "G76", "tool length compensation"]
        }
        if not self.app.initialize_rag():
            return
        for cat, patterns in categories.items():
            print(f"\nCATEGORY: {cat}")
            for p in patterns:
                res = self.app.rag.search(p, n_results=5)
                if res.get("total_results", 0) > 0:
                    question = res["documents"][0][:200] + "..."
                    answer = self.app.auto_answer_question(question, use_cloud=self.use_cloud)
                    print(f"Pattern: {p} → Answer preview: {answer[:200]}...")
                    with open("category_solutions.txt", "a", encoding="utf-8") as fh:
                        fh.write(f"\n{'='*50}\nCATEGORY: {cat}\nPATTERN: {p}\nQUESTION: {question}\nANSWER:\n{answer}\n")

def main():
    print("CADCAM PYQ AUTO-SOLVER")
    solver = PYQAutoSolver()
    pdfs = get_pdf_files_recursive(solver.data_dir)
    if not pdfs:
        print("No PDFs found. Add them to data/ and re-run.")
        return
    print("Found PDFs:")
    for p in pdfs:
        print(f" - {p['file_name']} ({p['subject']} / {p['module']})")
    choice = input("1: Solve ALL, 2: Solve by categories. Choose (1/2): ").strip()
    if choice == "1":
        solver.solve_all_questions()
    elif choice == "2":
        solver.solve_specific_categories()
    else:
        print("Invalid choice; exiting.")

if __name__ == "__main__":
    main()
