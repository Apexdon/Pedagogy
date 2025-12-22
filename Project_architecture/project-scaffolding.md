# Pedagogy - Project Scaffolding & Implementation Phases

## Project Structure Overview

```
pedagogy/
├── frontend/                    # Tauri + React Frontend
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── store/
│   │   ├── styles/
│   │   └── utils/
│   ├── src-tauri/              # Rust Core
│   │   ├── src/
│   │   └── Cargo.toml
│   ├── package.json
│   └── tauri.conf.json
│
├── backend/                     # Python FastAPI Backend
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── utils/
│   ├── cv_pipeline/            # Computer Vision
│   ├── rag_system/             # RAG Knowledge System
│   ├── tests/
│   ├── requirements.txt
│   └── main.py
│
├── database/                    # Database Scripts
│   ├── migrations/
│   ├── seeds/
│   └── schema.sql
│
├── docs/                        # Documentation
├── scripts/                     # Build & Deploy Scripts
└── docker/                      # Docker Configurations
```

---

## Implementation Phases

```mermaid
gantt
    title Pedagogy Implementation Phases
    dateFormat YYYY-MM-DD
    excludes weekends, 2025-12-25, 2026-01-01

    section Foundation
    Project Setup & Infrastructure     :p1, 2025-12-15, 2025-12-15
    Auth & Organisation Management     :p2, 2025-12-16, 2025-12-17

    section Core Systems
    Knowledge Base & RAG System        :p3, 2025-12-18, 2025-12-19
    Computer Vision Pipeline           :p4, 2025-12-22, 2025-12-23
    Screen Capture & Hotkeys           :p5, 2025-12-24, 2025-12-24

    section AI & UI
    AI Guidance Engine                 :p6, 2025-12-26, 2025-12-29
    Halo Overlay System                :p7, 2025-12-30, 2025-12-30

    section Delivery
    Integration, Testing & Deployment  :p8, 2025-12-31, 2026-01-02
```

---

# Phase 1: Project Setup & Core Infrastructure

## 1.1 Objectives
- Set up development environment
- Initialize project repositories
- Configure database
- Create basic project structure

## 1.2 Directory Structure

```
pedagogy/
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── vite-env.d.ts
│   ├── src-tauri/
│   │   ├── src/
│   │   │   ├── main.rs
│   │   │   └── lib.rs
│   │   ├── Cargo.toml
│   │   ├── tauri.conf.json
│   │   └── build.rs
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── config.py
│   ├── requirements.txt
│   └── .env.example
│
├── database/
│   ├── migrations/
│   │   └── 001_initial_schema.sql
│   └── schema.sql
│
├── .gitignore
├── README.md
└── docker-compose.yml
```

## 1.3 Tasks

### Task 1.3.1: Initialize Frontend (Tauri + React)
```bash
# Create Tauri project with React
npm create tauri-app@latest frontend -- --template react-ts

# Install dependencies
cd frontend
npm install
npm install @tanstack/react-query axios zustand tailwindcss
```

**Files to create:**

`frontend/package.json`
```json
{
  "name": "pedagogy-frontend",
  "version": "0.1.0",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "tauri": "tauri"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@tanstack/react-query": "^5.0.0",
    "axios": "^1.6.0",
    "zustand": "^4.4.0"
  },
  "devDependencies": {
    "@tauri-apps/cli": "^1.5.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "typescript": "^5.0.0",
    "vite": "^5.0.0",
    "@vitejs/plugin-react": "^4.0.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0"
  }
}
```

`frontend/src-tauri/Cargo.toml`
```toml
[package]
name = "pedagogy"
version = "0.1.0"
edition = "2021"

[build-dependencies]
tauri-build = { version = "1.5", features = [] }

[dependencies]
tauri = { version = "1.5", features = ["shell-open", "window-all"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
tokio = { version = "1", features = ["full"] }
reqwest = { version = "0.11", features = ["json"] }
screenshots = "0.8"
```

### Task 1.3.2: Initialize Backend (FastAPI)
```bash
# Create backend directory
mkdir -p backend/app
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install fastapi uvicorn sqlalchemy asyncpg pydantic python-dotenv
```

**Files to create:**

`backend/requirements.txt`
```
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.25
asyncpg==0.29.0
pydantic==2.5.3
pydantic-settings==2.1.0
python-dotenv==1.0.0
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.3.0
python-multipart==0.0.6
httpx==0.26.0
alembic==1.13.1
```

`backend/app/main.py`
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Pedagogy API",
    description="AI Desktop Assistant Backend",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}
```

`backend/app/config.py`
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/pedagogy"
    SECRET_KEY: str = "your-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    class Config:
        env_file = ".env"

settings = Settings()
```

### Task 1.3.3: Database Setup

`database/schema.sql`
```sql
-- Core Tables
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

CREATE TABLE organisations (
    org_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_name VARCHAR(255) NOT NULL,
    org_slug VARCHAR(100) UNIQUE NOT NULL,
    logo_path VARCHAR(500),
    primary_color VARCHAR(7),
    subscription_tier VARCHAR(50) DEFAULT 'free',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organisations(org_id),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user',
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE INDEX idx_users_org ON users(org_id);
CREATE INDEX idx_users_email ON users(email);
```

`docker-compose.yml`
```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: pedagogy_db
    environment:
      POSTGRES_USER: pedagogy
      POSTGRES_PASSWORD: pedagogy_secret
      POSTGRES_DB: pedagogy
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/schema.sql:/docker-entrypoint-initdb.d/schema.sql

volumes:
  postgres_data:
```

## 1.4 Phase 1 Checklist

