import os
import sys
import logging
import json
from pathlib import Path
from main import AthenaApp, get_pdf_files_recursive
from local_rag import create_rag_system
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load config
CONFIG = json.load(open(Path(__file__).parent / "config.json"))
USE_CLOUD_DEFAULT = CONFIG.get("use_cloud_by_default", False)

class PYQAutoSolver:
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.app = AthenaApp(data_dir)
        self.use_cloud = USE_CLOUD_DEFAULT
        
    def set_cloud_mode(self, use_cloud: bool):
        """Set whether to use cloud AI for solving."""
        self.use_cloud = use_cloud
        mode = "CLOUD" if use_cloud else "LOCAL"
        print(f"🔧 Auto-solver mode set to: {mode}")
        
    def extract_questions_from_pdf(self):
        """Extract all questions from the indexed PDF."""
        print("📖 Extracting all questions from CADCAM PYQ PDF...")
        
        # Search for question patterns in the document
        question_patterns = [
            "Explain concurrent engineering with neat figure",
            "What is Adaptive Control (AC)",
            "Explain Z-buffer Algorithm with figure",
            "Construct a B-spline curve",
            "Write a C++ program for",
            "Explain Generative CAPP & CAQC",
            "Formulate a CNC program",
            "Explain Design for Assembly (DFA)",
            "Triangle.*vertices.*reflect",
            "Write Short Notes on"
        ]
        
        all_questions = []
        
        for pattern in question_patterns:
            print(f"   🔍 Searching for: {pattern}")
            results = self.app.rag.search(pattern, n_results=10)
            
            for doc, metadata in zip(results['documents'], results['metadatas']):
                # Extract complete questions from the text
                questions = self._extract_complete_questions(doc)
                all_questions.extend(questions)
                
            time.sleep(1)  # Avoid rate limiting
        
        # Remove duplicates
        unique_questions = list(set(all_questions))
        print(f"🎯 Found {len(unique_questions)} unique questions")
        return unique_questions
    
    def _extract_complete_questions(self, text: str):
        """Extract complete questions from document text."""
        questions = []
        
        # Split by common question indicators
        lines = text.split('\n')
        current_question = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Question indicators
            if any(indicator in line for indicator in ['Explain', 'What is', 'Describe', 'Write', 'Calculate', 'Construct', 'Formulate']):
                if current_question:
                    questions.append(current_question.strip())
                current_question = line
            elif current_question and len(line) > 10:  # Continue multi-line questions
                current_question += " " + line
            elif len(line) > 50:  # Standalone questions
                questions.append(line)
        
        if current_question:
            questions.append(current_question.strip())
            
        return [q for q in questions if len(q) > 20]  # Filter out short fragments
    
    def solve_all_questions(self):
        """Solve all extracted questions automatically."""
        mode = "CLOUD" if self.use_cloud else "LOCAL"
        print(f"🚀 Starting Auto-Solver for CADCAM PYQs... [{mode} MODE]")
        print("=" * 80)
        
        # Initialize RAG system
        if not self.app.initialize_rag():
            print("❌ Failed to initialize RAG system")
            return
        
        # Extract questions
        questions = self.extract_questions_from_pdf()
        
        if not questions:
            print("❌ No questions found in the PDF")
            return
        
        print(f"\n🎯 Solving {len(questions)} questions automatically...")
        print("=" * 80)
        
        # Solve each question
        for i, question in enumerate(questions, 1):
            print(f"\n📝 QUESTION {i}/{len(questions)}:")
            print(f"   {question}")
            print("-" * 60)
            
            try:
                # Auto-answer the question
                answer = self.app.auto_answer_question(question, use_cloud=self.use_cloud)
                print(f"🤖 ANSWER [{mode}]:")
                print(answer)
                
                # Save to file
                self._save_answer(i, question, answer, mode)
                
                print("✅ Saved to solutions.txt")
                print("=" * 80)
                
            except Exception as e:
                print(f"❌ Error solving question {i}: {e}")
                self._save_answer(i, question, f"ERROR: {e}", "ERROR")
            
            time.sleep(2)  # Be nice to the API
    
    def _save_answer(self, q_num: int, question: str, answer: str, mode: str):
        """Save question and answer to file."""
        with open("solutions.txt", "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"QUESTION {q_num} [MODE: {mode}]:\n")
            f.write(f"{question}\n")
            f.write(f"{'='*80}\n")
            f.write(f"ANSWER:\n")
            f.write(f"{answer}\n")
            f.write(f"{'='*80}\n\n")
    
    def solve_specific_categories(self):
        """Solve questions by category."""
        categories = {
            "2D Transformations": [
                "Triangle.*reflect.*line",
                "Rectangle.*rotated.*vertex",
                "transformation matrix",
                "reflection about line"
            ],
            "CAD Algorithms": [
                "Z-buffer algorithm",
                "Cohen Sutherland algorithm", 
                "Bresenhams algorithm",
                "Bezier curve properties",
                "B-spline curve"
            ],
            "CAM Concepts": [
                "Adaptive Control",
                "Concurrent engineering",
                "Generative CAPP",
                "CAQC",
                "Design for Assembly",
                "Computer Integrated Manufacturing"
            ],
            "CNC Programming": [
                "G81 canned cycle",
                "G83 canned cycle", 
                "G76 cycle",
                "CNC program",
                "tool length compensation"
            ],
            "C++ Programming": [
                "C++ program for line",
                "Bresenhams line algorithm",
                "Bezier curve program",
                "2D transformations program"
            ]
        }
        
        mode = "CLOUD" if self.use_cloud else "LOCAL"
        print(f"🎯 Solving questions by category... [{mode} MODE]")
        
        for category, patterns in categories.items():
            print(f"\n📂 CATEGORY: {category}")
            print("-" * 50)
            
            for pattern in patterns:
                results = self.app.rag.search(pattern, n_results=5)
                if results['total_results'] > 0:
                    question = results['documents'][0][:200] + "..."
                    print(f"   🔍 Pattern: {pattern}")
                    answer = self.app.auto_answer_question(question, use_cloud=self.use_cloud)
                    print(f"   🤖 Answer preview: {answer[:100]}...")
                    
                    # Save category solutions
                    with open("category_solutions.txt", "a", encoding="utf-8") as f:
                        f.write(f"\n{'='*50}\n")
                        f.write(f"CATEGORY: {category} [MODE: {mode}]\n")
                        f.write(f"PATTERN: {pattern}\n")
                        f.write(f"QUESTION: {question}\n")
                        f.write(f"ANSWER: {answer}\n")

def main():
    """Main function to run the auto-solver."""
    print("🎓 CADCAM PYQ AUTO-SOLVER - ENHANCED")
    print("🚀 This will solve ALL questions from your PYQ PDF automatically!")
    print(f"🔧 Default mode: {'CLOUD' if USE_CLOUD_DEFAULT else 'LOCAL'}")
    print("⏰ Estimated time: 10-15 minutes for complete solution set")
    print("=" * 80)
    
    solver = PYQAutoSolver()
    
    # Check if PDF exists
    pdf_files = get_pdf_files_recursive()
    if not pdf_files:
        print("❌ No PDF files found. Please add your CADCAM PYQ PDF to the data folder.")
        return
    
    print("📚 Found PDF files:")
    for pdf in pdf_files:
        print(f"   📄 {pdf['file_name']} ({pdf['subject']} → {pdf['module']})")
    
    # Ask user preference
    print("\n🔧 Choose solving mode:")
    print("   1. Solve ALL questions (Comprehensive)")
    print("   2. Solve by categories (Organized)")
    print("   3. Switch to LOCAL mode (Current: CLOUD)" if USE_CLOUD_DEFAULT else "   3. Switch to CLOUD mode (Current: LOCAL)")
    
    try:
        choice = input("   Enter choice (1, 2, or 3): ").strip()
        
        if choice == "1":
            solver.solve_all_questions()
        elif choice == "2":
            solver.solve_specific_categories()
        elif choice == "3":
            # Toggle cloud mode
            new_mode = not USE_CLOUD_DEFAULT
            solver.set_cloud_mode(new_mode)
            print(f"\n🔄 Restart the script to use {'CLOUD' if new_mode else 'LOCAL'} mode")
        else:
            print("❌ Invalid choice. Running comprehensive mode...")
            solver.solve_all_questions()
            
    except KeyboardInterrupt:
        print("\n⏹️ Auto-solver stopped by user.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()