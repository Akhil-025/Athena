# auto_solver.py

import os
import time
import json
import re
from pathlib import Path
from typing import List, Dict, Optional
import logging
from main import AthenaApp
from pdf_processor import get_pdf_files_recursive
from config import get_config
from config import paths  


logger = logging.getLogger(__name__)

config = get_config()
USE_CLOUD_DEFAULT = config.use_cloud_by_default


class UniversalQuestionExtractor:
    """Intelligent question extraction from any question paper format"""
    
    # Comprehensive question patterns for various subjects
    QUESTION_PATTERNS = [
        # Direct question formats
        r'^\s*(?:Q\.?|Question)\s*\d+[:\.\)]\s*(.+?)(?=(?:Q\.?|Question)\s*\d+|$)',
        r'^\s*\d+[\.\)]\s*(.+?)(?=^\s*\d+[\.\)]|$)',
        
        # Command-based questions (common in technical subjects)
        r'\b(Explain|Describe|Define|Discuss|Compare|Differentiate|Derive|Prove|Calculate|Compute|Evaluate|Analyze|Illustrate|Draw|Sketch|Design|Write|List|State|Solve|Find|Determine)\b.{10,}?[.?]',
        
        # Academic-style questions
        r'(?:What|How|Why|When|Where|Which)\s+(?:is|are|do|does|can|could|would|should).{10,}?[?]',
        
        # "With respect to" style questions
        r'With\s+(?:respect\s+to|reference\s+to|regard\s+to).{10,}?[.?]',
        
        # OR questions (multiple parts)
        r'.{20,}?\s+OR\s+.{20,}?[.?]',
    ]
    
    # Subject-specific markers for context
    SUBJECT_INDICATORS = {
        'mathematics': ['equation', 'theorem', 'proof', 'derivative', 'integral', 'matrix', 'vector'],
        'physics': ['force', 'energy', 'momentum', 'wave', 'particle', 'field', 'quantum'],
        'chemistry': ['reaction', 'compound', 'element', 'molecule', 'bond', 'acid', 'base'],
        'engineering': ['design', 'circuit', 'system', 'algorithm', 'structure', 'analysis'],
        'computer_science': ['algorithm', 'program', 'database', 'network', 'code', 'function'],
        'biology': ['cell', 'organism', 'evolution', 'gene', 'protein', 'tissue'],
        'economics': ['market', 'demand', 'supply', 'price', 'cost', 'production'],
        'management': ['strategy', 'organization', 'leadership', 'planning', 'control'],
    }
    
    def __init__(self):
        self.compiled_patterns = [re.compile(p, re.MULTILINE | re.IGNORECASE | re.DOTALL) 
                                  for p in self.QUESTION_PATTERNS]
    
    def detect_subject(self, text: str) -> Optional[str]:
        """Detect the likely subject based on keywords"""
        text_lower = text.lower()
        subject_scores = {}
        
        for subject, keywords in self.SUBJECT_INDICATORS.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                subject_scores[subject] = score
        
        if subject_scores:
            return max(subject_scores, key=subject_scores.get)
        return None
    
    def clean_question(self, text: str) -> str:
        """Clean and normalize extracted question text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page numbers, headers, footers
        text = re.sub(r'Page\s+\d+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\d+\s+of\s+\d+', '', text)
        
        # Remove marks/points indicators
        text = re.sub(r'\[\s*\d+\s*(?:marks?|points?)\s*\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\(\s*\d+\s*(?:marks?|points?)\s*\)', '', text, flags=re.IGNORECASE)
        
        # Remove "OR" dividers (but keep the question)
        text = re.sub(r'\s+OR\s+', ' OR ', text)
        
        return text.strip()
    
    def extract_questions_from_text(self, text: str) -> List[Dict[str, str]]:
        """Extract all questions from text using multiple strategies"""
        questions = []
        seen = set()
        
        # Strategy 1: Pattern-based extraction
        for pattern in self.compiled_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                question_text = match.group(0) if match.lastindex is None else match.group(1)
                cleaned = self.clean_question(question_text)
                
                if self._is_valid_question(cleaned) and cleaned not in seen:
                    questions.append({
                        'text': cleaned,
                        'method': 'pattern',
                        'confidence': 'high'
                    })
                    seen.add(cleaned)
        
        # Strategy 2: Numbered list detection
        numbered_questions = self._extract_numbered_questions(text)
        for q in numbered_questions:
            if q['text'] not in seen:
                questions.append(q)
                seen.add(q['text'])
        
        # Strategy 3: Section-based extraction (for structured papers)
        section_questions = self._extract_section_questions(text)
        for q in section_questions:
            if q['text'] not in seen:
                questions.append(q)
                seen.add(q['text'])
        
        return questions
    
    def _extract_numbered_questions(self, text: str) -> List[Dict[str, str]]:
        """Extract questions from numbered lists (1. 2. 3. etc.)"""
        questions = []
        lines = text.split('\n')
        current_question = ""
        question_number = None
        
        for line in lines:
            # Check if line starts with a number
            match = re.match(r'^\s*(\d+)[\.\)]\s*(.+)', line)
            if match:
                # Save previous question if exists
                if current_question:
                    cleaned = self.clean_question(current_question)
                    if self._is_valid_question(cleaned):
                        questions.append({
                            'text': cleaned,
                            'number': question_number,
                            'method': 'numbered',
                            'confidence': 'high'
                        })
                
                # Start new question
                question_number = match.group(1)
                current_question = match.group(2)
            elif current_question:
                # Continue current question
                current_question += " " + line.strip()
        
        # Don't forget the last question
        if current_question:
            cleaned = self.clean_question(current_question)
            if self._is_valid_question(cleaned):
                questions.append({
                    'text': cleaned,
                    'number': question_number,
                    'method': 'numbered',
                    'confidence': 'high'
                })
        
        return questions
    
    def _extract_section_questions(self, text: str) -> List[Dict[str, str]]:
        """Extract questions from section-based papers (Section A, B, C, etc.)"""
        questions = []
        
        # Split by sections
        section_pattern = r'(?:SECTION|Section|PART|Part)\s+[A-Z]'
        sections = re.split(section_pattern, text, flags=re.IGNORECASE)
        
        for section in sections:
            # Look for question markers within section
            q_pattern = r'(?:Q\.|Question)\s*\d+[:\.\)]?\s*(.+?)(?=(?:Q\.|Question)\s*\d+|$)'
            matches = re.finditer(q_pattern, section, re.MULTILINE | re.DOTALL)
            
            for match in matches:
                question_text = match.group(1)
                cleaned = self.clean_question(question_text)
                
                if self._is_valid_question(cleaned):
                    questions.append({
                        'text': cleaned,
                        'method': 'section',
                        'confidence': 'medium'
                    })
        
        return questions
    
    def _is_valid_question(self, text: str) -> bool:
        """Validate if extracted text is likely a question"""
        if not text or len(text) < 20:
            return False
        
        if len(text) > 1000:  # Too long, probably not a single question
            return False
        
        # Must have some alphabetic content
        if not re.search(r'[a-zA-Z]{3,}', text):
            return False
        
        # Exclude common non-question content
        exclude_patterns = [
            r'^(?:Page|Figure|Table|Diagram|Image)\s+\d+',
            r'^(?:Time|Duration|Total Marks):',
            r'^(?:Instructions?|Note|Guidelines?):',
            r'^(?:UNIVERSITY|COLLEGE|DEPARTMENT)',
        ]
        
        for pattern in exclude_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return False
        
        return True


class UniversalAutoSolver:
    """Universal solver for any question paper"""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = paths.data_dir
        self.app = AthenaApp(data_dir)
        self.extractor = UniversalQuestionExtractor()
        self.use_cloud = USE_CLOUD_DEFAULT
        
    def set_cloud_mode(self, use_cloud: bool):
        """Toggle between local and cloud LLM"""
        self.use_cloud = use_cloud
        mode = "CLOUD ☁️" if use_cloud else "LOCAL 💻"
        print(f"Solver mode: {mode}")
    
    def analyze_question_paper(self, pdf_path: str) -> Dict:
        """Analyze a question paper and extract metadata"""
        print(f"\n📄 Analyzing: {os.path.basename(pdf_path)}")
        
        # Initialize RAG if needed
        if not self.app.rag:
            self.app.initialize_rag()
        
        # Extract text from PDF
        from pdf_processor import PDFProcessor
        processor = PDFProcessor()
        pages = processor.extract_text_from_pdf(pdf_path)
        
        if not pages:
            return {'error': 'Failed to extract text from PDF'}
        
        # Combine all page text
        full_text = "\n".join([p['text'] for p in pages])
        
        # Extract questions
        questions = self.extractor.extract_questions_from_text(full_text)
        
        # Detect subject
        subject = self.extractor.detect_subject(full_text)
        
        # Extract metadata from filename and content
        filename = os.path.basename(pdf_path)
        metadata = self._extract_metadata(filename, full_text)
        
        analysis = {
            'file': pdf_path,
            'filename': filename,
            'total_pages': len(pages),
            'total_questions': len(questions),
            'questions': questions,
            'detected_subject': subject,
            'metadata': metadata,
            'preview': full_text[:500]
        }
        
        return analysis
    
    def _extract_metadata(self, filename: str, text: str) -> Dict:
        """Extract metadata like year, semester, course from filename and content"""
        metadata = {}
        
        # Extract year
        year_match = re.search(r'\b(20\d{2}|19\d{2})\b', filename + " " + text[:500])
        if year_match:
            metadata['year'] = year_match.group(1)
        
        # Extract semester/term
        sem_match = re.search(r'(?:Semester|Sem|Term)\s*[:-]?\s*(\d+|[IVX]+)', 
                             filename + " " + text[:500], re.IGNORECASE)
        if sem_match:
            metadata['semester'] = sem_match.group(1)
        
        # Extract course code
        code_match = re.search(r'\b([A-Z]{2,4}\s*\d{3,4})\b', filename + " " + text[:500])
        if code_match:
            metadata['course_code'] = code_match.group(1)
        
        return metadata
    
    def solve_question_paper(self, pdf_path: str, output_file: Optional[str] = None,
                           subject_filter: Optional[str] = None,
                           module_filter: Optional[str] = None):
        """Solve all questions in a question paper"""
        print("\n" + "="*80)
        print("🎯 UNIVERSAL QUESTION PAPER SOLVER")
        print("="*80)
        
        # Analyze the paper
        analysis = self.analyze_question_paper(pdf_path)
        
        if 'error' in analysis:
            print(f"❌ Error: {analysis['error']}")
            return
        
        # Display analysis
        print(f"\n📊 Analysis:")
        print(f"   • File: {analysis['filename']}")
        print(f"   • Pages: {analysis['total_pages']}")
        print(f"   • Questions found: {analysis['total_questions']}")
        print(f"   • Detected subject: {analysis['detected_subject'] or 'Unknown'}")
        
        if analysis['metadata']:
            print(f"   • Metadata: {analysis['metadata']}")
        
        questions = analysis['questions']
        
        if not questions:
            print("\n⚠️  No questions found in the PDF.")
            print("   The PDF might be:")
            print("   - Image-based (needs OCR)")
            print("   - Using an unusual format")
            print("   - Not actually a question paper")
            return
        
        # Confirm before solving
        proceed = input(f"\n❓ Proceed to solve {len(questions)} questions? (y/n): ").strip().lower()
        if proceed != 'y':
            print("Cancelled.")
            return
        
        # Setup output file
        if not output_file:
            base_name = os.path.splitext(analysis['filename'])[0]
            output_file = f"{base_name}_solutions.txt"
        
        # Initialize RAG
        if not self.app.initialize_rag():
            print("❌ Failed to initialize RAG")
            return
        
        # Solve questions
        print(f"\n🚀 Starting to solve questions...")
        print(f"   Mode: {'☁️  CLOUD' if self.use_cloud else '💻 LOCAL'}")
        print(f"   Output: {output_file}\n")
        
        self._write_header(output_file, analysis)
        
        solved = 0
        failed = 0
        
        for i, q_data in enumerate(questions, 1):
            question = q_data['text']
            print(f"\n[{i}/{len(questions)}] Solving...")
            print(f"Q: {question[:100]}{'...' if len(question) > 100 else ''}")
            
            try:
                # Get answer
                answer = self.app.auto_answer_question(
                    question,
                    subject_filter=subject_filter or analysis.get('detected_subject'),
                    module_filter=module_filter,
                    use_cloud=self.use_cloud
                )
                
                # Save answer
                self._save_answer(output_file, i, question, answer, q_data)
                
                print(f"✅ Solved")
                solved += 1
                
                # Rate limiting
                time.sleep(1 if self.use_cloud else 0.5)
                
            except Exception as e:
                logger.exception(f"Error solving question {i}")
                self._save_answer(output_file, i, question, f"❌ ERROR: {str(e)}", q_data)
                print(f"❌ Failed: {str(e)}")
                failed += 1
        
        # Summary
        print("\n" + "="*80)
        print("📊 SUMMARY")
        print("="*80)
        print(f"   ✅ Solved: {solved}")
        print(f"   ❌ Failed: {failed}")
        print(f"   📄 Output: {output_file}")
        print("="*80 + "\n")
    
    def _write_header(self, output_file: str, analysis: Dict):
        """Write header section to output file"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("AUTOMATED SOLUTION SHEET\n")
            f.write("Generated by Athena Universal Auto-Solver\n")
            f.write("="*80 + "\n\n")
            f.write(f"Question Paper: {analysis['filename']}\n")
            f.write(f"Total Questions: {analysis['total_questions']}\n")
            f.write(f"Detected Subject: {analysis.get('detected_subject', 'Unknown')}\n")
            
            if analysis.get('metadata'):
                f.write(f"Metadata: {analysis['metadata']}\n")
            
            f.write(f"Solved using: {'Cloud LLM' if self.use_cloud else 'Local LLM'}\n")
            f.write(f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n" + "="*80 + "\n\n")
    
    def _save_answer(self, output_file: str, q_num: int, question: str, 
                    answer: str, q_data: Dict):
        """Save individual answer to file"""
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write("\n" + "="*80 + "\n")
            f.write(f"QUESTION {q_num}\n")
            
            if q_data.get('number'):
                f.write(f"Original Number: {q_data['number']}\n")
            
            f.write(f"Extraction Method: {q_data.get('method', 'unknown')}\n")
            f.write(f"Confidence: {q_data.get('confidence', 'unknown')}\n")
            f.write("-"*80 + "\n")
            f.write(f"{question}\n")
            f.write("-"*80 + "\n")
            f.write("ANSWER:\n\n")
            f.write(f"{answer}\n")
            f.write("="*80 + "\n")
    
    def batch_solve_directory(self, directory: str = None):
        """Solve all question papers in a directory"""
        if directory is None:
            directory = input("Enter directory path containing question papers: ").strip()
        
        if not os.path.exists(directory):
            print(f"❌ Directory not found: {directory}")
            return
        
        # Find all PDFs
        pdf_files = []
        for root, _, files in os.walk(directory):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
        
        if not pdf_files:
            print(f"❌ No PDF files found in {directory}")
            return
        
        print(f"\n📚 Found {len(pdf_files)} PDF files")
        print("\nFiles:")
        for i, pdf in enumerate(pdf_files, 1):
            print(f"  {i}. {os.path.basename(pdf)}")
        
        proceed = input(f"\n❓ Solve all {len(pdf_files)} papers? (y/n): ").strip().lower()
        if proceed != 'y':
            print("Cancelled.")
            return
        
        # Solve each paper
        for i, pdf_path in enumerate(pdf_files, 1):
            print(f"\n{'='*80}")
            print(f"Processing {i}/{len(pdf_files)}")
            print(f"{'='*80}")
            
            try:
                self.solve_question_paper(pdf_path)
            except Exception as e:
                logger.exception(f"Failed to process {pdf_path}")
                print(f"❌ Failed: {str(e)}")
            
            if i < len(pdf_files):
                time.sleep(2)  # Brief pause between papers


def main():
    print("\n" + "="*80)
    print("🎓 ATHENA UNIVERSAL QUESTION PAPER AUTO-SOLVER")
    print("="*80)
    print("\nThis tool can solve question papers from ANY subject!")
    print("It automatically detects questions and provides detailed answers.\n")
    
    solver = UniversalAutoSolver()
    
    # Check for indexed documents
    pdfs = get_pdf_files_recursive(solver.data_dir)
    if pdfs:
        print(f"📚 Found {len(pdfs)} indexed documents in knowledge base:")
        subjects = {}
        for p in pdfs:
            subj = p['subject']
            subjects[subj] = subjects.get(subj, 0) + 1
        for subj, count in subjects.items():
            print(f"   • {subj}: {count} file(s)")
    else:
        print("⚠️  No documents in knowledge base.")
        print("   Add reference materials to ./data/ for better answers.")
    
    print("\n" + "-"*80)
    print("OPTIONS:")
    print("  1. Solve a single question paper")
    print("  2. Batch solve all papers in a directory")
    print("  3. Change LLM mode (current: {})".format("CLOUD ☁️" if solver.use_cloud else "LOCAL 💻"))
    print("-"*80)
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == '1':
        pdf_path = input("\nEnter path to question paper PDF: ").strip()
        if os.path.exists(pdf_path):
            solver.solve_question_paper(pdf_path)
        else:
            print(f"❌ File not found: {pdf_path}")
    
    elif choice == '2':
        solver.batch_solve_directory()
    
    elif choice == '3':
        mode = input("Use CLOUD (c) or LOCAL (l)? ").strip().lower()
        solver.set_cloud_mode(mode == 'c')
        print("\nReturning to main menu...")
        time.sleep(1)
        main()  # Restart menu
    
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    main()