| Task | Description | Status |
|------|-------------|--------|
| 1.3.1 | Initialize Tauri + React frontend | Pending |
| 1.3.2 | Initialize FastAPI backend | Pending |
| 1.3.3 | Set up PostgreSQL with pgvector | Pending |
| 1.3.4 | Configure Docker Compose | Pending |
| 1.3.5 | Set up Git repository | Pending |
| 1.3.6 | Create basic health check endpoints | Pending |

---

# Phase 2: Authentication & Organisation Management

## 2.1 Objectives
- Implement user authentication (JWT)
- Build organisation registration/onboarding
- Create user management APIs
- Set up role-based access control

## 2.2 Directory Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── organisations.py
│   │   └── users.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py
│   │   └── dependencies.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── organisation.py
│   │   └── user.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── organisation.py
│   │   └── user.py
│   └── services/
│       ├── __init__.py
│       ├── auth_service.py
│       └── org_service.py
```

## 2.3 Tasks

### Task 2.3.1: Authentication Models & Schemas

`backend/app/models/user.py`
```python
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid

class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organisations.org_id"))
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="user")
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default="now()")
    last_login = Column(DateTime)

    organisation = relationship("Organisation", back_populates="users")
```

`backend/app/schemas/auth.py`
```python
from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    org_id: UUID
    invite_code: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int

class TokenPayload(BaseModel):
    sub: UUID
    org_id: UUID
    role: str
    exp: int
```

### Task 2.3.2: Security Module

`backend/app/core/security.py`
```python
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return None
```

### Task 2.3.3: Auth API Endpoints

`backend/app/api/auth.py`
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.auth import UserRegister, UserLogin, Token
from app.services.auth_service import AuthService
from app.core.database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=dict)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    return await service.register_user(user_data)

@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    return await service.authenticate_user(credentials)

@router.post("/logout")
async def logout(
    db: AsyncSession = Depends(get_db)
):
    return {"success": True, "message": "Successfully logged out"}

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    return await service.refresh_tokens(refresh_token)
```

### Task 2.3.4: Organisation Management

`backend/app/api/organisations.py`
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.organisation import OrgRegister, OrgOnboard, OrgProfile
from app.services.org_service import OrgService
from app.core.database import get_db

router = APIRouter(prefix="/org", tags=["Organisation"])

@router.post("/register", response_model=dict)
async def register_organisation(
    org_data: OrgRegister,
    db: AsyncSession = Depends(get_db)
):
    service = OrgService(db)
    return await service.register_organisation(org_data)

@router.post("/onboard", response_model=dict)
async def onboard_organisation(
    onboard_data: OrgOnboard,
    db: AsyncSession = Depends(get_db)
):
    service = OrgService(db)
    return await service.complete_onboarding(onboard_data)

@router.get("/list", response_model=list)
async def list_organisations(
    db: AsyncSession = Depends(get_db)
):
    service = OrgService(db)
    return await service.get_all_organisations()

@router.get("/profile/{org_id}", response_model=OrgProfile)
async def get_organisation_profile(
    org_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = OrgService(db)
    return await service.get_organisation(org_id)
```

## 2.4 Frontend Components

`frontend/src/services/api.ts`
```typescript
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const authApi = {
  register: (data: any) => api.post('/auth/register', data),
  login: (data: any) => api.post('/auth/login', data),
  logout: () => api.post('/auth/logout'),
  refresh: (refreshToken: string) => api.post('/auth/refresh', { refresh_token: refreshToken }),
  me: () => api.get('/auth/me'),
};

export const orgApi = {
  register: (data: any) => api.post('/org/register', data),
  onboard: (data: any) => api.post('/org/onboard', data),
  list: () => api.get('/org/list'),
  profile: (orgId: string) => api.get(`/org/profile/${orgId}`),
};

export default api;
```

## 2.5 Phase 2 Checklist

| Task | Description | Status |
|------|-------------|--------|
| 2.3.1 | Create User & Organisation models | Pending |
| 2.3.2 | Implement JWT security module | Pending |
| 2.3.3 | Build auth API endpoints | Pending |
| 2.3.4 | Build organisation API endpoints | Pending |
| 2.3.5 | Create frontend auth services | Pending |
| 2.3.6 | Build login/register UI components | Pending |
| 2.3.7 | Implement token refresh logic | Pending |
| 2.3.8 | Add role-based access control | Pending |

---

# Phase 3: Knowledge Base & RAG System

## 3.1 Objectives
- Build document upload and processing
- Implement text chunking and embedding
- Set up vector database (ChromaDB/pgvector)
- Create RAG search functionality

## 3.2 Directory Structure

```
backend/
├── rag_system/
│   ├── __init__.py
│   ├── document_parser.py
│   ├── chunker.py
│   ├── embedder.py
│   ├── vector_store.py
│   └── retriever.py
├── app/
│   ├── api/
│   │   └── knowledge.py
│   ├── models/
│   │   ├── knowledge_base.py
│   │   ├── document.py
│   │   └── embedding.py
│   └── services/
│       └── knowledge_service.py
```

## 3.3 Tasks

### Task 3.3.1: Document Parser

`backend/rag_system/document_parser.py`
```python
from abc import ABC, abstractmethod
from pathlib import Path
import fitz  # PyMuPDF
from docx import Document
import markdown

class DocumentParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> str:
        pass

class PDFParser(DocumentParser):
    def parse(self, file_path: str) -> str:
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text

class DocxParser(DocumentParser):
    def parse(self, file_path: str) -> str:
        doc = Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])

class MarkdownParser(DocumentParser):
    def parse(self, file_path: str) -> str:
        with open(file_path, 'r') as f:
            return f.read()

class ParserFactory:
    @staticmethod
    def get_parser(file_path: str) -> DocumentParser:
        ext = Path(file_path).suffix.lower()
        parsers = {
            '.pdf': PDFParser(),
            '.docx': DocxParser(),
            '.md': MarkdownParser(),
        }
        return parsers.get(ext, MarkdownParser())
