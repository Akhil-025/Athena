# /utils/llm_cache.py
import os, json, hashlib
from pathlib import Path

# Windows-compatible path handling
CACHE_DIR = Path(".\\cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def question_hash(question: str, context_ids: list):
    key = question + "|" + "|".join(context_ids or [])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()

def load_cached_answer(qhash: str):
    f = CACHE_DIR / f"{qhash}.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Cache read error: {e}")
            return None
    return None

def save_cached_answer(qhash: str, payload: dict):
    f = CACHE_DIR / f"{qhash}.json"
    try:
        f.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Cache write error: {e}")