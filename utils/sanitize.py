# /utils/sanitize.py
import re, html
from typing import List, Dict

EMAIL_RE = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
PHONE_RE = re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?(?:\d{2,4}[-.\s]?){2,4}\d{2,4}\b')

def sanitize_chunk_text(text: str, max_chars: int) -> str:
    t = html.unescape(text)
    t = EMAIL_RE.sub("[REDACTED_EMAIL]", t)
    t = PHONE_RE.sub("[REDACTED_PHONE]", t)
    if len(t) > max_chars:
        t = t[:max_chars].rsplit(" ", 1)[0] + " ... [TRUNCATED]"
    return t

def prepare_context_for_cloud(chunks: List[Dict], max_chunks: int = 3, max_chars: int = 1500):
    chosen = chunks[:max_chunks]
    out = []
    for c in chosen:
        out.append({"source": c.get("source", "unknown"), "text": sanitize_chunk_text(c.get("text", ""), max_chars)})
    return out