```

### Task 3.3.2: Text Chunker

`backend/rag_system/chunker.py`
```python
from typing import List
from dataclasses import dataclass

@dataclass
class Chunk:
    content: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: dict

class TextChunker:
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str, metadata: dict = None) -> List[Chunk]:
        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = start + self.chunk_size

            # Find natural break point
            if end < len(text):
                break_point = text.rfind('.', start, end)
                if break_point > start:
                    end = break_point + 1

            chunk_content = text[start:end].strip()

            if chunk_content:
                chunks.append(Chunk(
                    content=chunk_content,
                    chunk_index=chunk_index,
                    start_char=start,
                    end_char=end,
                    metadata=metadata or {}
                ))
                chunk_index += 1

            start = end - self.overlap

        return chunks
```

### Task 3.3.3: Embedding Generator

`backend/rag_system/embedder.py`
```python
from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np

class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()

    def embed_text(self, text: str) -> List[float]:
        embedding = self.model.encode(text)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts)
        return embeddings.tolist()
```

### Task 3.3.4: Vector Store

`backend/rag_system/vector_store.py`
```python
from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import numpy as np

class VectorStore:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def store_embedding(
        self,
        embedding_id: str,
        chunk_id: str,
        index_id: str,
        vector: List[float],
        content: str
    ):
        query = text("""
            INSERT INTO embeddings (embedding_id, chunk_id, index_id, vector, content_preview)
            VALUES (:embedding_id, :chunk_id, :index_id, :vector, :content)
        """)
        await self.db.execute(query, {
            "embedding_id": embedding_id,
            "chunk_id": chunk_id,
            "index_id": index_id,
            "vector": vector,
            "content": content[:200]
        })

    async def search_similar(
        self,
        query_vector: List[float],
        org_id: str,
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        query = text("""
            SELECT e.chunk_id, e.content_preview,
                   1 - (e.vector <=> :query_vector) as similarity
            FROM embeddings e
            JOIN embedding_indexes ei ON e.index_id = ei.index_id
            WHERE ei.org_id = :org_id
            ORDER BY e.vector <=> :query_vector
            LIMIT :top_k
        """)
        result = await self.db.execute(query, {
            "query_vector": query_vector,
            "org_id": org_id,
            "top_k": top_k
        })
        return result.fetchall()
```

### Task 3.3.5: RAG Retriever

`backend/rag_system/retriever.py`
```python
from typing import List, Dict
from .embedder import Embedder
from .vector_store import VectorStore

class RAGRetriever:
    def __init__(self, embedder: Embedder, vector_store: VectorStore):
        self.embedder = embedder
        self.vector_store = vector_store

    async def retrieve(
        self,
        query: str,
        org_id: str,
        top_k: int = 5,
        min_similarity: float = 0.7
    ) -> List[Dict]:
        # Generate query embedding
        query_vector = self.embedder.embed_text(query)

        # Search vector store
        results = await self.vector_store.search_similar(
            query_vector, org_id, top_k
        )

        # Filter by similarity threshold
        filtered_results = [
            {
                "chunk_id": r[0],
                "content": r[1],
                "similarity": r[2]
            }
            for r in results
            if r[2] >= min_similarity
        ]

        return filtered_results
```

### Task 3.3.6: Knowledge API

`backend/app/api/knowledge.py`
```python
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.knowledge_service import KnowledgeService
from app.core.database import get_db
from typing import List

router = APIRouter(prefix="/org", tags=["Knowledge Base"])

@router.post("/upload-knowledge")
async def upload_knowledge(
    org_id: str = Form(...),
    kb_name: str = Form(...),
    kb_description: str = Form(None),
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db)
):
    service = KnowledgeService(db)
    return await service.process_documents(org_id, kb_name, kb_description, files)

@router.post("/query/rag")
async def query_rag(
    query: str,
    org_id: str,
    top_k: int = 5,
    db: AsyncSession = Depends(get_db)
):
    service = KnowledgeService(db)
    return await service.search_knowledge(query, org_id, top_k)
```

## 3.4 Phase 3 Checklist

| Task | Description | Status |
|------|-------------|--------|
| 3.3.1 | Implement document parsers (PDF, DOCX, MD) | Pending |
| 3.3.2 | Build text chunking system | Pending |
| 3.3.3 | Set up SentenceTransformers embedder | Pending |
| 3.3.4 | Implement pgvector storage | Pending |
| 3.3.5 | Build RAG retriever | Pending |
| 3.3.6 | Create knowledge upload API | Pending |
| 3.3.7 | Create RAG search API | Pending |
| 3.3.8 | Build instruction step extractor | Pending |

---

# Phase 4: Computer Vision Pipeline

## 4.1 Objectives
- Set up YOLO V11 for UI element detection
- Implement EasyOCR for text extraction
- Build screen state fusion engine
- Create CV processing API

## 4.2 Directory Structure

```
backend/
├── cv_pipeline/
│   ├── __init__.py
│   ├── preprocessor.py
│   ├── yolo_detector.py
│   ├── ocr_engine.py
│   ├── context_engine.py
│   └── models/
│       └── yolo_ui.pt
```

## 4.3 Tasks

### Task 4.3.1: Image Preprocessor

`backend/cv_pipeline/preprocessor.py`
```python
import cv2
import numpy as np
from PIL import Image
import io
import base64

class ImagePreprocessor:
    def __init__(self, target_width: int = 1920, target_height: int = 1080):
        self.target_width = target_width
        self.target_height = target_height

    def preprocess(self, image_data: bytes) -> np.ndarray:
        # Decode image
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Resize maintaining aspect ratio
        img = self._resize_image(img)

        # Normalize and enhance
        img = self._normalize(img)
        img = self._enhance_contrast(img)

        return img

    def _resize_image(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        scale = min(self.target_width / w, self.target_height / h)
        new_w, new_h = int(w * scale), int(h * scale)
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def _normalize(self, img: np.ndarray) -> np.ndarray:
        return cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)

    def _enhance_contrast(self, img: np.ndarray) -> np.ndarray:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge((l, a, b))
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def decode_base64(self, base64_string: str) -> bytes:
        return base64.b64decode(base64_string)
