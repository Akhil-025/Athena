"""
LLM response caching utility - now using centralized configuration
"""
import json
import hashlib
from pathlib import Path

from config import get_config, paths

# Get cache directory from config
CACHE_DIR = paths.CACHE_DIR


def question_hash(question: str, context_ids: list) -> str:
    """Generate unique hash for question + context combination"""
    key = question + "|" + "|".join(context_ids or [])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def load_cached_answer(qhash: str):
    """Load cached answer if it exists"""
    cache_file = CACHE_DIR / f"{qhash}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Cache read error: {e}")
            return None
    return None


def save_cached_answer(qhash: str, payload: dict):
    """Save answer to cache"""
    cache_file = CACHE_DIR / f"{qhash}.json"
    try:
        cache_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), 
            encoding="utf-8"
        )
    except Exception as e:
        print(f"Cache write error: {e}")