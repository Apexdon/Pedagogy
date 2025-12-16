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

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