```

### Task 4.3.2: YOLO UI Detector

`backend/cv_pipeline/yolo_detector.py`
```python
from ultralytics import YOLO
import numpy as np
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class UIElement:
    element_type: str
    bbox: List[int]  # [x1, y1, x2, y2]
    confidence: float

class YOLODetector:
    UI_CLASSES = [
        "button", "input", "checkbox", "dropdown",
        "text", "table", "menu", "modal", "icon", "link"
    ]

    def __init__(self, model_path: str = "cv_pipeline/models/yolo_ui.pt"):
        self.model = YOLO(model_path)

    def detect(self, image: np.ndarray, confidence_threshold: float = 0.5) -> List[UIElement]:
        results = self.model(image, conf=confidence_threshold)

        elements = []
        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = box.conf[0].item()
                cls = int(box.cls[0].item())

                elements.append(UIElement(
                    element_type=self.UI_CLASSES[cls] if cls < len(self.UI_CLASSES) else "unknown",
                    bbox=[int(x1), int(y1), int(x2), int(y2)],
                    confidence=conf
                ))

        return elements
```

### Task 4.3.3: OCR Engine

`backend/cv_pipeline/ocr_engine.py`
```python
from paddleocr import PaddleOCR
import numpy as np
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class TextRegion:
    text: str
    bbox: List[int]  # [x1, y1, x2, y2]
    confidence: float

class OCREngine:
    def __init__(self, lang: str = "en"):
        self.ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)

    def extract_text(self, image: np.ndarray) -> List[TextRegion]:
        results = self.ocr.ocr(image, cls=True)

        text_regions = []
        if results and results[0]:
            for line in results[0]:
                bbox_points = line[0]
                text = line[1][0]
                confidence = line[1][1]

                # Convert polygon to bounding box
                x_coords = [p[0] for p in bbox_points]
                y_coords = [p[1] for p in bbox_points]
                bbox = [
                    int(min(x_coords)),
                    int(min(y_coords)),
                    int(max(x_coords)),
                    int(max(y_coords))
                ]

                text_regions.append(TextRegion(
                    text=text,
                    bbox=bbox,
                    confidence=confidence
                ))

        return text_regions

    def extract_from_region(self, image: np.ndarray, bbox: List[int]) -> str:
        x1, y1, x2, y2 = bbox
        region = image[y1:y2, x1:x2]
        results = self.extract_text(region)
        return " ".join([r.text for r in results])
```

### Task 4.3.4: Context Engine

`backend/cv_pipeline/context_engine.py`
```python
from typing import List, Dict
from .yolo_detector import YOLODetector, UIElement
from .ocr_engine import OCREngine, TextRegion
from .preprocessor import ImagePreprocessor
import numpy as np

class ContextEngine:
    def __init__(self):
        self.preprocessor = ImagePreprocessor()
        self.detector = YOLODetector()
        self.ocr = OCREngine()

    def process_screenshot(self, image_data: bytes) -> Dict:
        # Preprocess image
        image = self.preprocessor.preprocess(image_data)

        # Detect UI elements
        ui_elements = self.detector.detect(image)

        # Extract text
        text_regions = self.ocr.extract_text(image)

        # Fuse results
        screen_state = self._fuse_results(image, ui_elements, text_regions)

        return screen_state

    def _fuse_results(
        self,
        image: np.ndarray,
        ui_elements: List[UIElement],
        text_regions: List[TextRegion]
    ) -> Dict:
        elements = []

        for ui_elem in ui_elements:
            # Find overlapping text
            label = self._find_element_label(ui_elem.bbox, text_regions)

            elements.append({
                "type": ui_elem.element_type,
                "label": label,
                "bbox": {
                    "x1": ui_elem.bbox[0],
                    "y1": ui_elem.bbox[1],
                    "x2": ui_elem.bbox[2],
                    "y2": ui_elem.bbox[3]
                },
                "confidence": ui_elem.confidence
            })

        return {
            "elements": elements,
            "total_elements": len(elements),
            "image_size": {
                "width": image.shape[1],
                "height": image.shape[0]
            }
        }

    def _find_element_label(
        self,
        elem_bbox: List[int],
        text_regions: List[TextRegion]
    ) -> str:
        best_match = ""
        best_overlap = 0

        for text_region in text_regions:
            overlap = self._calculate_overlap(elem_bbox, text_region.bbox)
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = text_region.text

        return best_match

    def _calculate_overlap(self, bbox1: List[int], bbox2: List[int]) -> float:
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])

        if x2 < x1 or y2 < y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)
        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0
```

## 4.4 Phase 4 Checklist

| Task | Description | Status |
|------|-------------|--------|
| 4.3.1 | Build image preprocessor | Pending |
| 4.3.2 | Set up YOLO UI detector | Pending |
| 4.3.3 | Implement PaddleOCR engine | Pending |
| 4.3.4 | Build context fusion engine | Pending |
| 4.3.5 | Train/fine-tune YOLO on UI elements | Pending |
| 4.3.6 | Create capture context API | Pending |
| 4.3.7 | Optimize for performance | Pending |

---

# Phase 5: Detection & Screen Capture

## 5.1 Objectives
- Implement window title monitoring (Rust)
- Build URL/visual detection system
- Create hotkey listener
- Integrate with frontend detection UI

## 5.2 Directory Structure

```
frontend/
├── src-tauri/
│   ├── src/
│   │   ├── main.rs
│   │   ├── detection/
│   │   │   ├── mod.rs
│   │   │   ├── window_monitor.rs
│   │   │   ├── screenshot.rs
│   │   │   └── hotkey.rs
│   │   └── commands/
│   │       ├── mod.rs
│   │       └── detection_commands.rs
```

## 5.3 Tasks

### Task 5.3.1: Window Monitor (Rust)

`frontend/src-tauri/src/detection/window_monitor.rs`
```rust
use std::time::Duration;
use tokio::time::interval;

