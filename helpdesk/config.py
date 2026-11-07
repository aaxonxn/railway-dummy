"""Central configuration for Railway Passenger Help Desk."""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "rail_capstone_pack"
DOCUMENTS_DIR = DATA_DIR / "documents"
DATABASE_DIR = DATA_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "rail_timetable.db"
QUESTIONS_DIR = DATA_DIR / "questions"
SAMPLE_QUESTIONS_PATH = QUESTIONS_DIR / "sample_questions.json"

INDEX_DIR = PROJECT_ROOT / "index"
EVAL_DIR = PROJECT_ROOT / "eval"
LOGS_DIR = PROJECT_ROOT / "logs"

# Ensure essential output directories exist
INDEX_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Config:
    """Application configuration parameters."""

    # Gemini API configuration
    gemini_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    )
    gemini_timeout_sec: float = 30.0
    gemini_max_retries: int = 3

    # Tesseract OCR configuration
    tesseract_cmd: str = field(
        default_factory=lambda: os.getenv(
            "TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )
    )
    ocr_dpi: int = 300
    ocr_min_text_chars: int = 50  # Pages with fewer chars trigger OCR

    # Embedding & Retrieval
    embedding_model_name: str = "all-MiniLM-L6-v2"
    local_model_path: Optional[str] = field(
        default_factory=lambda: r"C:\Users\aaxon\.cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2\snapshots\c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
        if Path(
            r"C:\Users\aaxon\.cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2\snapshots\c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
        ).exists()
        else None
    )
    chunk_size_chars: int = 800
    chunk_overlap_chars: int = 150
    retrieval_top_k: int = 5
    rrf_k: int = 60
    dense_weight: float = 0.5
    bm25_weight: float = 0.5

    # SQL Engine configuration
    sql_max_rows: int = 50
    sql_timeout_sec: float = 5.0

    # Paths
    project_root: Path = PROJECT_ROOT
    data_dir: Path = DATA_DIR
    documents_dir: Path = DOCUMENTS_DIR
    database_path: Path = DATABASE_PATH
    index_dir: Path = INDEX_DIR
    logs_dir: Path = LOGS_DIR


config = Config()

