"""
Pedagogy Backend Configuration

Application settings loaded from environment variables.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List
import os


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
        "https://tauri.localhost"  # Tauri production (alternative)
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
    OMNIPARSER_ENABLE_CAPTIONING: bool = True

    # Legacy YOLO v11 Settings (fallback if OmniParser not available)
    YOLO_MODEL_PATH: str = "yolo11n.pt"
    YOLO_CONFIDENCE_THRESHOLD: float = 0.5
    YOLO_IOU_THRESHOLD: float = 0.45

    # EasyOCR Settings
    OCR_LANGUAGE: str = "en"
    OCR_USE_GPU: bool = False
    OCR_CONFIDENCE_THRESHOLD: float = 0.6

    # CV Processing Settings
    CV_MAX_IMAGE_SIZE_MB: int = 10
    CV_SUPPORTED_FORMATS: List[str] = ["png", "jpg", "jpeg", "bmp", "webp"]
    CV_DEFAULT_RESIZE_WIDTH: int = 1920
    CV_DEFAULT_RESIZE_HEIGHT: int = 1080

    # =============================================
    # AI Guidance Engine Configuration (Phase 6)
    # =============================================

    # LLM Provider: "ollama" (local/free) or "openai" (cloud/paid)
    LLM_PROVIDER: str = "ollama"

    # Ollama Settings (Local LLM - primary)
    # Install: https://ollama.ai then run: ollama pull llama3.2
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # OpenAI Settings (cloud fallback)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1"
    OPENAI_MAX_TOKENS: int = 1024
    OPENAI_TEMPERATURE: float = 0.3

    # Guidance Generation Settings
    GUIDANCE_MAX_STEPS: int = 20
    GUIDANCE_MATCH_THRESHOLD: float = 0.6  # Min similarity for element matching
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