#[cfg(target_os = "windows")]
use windows::Win32::UI::WindowsAndMessaging::{GetForegroundWindow, GetWindowTextW};

pub struct WindowMonitor {
    patterns: Vec<String>,
    poll_interval_ms: u64,
}

impl WindowMonitor {
    pub fn new(patterns: Vec<String>, poll_interval_ms: u64) -> Self {
        Self {
            patterns,
            poll_interval_ms,
        }
    }

    pub async fn start_monitoring<F>(&self, callback: F)
    where
        F: Fn(String) + Send + 'static,
    {
        let mut interval = interval(Duration::from_millis(self.poll_interval_ms));

        loop {
            interval.tick().await;

            if let Some(title) = self.get_active_window_title() {
                if self.matches_pattern(&title) {
                    callback(title);
                }
            }
        }
    }

    #[cfg(target_os = "windows")]
    fn get_active_window_title(&self) -> Option<String> {
        unsafe {
            let hwnd = GetForegroundWindow();
            let mut title: [u16; 512] = [0; 512];
            let len = GetWindowTextW(hwnd, &mut title);

            if len > 0 {
                Some(String::from_utf16_lossy(&title[..len as usize]))
            } else {
                None
            }
        }
    }

    fn matches_pattern(&self, title: &str) -> bool {
        self.patterns.iter().any(|pattern| {
            if pattern.starts_with('*') && pattern.ends_with('*') {
                title.to_lowercase().contains(&pattern[1..pattern.len()-1].to_lowercase())
            } else if pattern.starts_with('*') {
                title.to_lowercase().ends_with(&pattern[1..].to_lowercase())
            } else if pattern.ends_with('*') {
                title.to_lowercase().starts_with(&pattern[..pattern.len()-1].to_lowercase())
            } else {
                title.to_lowercase() == pattern.to_lowercase()
            }
        })
    }
}
```

### Task 5.3.2: Screenshot Capture (Rust)

`frontend/src-tauri/src/detection/screenshot.rs`
```rust
use screenshots::Screen;
use base64::{Engine as _, engine::general_purpose};

pub struct ScreenCapture;

impl ScreenCapture {
    pub fn capture_primary() -> Result<String, String> {
        let screens = Screen::all().map_err(|e| e.to_string())?;

        if let Some(screen) = screens.first() {
            let image = screen.capture().map_err(|e| e.to_string())?;
            let buffer = image.to_png().map_err(|e| e.to_string())?;

            Ok(general_purpose::STANDARD.encode(&buffer))
        } else {
            Err("No screen found".to_string())
        }
    }

    pub fn capture_low_res() -> Result<String, String> {
        // Capture at lower resolution for detection
        let screens = Screen::all().map_err(|e| e.to_string())?;

        if let Some(screen) = screens.first() {
            let image = screen.capture().map_err(|e| e.to_string())?;
            // Resize to 480p for quick OCR
            let resized = image.resize(854, 480, image::imageops::FilterType::Nearest);
            let buffer = resized.to_png().map_err(|e| e.to_string())?;

            Ok(general_purpose::STANDARD.encode(&buffer))
        } else {
            Err("No screen found".to_string())
        }
    }
}
```

### Task 5.3.3: Tauri Commands

`frontend/src-tauri/src/commands/detection_commands.rs`
```rust
use tauri::command;
use crate::detection::{screenshot::ScreenCapture, window_monitor::WindowMonitor};

#[command]
pub async fn capture_screenshot() -> Result<String, String> {
    ScreenCapture::capture_primary()
}

#[command]
pub async fn capture_low_res() -> Result<String, String> {
    ScreenCapture::capture_low_res()
}

#[command]
pub async fn get_active_window_title() -> Result<String, String> {
    // Implementation depends on OS
    #[cfg(target_os = "windows")]
    {
        use windows::Win32::UI::WindowsAndMessaging::{GetForegroundWindow, GetWindowTextW};

        unsafe {
            let hwnd = GetForegroundWindow();
            let mut title: [u16; 512] = [0; 512];
            let len = GetWindowTextW(hwnd, &mut title);

            if len > 0 {
                Ok(String::from_utf16_lossy(&title[..len as usize]))
            } else {
                Ok(String::new())
            }
        }
    }

    #[cfg(not(target_os = "windows"))]
    {
        Ok(String::new())
    }
}

#[command]
pub fn register_hotkey(key_combo: String) -> Result<(), String> {
    // Register global hotkey
    Ok(())
}
```

## 5.4 Phase 5 Checklist

| Task | Description | Status |
|------|-------------|--------|
| 5.3.1 | Implement window title monitor | Pending |
| 5.3.2 | Build screenshot capture | Pending |
| 5.3.3 | Create Tauri commands | Pending |
| 5.3.4 | Implement global hotkey listener | Pending |
| 5.3.5 | Build detection state machine | Pending |
| 5.3.6 | Create detection UI components | Pending |
| 5.3.7 | Integrate with backend detection API | Pending |

---

# Phase 6: AI Guidance Engine

## 6.1 Objectives
- Build element-to-instruction matcher
- Implement AI reasoning with LLM
- Create guidance generation system
- Build step tracking logic

## 6.2 Directory Structure

```
backend/
├── app/
│   ├── ai_engine/
│   │   ├── __init__.py
│   │   ├── matcher.py
│   │   ├── reasoner.py
│   │   └── guidance_generator.py
│   ├── api/
│   │   └── guidance.py
│   └── services/
│       └── guidance_service.py
```

## 6.3 Tasks

### Task 6.3.1: Element Matcher

`backend/app/ai_engine/matcher.py`
```python
from typing import List, Dict, Optional
from difflib import SequenceMatcher

