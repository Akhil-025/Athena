"""
Centralized path management for Athena RAG system.
All path constants should be defined here.
"""
from pathlib import Path

# Base directories
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"

# Cache and logs
CACHE_DIR = PROJECT_ROOT / "cache"
LOGS_DIR = PROJECT_ROOT / "logs"

# Database
CHROMA_DB_DIR = PROJECT_ROOT / "chroma_db"

# Configuration
CONFIG_FILE = PROJECT_ROOT / "config.json"

# Ensure critical directories exist
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_log_file(name: str = "athena") -> Path:
    """Get path to a log file"""
    return LOGS_DIR / f"{name}.log"


def get_cache_file(filename: str) -> Path:
    """Get path to a cache file"""
    return CACHE_DIR / filename