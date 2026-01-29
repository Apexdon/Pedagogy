"""
Pedagogy Backend Configuration

Application settings loaded from environment variables.
"""

# CRITICAL: Set these environment variables BEFORE any imports
# PaddleOCR/PaddleX connectivity check can add 10-60 seconds on first load
import os
os.environ['DISABLE_MODEL_SOURCE_CHECK'] = 'True'
os.environ['PADDLEX_NO_CONNECTIVITY_CHECK'] = 'True'
os.environ['GLOG_minloglevel'] = '2'  # Suppress PaddlePaddle verbose logging

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List
import os
from pathlib import Path

# Explicitly load .env file to ensure environment variables are set
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path, override=True)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database - Using SQLite for development (no Docker required)
    # Switch to PostgreSQL when Docker is available
    DATABASE_URL: str = "sqlite+aiosqlite:///./pedagogy.db"
    # For PostgreSQL: "postgresql+asyncpg://pedagogy:pedagogy_secret@localhost:5432/pedagogy"

    # Security
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # API
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # CORS - Origins that can access the API
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",   # Vite dev server (React frontend)
        "http://localhost:3001",   # Vite dev server (alternate port)
        "http://localhost:5173",   # Vite default port
        "http://localhost:1420",   # Tauri dev
        "tauri://localhost",       # Tauri production
        "https://tauri.localhost", # Tauri production (alternative)
        "http://tauri.localhost",  # Tauri production (HTTP)
    ]

    # =============================================
    # RAG System Configuration
    # =============================================

    # ChromaDB Settings
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # Document Processing
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_FILE_TYPES: List[str] = ["pdf", "docx", "md", "markdown", "txt"]

    # Embedding Model
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Chunking Defaults
    DEFAULT_CHUNK_SIZE: int = 500
    DEFAULT_CHUNK_OVERLAP: int = 50
    MIN_CHUNK_SIZE: int = 50

    # RAG Query Defaults
    DEFAULT_TOP_K: int = 5
    DEFAULT_MIN_SIMILARITY: float = 0.7

    # =============================================
    # CV Pipeline Configuration (Phase 4)
    # =============================================

    # UI Detection Backend: "omniparser" (recommended) or "yolo" (legacy)
    CV_DETECTION_BACKEND: str = "omniparser"

    # OmniParser v2 Settings (Microsoft's UI detection model)
    # Download models: huggingface-cli download microsoft/OmniParser-v2.0 --local-dir weights
    OMNIPARSER_ICON_DETECT_PATH: str = "weights/icon_detect/model.pt"
    OMNIPARSER_ICON_CAPTION_PATH: str = "weights/icon_caption_florence"
    OMNIPARSER_CONFIDENCE_THRESHOLD: float = 0.1  # Lower threshold for more detections
    OMNIPARSER_IOU_THRESHOLD: float = 0.45
    OMNIPARSER_ENABLE_CAPTIONING: bool = False  # Disabled - using OCR fusion instead (Florence-2 has _supports_sdpa error)

    # Legacy YOLO v11 Settings (fallback if OmniParser not available)
    YOLO_MODEL_PATH: str = "yolo11n.pt"
    YOLO_CONFIDENCE_THRESHOLD: float = 0.5
    YOLO_IOU_THRESHOLD: float = 0.45

    # OCR Backend Selection: "windows_ocr" (fastest), "surya", "paddleocr", or "easyocr"
    # windows_ocr: ~100-300ms, good accuracy (Windows 10+ native API, best for clean UI text)
    # surya: ~8-15min on CPU (needs GPU), excellent accuracy (transformer-based)
    # paddleocr: ~5-10s, excellent accuracy (uses PaddlePaddle)
    # easyocr: ~1-3s, good accuracy (fallback)
    # auto: tries windows_ocr -> paddleocr -> easyocr
    OCR_BACKEND: str = "paddleocr"

    # Debug Settings
    CV_DEBUG_TIMING: bool = True  # Enable detailed timing logs for CV pipeline

    # Common OCR Settings
    OCR_LANGUAGE: str = "en"
    OCR_USE_GPU: bool = False
    OCR_CONFIDENCE_THRESHOLD: float = 0.4  # Lowered to detect more text (form labels often low contrast)

    # PaddleOCR Settings (used when OCR_BACKEND="paddleocr")
    PADDLEOCR_USE_ANGLE_CLS: bool = False  # Disable for speed (only enable for rotated text)
    PADDLEOCR_USE_OPENVINO: bool = True  # Use OpenVINO for faster OCR inference (~5-10x speedup)
    PADDLEOCR_OPENVINO_DEVICE: str = "CPU"  # OpenVINO device: "CPU", "GPU", or "AUTO"

    # Surya OCR Settings (used when OCR_BACKEND="surya")
    SURYA_OCR_LANGUAGE: str = "en"
    SURYA_OCR_CONFIDENCE_THRESHOLD: float = 0.5

    # Fast OCR Settings (for target verification - uses Tesseract/Windows OCR)
    # Much faster than PaddleOCR (~500-700ms vs ~5-10s) but less accurate
    FAST_OCR_BACKEND: str = "tesseract"  # "tesseract", "windows_ocr", or "paddleocr"
    FAST_OCR_LANGUAGE: str = "eng"  # Tesseract language code
    FAST_OCR_CONFIDENCE_THRESHOLD: float = 0.3
    FAST_OCR_PREFER_WINDOWS: bool = True  # Use Windows OCR if available (Windows 10+)
    TESSERACT_PATH: str = r"C:\Users\GuestMi\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

    # CV Processing Settings
    CV_MAX_IMAGE_SIZE_MB: int = 10
    CV_SUPPORTED_FORMATS: List[str] = ["png", "jpg", "jpeg", "bmp", "webp"]
    CV_DEFAULT_RESIZE_WIDTH: int = 1280  # Higher resolution for better OCR on small text
    CV_DEFAULT_RESIZE_HEIGHT: int = 720   # 720p for balance of speed and accuracy

    # OpenVINO Settings (for YOLO acceleration)
    OMNIPARSER_USE_OPENVINO: bool = False  # Disabled - OpenVINO causes StopIteration error on this system
    OMNIPARSER_OPENVINO_HALF: bool = True  # Use FP16 precision

    # =============================================
    # AI Guidance Engine Configuration (Phase 6)
    # =============================================

    # LLM Provider: "gemini" (cloud/free tier), "ollama" (local), or "openai" (cloud/paid)
    LLM_PROVIDER: str = "gemini"

    # Google Gemini Settings (Primary - free tier with good performance)
    # Get API key from: https://aistudio.google.com/apikey
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"  # Best balance of speed and capability
    GEMINI_MAX_TOKENS: int = 2048
    GEMINI_TEMPERATURE: float = 0.3

    # Ollama Settings (Fallback - local/offline)
    # Install: https://ollama.ai then run: ollama pull llama3.2
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # OpenAI Settings (alternative cloud option)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1"
    OPENAI_MAX_TOKENS: int = 1024
    OPENAI_TEMPERATURE: float = 0.3

    # Guidance Generation Settings
    GUIDANCE_MAX_STEPS: int = 20
    GUIDANCE_MATCH_THRESHOLD: float = 0.45  # Min similarity for element matching
    GUIDANCE_RAG_TOP_K: int = 5  # Number of RAG results to include in context

    # Session Settings
    GUIDANCE_SESSION_TIMEOUT_MINUTES: int = 30
    GUIDANCE_CAPTURES_DIR: str = "./guidance_captures"

    class Config:
        env_file = ".env"
        case_sensitive = True


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()


settings = get_settings()