class ElementMatcher:
    def __init__(self, similarity_threshold: float = 0.6):
        self.threshold = similarity_threshold

    def match_step_to_element(
        self,
        step: Dict,
        elements: List[Dict]
    ) -> Optional[Dict]:
        target_label = step.get("target_label", "").lower()
        target_type = step.get("target_element", "").lower()

        best_match = None
        best_score = 0

        for element in elements:
            score = self._calculate_match_score(
                target_label, target_type, element
            )

            if score > best_score and score >= self.threshold:
                best_score = score
                best_match = {**element, "match_score": score}

        return best_match

    def _calculate_match_score(
        self,
        target_label: str,
        target_type: str,
        element: Dict
    ) -> float:
        label_score = 0
        type_score = 0

        # Label similarity
        elem_label = element.get("label", "").lower()
        if target_label and elem_label:
            label_score = SequenceMatcher(
                None, target_label, elem_label
            ).ratio()

        # Type matching
        elem_type = element.get("type", "").lower()
        if target_type == elem_type:
            type_score = 1.0
        elif self._types_compatible(target_type, elem_type):
            type_score = 0.7

        # Weighted combination
        return (label_score * 0.7) + (type_score * 0.3)

    def _types_compatible(self, type1: str, type2: str) -> bool:
        compatible_types = {
            "button": ["link", "icon"],
            "input": ["text", "textarea"],
            "dropdown": ["select", "combobox"]
        }
        return type2 in compatible_types.get(type1, [])
```

### Task 6.3.2: AI Reasoner

`backend/app/ai_engine/reasoner.py`
```python
from typing import List, Dict
import httpx

class AIReasoner:
    def __init__(self, api_url: str = None, api_key: str = None):
        self.api_url = api_url or "http://localhost:11434/api/generate"
        self.api_key = api_key
        self.model = "llama3"

    async def generate_guidance(
        self,
        query: str,
        screen_state: Dict,
        rag_results: List[Dict],
        current_step: int = 1
    ) -> Dict:
        prompt = self._build_prompt(query, screen_state, rag_results, current_step)

        response = await self._call_llm(prompt)

        return self._parse_response(response)

    def _build_prompt(
        self,
        query: str,
        screen_state: Dict,
        rag_results: List[Dict],
        current_step: int
    ) -> str:
        elements_desc = "\n".join([
            f"- {e['type']}: '{e.get('label', 'unlabeled')}' at position ({e['bbox']['x1']}, {e['bbox']['y1']})"
            for e in screen_state.get("elements", [])[:20]
        ])

        instructions_desc = "\n".join([
            f"Step {r.get('step_number', i+1)}: {r.get('instruction', '')}"
            for i, r in enumerate(rag_results[:5])
        ])

        return f"""You are a UI guidance assistant. Based on the user's question and what's visible on screen, determine the next action.

USER QUESTION: {query}

CURRENT STEP: {current_step}

VISIBLE UI ELEMENTS:
{elements_desc}

RELEVANT INSTRUCTIONS FROM KNOWLEDGE BASE:
{instructions_desc}

Respond with JSON containing:
- current_instruction: The instruction for this step
- target_element_label: The label of the element to interact with
- action_type: click, type, select, or navigate
- confidence: Your confidence score (0-1)

JSON Response:"""

    async def _call_llm(self, prompt: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30.0
            )
            return response.json().get("response", "")

    def _parse_response(self, response: str) -> Dict:
        import json
        try:
            # Extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except:
            pass

        return {
            "current_instruction": "Unable to determine action",
            "target_element_label": "",
            "action_type": "unknown",
            "confidence": 0.0
        }
```

### Task 6.3.3: Guidance API

`backend/app/api/guidance.py`
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.guidance_service import GuidanceService
from app.core.database import get_db
from pydantic import BaseModel
from typing import List, Dict

router = APIRouter(prefix="/infer", tags=["Guidance"])

class GuidanceRequest(BaseModel):
    session_id: str
    capture_id: str
    query: str
    screen_state: Dict
    rag_results: List[Dict]
    current_step: int = 1

@router.post("/guidance")
async def generate_guidance(
    request: GuidanceRequest,
    db: AsyncSession = Depends(get_db)
):
    service = GuidanceService(db)
    return await service.generate_guidance(
        session_id=request.session_id,
        capture_id=request.capture_id,
        query=request.query,
        screen_state=request.screen_state,
        rag_results=request.rag_results,
        current_step=request.current_step
    )

@router.get("/steps/{session_id}")
async def get_session_steps(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = GuidanceService(db)
    return await service.get_session_steps(session_id)
```

## 6.4 Phase 6 Checklist

| Task | Description | Status |
|------|-------------|--------|
| 6.3.1 | Build element-to-instruction matcher | Pending |
| 6.3.2 | Implement AI reasoner with LLM | Pending |
| 6.3.3 | Create guidance generator | Pending |
| 6.3.4 | Build guidance API endpoints | Pending |
| 6.3.5 | Implement step tracking | Pending |
| 6.3.6 | Add confidence scoring | Pending |

---

# Phase 7: Halo Overlay System

## 7.1 Objectives
- Build transparent overlay window
- Implement halo rendering (glow, pulse)
- Create tooltip system
- Handle overlay positioning

## 7.2 Directory Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── HaloOverlay/
│   │   │   ├── HaloOverlay.tsx
│   │   │   ├── HaloElement.tsx
│   │   │   ├── Tooltip.tsx
│   │   │   └── styles.css
│   │   └── index.ts
│   └── hooks/
│       └── useHaloOverlay.ts
```

## 7.3 Tasks

### Task 7.3.1: Halo Overlay Component

`frontend/src/components/HaloOverlay/HaloOverlay.tsx`
```typescript
import React, { useEffect, useRef } from 'react';
import { HaloElement } from './HaloElement';
import { Tooltip } from './Tooltip';
import './styles.css';

interface HaloTarget {
  halo_id: string;
  element_id: string;
  label: string;
  bbox: { x1: number; y1: number; x2: number; y2: number };
  halo_style: 'glow' | 'pulse' | 'outline';
  tooltip_text: string;
}

interface HaloOverlayProps {
  targets: HaloTarget[];
  visible: boolean;
  onHaloClick?: (haloId: string) => void;
}

export const HaloOverlay: React.FC<HaloOverlayProps> = ({
  targets,
  visible,
  onHaloClick
}) => {
  const overlayRef = useRef<HTMLDivElement>(null);

  if (!visible || targets.length === 0) return null;

  return (
    <div ref={overlayRef} className="halo-overlay">
      {targets.map((target) => (
        <HaloElement
          key={target.halo_id}
          target={target}
          onClick={() => onHaloClick?.(target.halo_id)}
        />
      ))}
    </div>
  );
};
```

### Task 7.3.2: Halo Element Component

`frontend/src/components/HaloOverlay/HaloElement.tsx`
```typescript
import React, { useState } from 'react';
import { Tooltip } from './Tooltip';

interface HaloTarget {
  halo_id: string;
  label: string;
  bbox: { x1: number; y1: number; x2: number; y2: number };
  halo_style: 'glow' | 'pulse' | 'outline';
  tooltip_text: string;
}

interface HaloElementProps {
  target: HaloTarget;
  onClick?: () => void;
}

export const HaloElement: React.FC<HaloElementProps> = ({ target, onClick }) => {
  const [showTooltip, setShowTooltip] = useState(true);

  const { bbox, halo_style, tooltip_text, label } = target;
  const width = bbox.x2 - bbox.x1;
  const height = bbox.y2 - bbox.y1;

  const style: React.CSSProperties = {
    position: 'absolute',
    left: bbox.x1,
    top: bbox.y1,
    width,
    height,
    pointerEvents: 'none',
  };

  return (
    <div
      className={`halo-element halo-${halo_style}`}
      style={style}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <div className="halo-border" />
      {showTooltip && (
        <Tooltip
          text={tooltip_text}
          position={{ x: bbox.x1, y: bbox.y1 - 40 }}
        />
      )}
      <span className="halo-label">{label}</span>
    </div>
  );
};
```

### Task 7.3.3: Halo Styles

`frontend/src/components/HaloOverlay/styles.css`
```css
.halo-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  pointer-events: none;
  z-index: 9999;
}

.halo-element {
  position: absolute;
  border-radius: 4px;
}

.halo-border {
  position: absolute;
  inset: -4px;
  border-radius: 8px;
  pointer-events: none;
}

/* Glow Style */
.halo-glow .halo-border {
  border: 3px solid #4F46E5;
  box-shadow:
    0 0 10px #4F46E5,
    0 0 20px #4F46E5,
    0 0 30px #4F46E5,
    inset 0 0 10px rgba(79, 70, 229, 0.3);
  animation: glow-pulse 2s ease-in-out infinite;
}

@keyframes glow-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

/* Pulse Style */
.halo-pulse .halo-border {
  border: 3px solid #10B981;
  animation: pulse-ring 1.5s ease-out infinite;
}

@keyframes pulse-ring {
  0% {
    transform: scale(1);
    opacity: 1;
  }
  100% {
    transform: scale(1.1);
    opacity: 0;
  }
}

/* Outline Style */
.halo-outline .halo-border {
  border: 2px dashed #F59E0B;
  animation: dash-move 1s linear infinite;
}

@keyframes dash-move {
  to {
    stroke-dashoffset: -20;
  }
}

.halo-label {
  position: absolute;
  bottom: -25px;
  left: 50%;
  transform: translateX(-50%);
  background: #1F2937;
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
}

.tooltip {
  position: absolute;
  background: #111827;
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 14px;
  max-width: 250px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  z-index: 10000;
}

.tooltip::after {
  content: '';
  position: absolute;
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: #111827;
}
```

### Task 7.3.4: Tauri Overlay Window

`frontend/src-tauri/src/main.rs` (additions)
```rust
use tauri::{Manager, WindowBuilder, WindowUrl};

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            // Create overlay window
            let overlay_window = WindowBuilder::new(
                app,
                "overlay",
                WindowUrl::App("overlay.html".into())
            )
            .transparent(true)
            .decorations(false)
            .always_on_top(true)
            .skip_taskbar(true)
            .fullscreen(true)
            .build()?;

            // Make window click-through
            overlay_window.set_ignore_cursor_events(true)?;

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            show_halos,
            hide_halos,
            update_halos
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[tauri::command]
async fn show_halos(window: tauri::Window, targets: Vec<HaloTarget>) -> Result<(), String> {
    window.emit("show-halos", targets).map_err(|e| e.to_string())
}

#[tauri::command]
async fn hide_halos(window: tauri::Window) -> Result<(), String> {
    window.emit("hide-halos", ()).map_err(|e| e.to_string())
}

#[tauri::command]
async fn update_halos(window: tauri::Window, targets: Vec<HaloTarget>) -> Result<(), String> {
    window.emit("update-halos", targets).map_err(|e| e.to_string())
}
```

## 7.4 Phase 7 Checklist

| Task | Description | Status |
|------|-------------|--------|
| 7.3.1 | Build HaloOverlay component | Pending |
| 7.3.2 | Create HaloElement with animations | Pending |
| 7.3.3 | Implement tooltip system | Pending |
| 7.3.4 | Set up Tauri overlay window | Pending |
| 7.3.5 | Handle click-through behavior | Pending |
| 7.3.6 | Add multiple halo styles | Pending |
| 7.3.7 | Build halo API integration | Pending |

---

# Phase 8: Integration & Testing

## 8.1 Objectives
- Integrate all system components
- Write unit and integration tests
- Perform end-to-end testing
- Fix bugs and optimize performance

## 8.2 Tasks

### Task 8.2.1: Integration Tests

```python
# backend/tests/test_integration.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_full_guidance_flow():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 1. Start detection
        response = await client.post("/detection/start", json={
            "query": "How do I submit an invoice?",
            "user_id": "test-user-id"
        })
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        # 2. Confirm detection
        response = await client.post("/detection/confirm", json={
            "session_id": session_id,
            "org_id": "test-org-id"
        })
        assert response.status_code == 200

        # 3. Capture context
        response = await client.post("/capture/context", json={
            "session_id": session_id,
            "screenshot_base64": "...",
            "screenshot_width": 1920,
            "screenshot_height": 1080
        })
        assert response.status_code == 200
        capture_id = response.json()["capture_id"]

        # 4. Get guidance
        response = await client.post("/infer/guidance", json={
            "session_id": session_id,
            "capture_id": capture_id,
            "query": "How do I submit an invoice?",
            "screen_state": response.json()["screen_state"],
            "rag_results": []
        })
        assert response.status_code == 200
        assert "halo_targets" in response.json()
```

### Task 8.2.2: Frontend Tests

```typescript
// frontend/src/__tests__/HaloOverlay.test.tsx
import { render, screen } from '@testing-library/react';
import { HaloOverlay } from '../components/HaloOverlay';

describe('HaloOverlay', () => {
  const mockTargets = [
    {
      halo_id: 'halo-1',
      element_id: 'elem-1',
      label: 'Submit Button',
      bbox: { x1: 100, y1: 100, x2: 200, y2: 150 },
      halo_style: 'glow' as const,
      tooltip_text: 'Click here to submit'
    }
  ];

  it('renders halos when visible', () => {
    render(<HaloOverlay targets={mockTargets} visible={true} />);
    expect(screen.getByText('Submit Button')).toBeInTheDocument();
  });

  it('hides halos when not visible', () => {
    render(<HaloOverlay targets={mockTargets} visible={false} />);
    expect(screen.queryByText('Submit Button')).not.toBeInTheDocument();
  });
});
```

## 8.3 Phase 8 Checklist

| Task | Description | Status |
|------|-------------|--------|
| 8.2.1 | Write backend unit tests | Pending |
| 8.2.2 | Write frontend unit tests | Pending |
| 8.2.3 | Create integration tests | Pending |
| 8.2.4 | Perform E2E testing | Pending |
| 8.2.5 | Performance optimization | Pending |
| 8.2.6 | Bug fixes | Pending |
| 8.2.7 | Code review | Pending |

---

# Phase 9: Polish & Deployment

## 9.1 Objectives
- Final UI polish
- Documentation
- Build & package application
- Deployment preparation

## 9.2 Tasks

### Task 9.2.1: Build Configuration

`frontend/src-tauri/tauri.conf.json`
```json
{
  "build": {
    "beforeBuildCommand": "npm run build",
    "beforeDevCommand": "npm run dev",
    "devPath": "http://localhost:5173",
    "distDir": "../dist"
  },
  "package": {
    "productName": "Pedagogy",
    "version": "1.0.0"
  },
  "tauri": {
    "bundle": {
      "active": true,
      "identifier": "com.pedagogy.app",
      "icon": [
        "icons/32x32.png",
        "icons/128x128.png",
        "icons/128x128@2x.png",
        "icons/icon.icns",
        "icons/icon.ico"
      ],
      "targets": ["msi", "nsis", "dmg", "app"]
    },
    "windows": [
      {
        "title": "Pedagogy",
        "width": 400,
        "height": 600,
        "resizable": true,
        "fullscreen": false
      }
    ]
  }
}
```

### Task 9.2.2: Docker Production Config

`docker/Dockerfile.backend`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 9.3 Phase 9 Checklist

| Task | Description | Status |
|------|-------------|--------|
| 9.2.1 | Configure build settings | Pending |
| 9.2.2 | Create production Docker configs | Pending |
| 9.2.3 | Write user documentation | Pending |
| 9.2.4 | Create installer packages | Pending |
| 9.2.5 | Final testing | Pending |
| 9.2.6 | Release preparation | Pending |

---

## Summary: All Phases

| Phase | Description | Est. Tasks |
|-------|-------------|------------|
| **Phase 1** | Project Setup & Core Infrastructure | 6 |
| **Phase 2** | Authentication & Organisation Management | 8 |
| **Phase 3** | Knowledge Base & RAG System | 8 |
| **Phase 4** | Computer Vision Pipeline | 7 |
| **Phase 5** | Detection & Screen Capture | 7 |
| **Phase 6** | AI Guidance Engine | 6 |
| **Phase 7** | Halo Overlay System | 7 |
| **Phase 8** | Integration & Testing | 7 |
| **Phase 9** | Polish & Deployment | 6 |
| **Total** | | **62 Tasks** |

---

## How to Use This Document

1. **Track Progress**: Update the "Status" column in each checklist
2. **Sequential Execution**: Complete phases in order (dependencies exist)
3. **Parallel Work**: Some tasks within a phase can be done in parallel
4. **Code Templates**: Use provided code as starting points
5. **Adapt as Needed**: Modify structure based on actual requirements
