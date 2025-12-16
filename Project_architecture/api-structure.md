# Pedagogy - API Structure & Specifications

## 1. API Overview

```mermaid
flowchart TB
    subgraph CLIENT["CLIENT LAYER"]
        TAURI[Tauri Desktop App]
        RUST[Rust Core]
    end

    subgraph API["FASTAPI BACKEND"]
        ROUTER[API Router]

        subgraph ENDPOINTS["API Endpoint Groups"]
            direction TB
            CAPTURE["/capture/*<br/>Screenshot & CV"]
            RAG["/query/*<br/>RAG Search"]
            GUIDANCE["/infer/*<br/>AI Guidance"]
            HALO["/halo/*<br/>Overlay Control"]
            ORG["/org/*<br/>Organisation Management"]
            AUTH["/auth/*<br/>Authentication"]
            HEALTH["/health/*<br/>System Status"]
        end
    end

    subgraph SERVICES["BACKEND SERVICES"]
        CV_SVC[CV Pipeline Service]
        RAG_SVC[RAG Service]
        AI_SVC[AI Reasoning Service]
        ORG_SVC[Organisation Service]
        SESSION_SVC[Session Service]
        AUTH_SVC[Authentication Service]
    end

    subgraph DATA["DATA LAYER"]
        DB[(PostgreSQL)]
        VECTOR[(Vector DB)]
        FILES[File Storage]
    end

    TAURI --> RUST
    RUST --> ROUTER

    ROUTER --> CAPTURE
    ROUTER --> RAG
    ROUTER --> GUIDANCE
    ROUTER --> HALO
    ROUTER --> ORG
    ROUTER --> AUTH
    ROUTER --> HEALTH

    AUTH --> AUTH_SVC
    AUTH_SVC --> DB

    CAPTURE --> CV_SVC
    CAPTURE --> SESSION_SVC
    RAG --> RAG_SVC
    GUIDANCE --> AI_SVC
    ORG --> ORG_SVC

    CV_SVC --> DB
    RAG_SVC --> VECTOR
    AI_SVC --> DB
    ORG_SVC --> DB
    SESSION_SVC --> DB
    ORG_SVC --> FILES
```

## 2. API Endpoint Groups

```mermaid
flowchart LR
    subgraph CAPTURE["Capture APIs"]
        C1[POST /capture/context]
        C2[POST /capture/screenshot]
        C3[GET /capture/elements]
    end

    subgraph QUERY["Query/RAG APIs"]
        Q1[POST /query/rag]
        Q2[POST /query/embed]
        Q3[GET /query/history]
    end

    subgraph GUIDANCE["Guidance APIs"]
        G1[POST /infer/guidance]
        G2[POST /infer/match]
        G3[GET /infer/steps]
    end

    subgraph HALO["Halo APIs"]
        H1[POST /halo/overlay]
        H2[POST /halo/clear]
        H3[GET /halo/targets]
    end

    subgraph ORG["Organisation APIs"]
        O1[GET /org/profile]
        O2[POST /org/onboard]
        O3[POST /org/upload-knowledge]
    end

    subgraph AUTH["Authentication APIs"]
        A1[POST /auth/register]
        A2[POST /auth/login]
        A3[POST /auth/logout]
        A4[POST /auth/refresh]
        A5[GET /auth/me]
    end

    subgraph HEALTH["Health APIs"]
        HE1[GET /health]
        HE2[GET /health/services]
    end
```

## 3. Request/Response Flow

```mermaid
sequenceDiagram
    participant Client as Tauri Client
    participant API as FastAPI
    participant Auth as Auth Middleware
    participant Service as Service Layer
    participant DB as Database

    Client->>API: HTTP Request
    API->>Auth: Validate Request

    alt Invalid Request
        Auth-->>Client: 401 Unauthorized
    else Valid Request
        Auth->>Service: Process Request
        Service->>DB: Query/Update Data
        DB-->>Service: Data Response
        Service-->>API: Service Response
        API-->>Client: HTTP Response
    end
```

---

# Detailed API Specifications

## 4. Capture APIs

### 4.1 POST /capture/context

**Purpose**: Process screenshot through CV/OCR pipeline.

```mermaid
sequenceDiagram
    participant Client
    participant API as /capture/context
    participant CV as CV Pipeline
    participant OCR as OCR Service
    participant DB as Database

    Client->>API: POST screenshot + session_id
    API->>CV: Preprocess image
    CV->>CV: YOLO detection
    CV->>OCR: Extract text regions
    OCR-->>CV: OCR results
    CV->>CV: Fuse YOLO + OCR
    CV-->>API: Screen state JSON
    API->>DB: Store capture event
    API-->>Client: UI elements response
```

**Request:**
```json
{
  "session_id": "abc123-uuid",
  "screenshot_base64": "base64-encoded-image-data",
  "screenshot_width": 1920,
  "screenshot_height": 1080,
  "capture_timestamp": "2025-12-10T10:30:45Z"
}
```

**Response:**
```json
{
  "success": true,
  "capture_id": "capture-uuid",
  "processing_time_ms": 1250,
  "screen_state": {
    "elements": [
      {
        "element_id": "elem-001",
        "type": "button",
        "label": "Submit Invoice",
        "bbox": {"x1": 150, "y1": 400, "x2": 280, "y2": 440},
        "confidence": 0.94,
        "ocr_text": "Submit Invoice"
      },
      {
        "element_id": "elem-002",
        "type": "input",
        "label": "Invoice Number",
        "bbox": {"x1": 150, "y1": 200, "x2": 400, "y2": 240},
        "confidence": 0.91,
        "ocr_text": "INV-"
      },
      {
        "element_id": "elem-003",
        "type": "dropdown",
        "label": "Department",
        "bbox": {"x1": 150, "y1": 280, "x2": 400, "y2": 320},
        "confidence": 0.88,
        "ocr_text": "Select Department"
      }
    ],
    "total_elements": 3,
    "layout_info": {
      "detected_app": "Web Browser",
      "page_title": "ACME Invoice Portal"
    }
  }
}
```

---

### 4.2 GET /capture/elements/{capture_id}

**Purpose**: Retrieve detected UI elements from a capture.

**Response:**
```json
{
  "capture_id": "capture-uuid",
  "elements": [
    {
      "element_id": "elem-001",
      "type": "button",
      "label": "Submit Invoice",
      "bbox": {"x1": 150, "y1": 400, "x2": 280, "y2": 440},
      "confidence": 0.94
    }
  ],
  "total_count": 15
}
```

---

## 5. Query/RAG APIs

### 5.1 POST /query/rag

**Purpose**: Search knowledge base for relevant instructions.

```mermaid
sequenceDiagram
    participant Client
    participant API as /query/rag
    participant Embed as Embedding Service
    participant Vector as Vector DB
    participant Filter as Semantic Filter

    Client->>API: POST query + org_id
    API->>Embed: Generate query embedding
    Embed-->>API: Query vector
    API->>Vector: Similarity search
    Vector-->>API: Top K matches
    API->>Filter: Apply semantic filter
    Filter-->>API: Filtered results
    API-->>Client: Instruction steps
```

**Request:**
```json
{
  "query": "How do I submit an invoice?",
  "org_id": "acme-uuid",
  "session_id": "abc123-uuid",
  "top_k": 5,
  "min_similarity": 0.7
}
```

**Response:**
```json
{
  "success": true,
  "query_id": "query-uuid",
  "results": [
    {
      "step_id": "step-001",
      "step_number": 1,
      "instruction": "Navigate to the Invoices tab in the left sidebar",
      "target_element": "tab",
      "target_label": "Invoices",
      "step_type": "navigation",
      "similarity": 0.92
    },
    {
      "step_id": "step-002",
      "step_number": 2,
      "instruction": "Click the 'New Invoice' button",
      "target_element": "button",
      "target_label": "New Invoice",
      "step_type": "click",
      "similarity": 0.89
    },
    {
      "step_id": "step-003",
      "step_number": 3,
      "instruction": "Fill in the invoice number field",
      "target_element": "input",
      "target_label": "Invoice Number",
      "step_type": "input",
      "similarity": 0.85
    }
  ],
  "total_results": 3,
  "search_time_ms": 45
}
```

---

### 5.2 GET /query/history/{user_id}

**Purpose**: Get user's query history.

**Response:**
```json
{
  "user_id": "user-uuid",
  "queries": [
    {
      "query_id": "query-uuid",
      "query_text": "How do I submit an invoice?",
      "org_name": "ACME Corporation",
      "queried_at": "2025-12-10T10:30:00Z",
      "results_count": 5
    }
  ],
  "total_count": 25,
  "page": 1,
  "per_page": 10
}
```

---

## 6. Guidance APIs

### 6.1 POST /infer/guidance

**Purpose**: Generate AI guidance by matching screen state with instructions.

```mermaid
sequenceDiagram
    participant Client
    participant API as /infer/guidance
    participant AI as AI Engine
    participant Matcher as Element Matcher

    Client->>API: POST screen_state + rag_results
    API->>Matcher: Match elements to steps
    Matcher-->>API: Matched pairs
    API->>AI: Generate guidance
    AI-->>API: Guidance + halo targets
    API-->>Client: Guidance response
```

**Request:**
```json
{
  "session_id": "abc123-uuid",
  "capture_id": "capture-uuid",
  "query": "How do I submit an invoice?",
  "screen_state": {
    "elements": [...]
  },
  "rag_results": [
    {
      "step_id": "step-001",
      "instruction": "Click the Submit button",
      "target_label": "Submit"
    }
  ],
  "current_step": 1
}
```

**Response:**
```json
{
  "success": true,
  "guidance_id": "guidance-uuid",
  "current_step": {
    "step_number": 1,
    "instruction": "Click the 'Submit Invoice' button to proceed",
    "action_type": "click",
    "confidence": 0.91
  },
  "matched_element": {
    "element_id": "elem-001",
    "type": "button",
    "label": "Submit Invoice",
    "bbox": {"x1": 150, "y1": 400, "x2": 280, "y2": 440}
  },
  "halo_targets": [
    {
      "halo_id": "halo-001",
      "element_id": "elem-001",
      "label": "Click here: Submit Invoice",
      "bbox": {"x1": 150, "y1": 400, "x2": 280, "y2": 440},
      "halo_style": "glow",
      "tooltip_text": "Step 1: Click this button to submit your invoice"
    }
  ],
  "next_steps_preview": [
    "Step 2: Confirm the submission in the dialog",
    "Step 3: Note down the confirmation number"
  ],
  "total_steps": 5,
  "completed_steps": 0
}
```

---

### 6.2 GET /infer/steps/{session_id}

**Purpose**: Get all guidance steps for a session.

**Response:**
```json
{
  "session_id": "abc123-uuid",
  "steps": [
    {
      "step_number": 1,
      "instruction": "Navigate to Invoices tab",
      "status": "completed",
      "completed_at": "2025-12-10T10:31:00Z"
    },
    {
      "step_number": 2,
      "instruction": "Click Submit Invoice button",
      "status": "current"
    },
    {
      "step_number": 3,
      "instruction": "Confirm submission",
      "status": "pending"
    }
  ],
  "total_steps": 3,
  "completed_count": 1
}
```

---

## 7. Halo APIs

### 7.1 POST /halo/overlay

**Purpose**: Send halo overlay instructions to the frontend.

**Request:**
```json
{
  "session_id": "abc123-uuid",
  "halo_targets": [
    {
      "element_id": "elem-001",
      "label": "Submit Invoice",
      "bbox": {"x1": 150, "y1": 400, "x2": 280, "y2": 440},
      "halo_style": "glow",
      "tooltip_text": "Click here to submit",
      "display_order": 1
    }
  ],
  "animation": "pulse",
  "duration_ms": 5000
}
```

**Response:**
```json
{
  "success": true,
  "halo_count": 1,
  "displayed": true
}
```

---

### 7.2 POST /halo/clear

**Purpose**: Clear all active halo overlays.

**Request:**
```json
{
  "session_id": "abc123-uuid"
}
```

**Response:**
```json
{
  "success": true,
  "cleared_count": 3
}
```

---

## 8. Organisation APIs

### 8.1 GET /org/profile

**Purpose**: Get organisation profile for the deployed instance.

**Response:**
```json
{
  "org_id": "acme-uuid",
  "org_name": "ACME Corporation",
  "org_slug": "acme-corp",
  "logo_path": "/assets/logo.png",
  "primary_color": "#FF5733",
  "branding": {
    "logo_path": "assets/logo.png",
    "primary_color": "#FF5733"
  },
  "settings": {
    "hotkey": "Ctrl+Shift+P",
    "auto_capture_on_query": false,
    "default_language": "en"
  },
  "knowledge_bases": [
    {
      "kb_id": "kb-001",
      "kb_name": "Invoice Processing",
      "document_count": 15,
      "step_count": 45
    }
  ],
  "stats": {
    "total_users": 25,
    "total_sessions": 1250,
    "last_activity": "2025-12-10T10:30:00Z"
  }
}
```

---

### 8.2 POST /org/onboard

**Purpose**: Complete organisation onboarding with initial configuration.

```mermaid
sequenceDiagram
    participant Admin
    participant API as /org/onboard
    participant OrgSvc as Organisation Service
    participant DB as Database
    participant Files as File Storage

    Admin->>API: POST org details
    API->>OrgSvc: Validate org data
    OrgSvc->>DB: Create/update organisation record
    OrgSvc->>Files: Create org directories
    Files-->>OrgSvc: Directories created
    DB-->>OrgSvc: Organisation configured
    OrgSvc-->>API: Org profile
    API-->>Admin: Onboarding complete
```

**Request:**
```json
{
  "org_name": "ACME Corporation",
  "org_slug": "acme-corp",
  "admin_email": "admin@acme.com",
  "admin_password": "secure_password_123",
  "branding": {
    "primary_color": "#FF5733",
    "logo_base64": "base64-encoded-logo-image"
  },
  "settings": {
    "hotkey": "Ctrl+Shift+P",
    "auto_capture_on_query": false,
    "default_language": "en"
  },
  "initial_users": [
    {
      "email": "user1@acme.com",
      "role": "user"
    },
    {
      "email": "manager@acme.com",
      "role": "manager"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "organisation": {
    "org_id": "acme-uuid",
    "org_name": "ACME Corporation",
    "org_slug": "acme-corp",
    "status": "active",
    "created_at": "2025-12-10T10:30:00Z"
  },
  "admin_user": {
    "user_id": "admin-uuid",
    "email": "admin@acme.com",
    "role": "org_admin"
  },
  "users_invited": 2,
  "next_steps": [
    "Upload knowledge base documents via /org/upload-knowledge",
    "Invite additional users"
  ]
}
```

**Error Responses:**
| Status | Code | Description |
|--------|------|-------------|
| 400 | `INVALID_ORG_DATA` | Missing or invalid organisation data |
| 409 | `ORG_SLUG_EXISTS` | Organisation slug already taken |
| 409 | `EMAIL_EXISTS` | Admin email already registered |

---

### 8.3 POST /org/upload-knowledge

**Purpose**: Upload knowledge base documents (SOPs, manuals, walkthroughs) for an organisation.

```mermaid
sequenceDiagram
    participant Admin
    participant API as /org/upload-knowledge
    participant Parser as Document Parser
    participant Embed as Embedding Service
    participant Vector as Vector DB
    participant DB as Database

    Admin->>API: POST documents
    API->>Parser: Parse document files
    Parser->>Parser: Extract text & structure
    Parser-->>API: Parsed content
    API->>API: Convert to instruction steps
    API->>Embed: Generate embeddings
    Embed-->>API: Step vectors
    API->>Vector: Store embeddings
    API->>DB: Save knowledge base records
    DB-->>API: Records saved
    API-->>Admin: Upload complete
```

**Request (multipart/form-data):**
```json
{
  "org_id": "acme-uuid",
  "kb_name": "Invoice Processing",
  "kb_description": "Step-by-step guide for invoice submission and approval",
  "documents": [
    {
      "file": "(binary file data - PDF/DOCX/MD)",
      "filename": "invoice_sop.pdf",
      "doc_type": "sop"
    },
    {
      "file": "(binary file data)",
      "filename": "invoice_walkthrough.md",
      "doc_type": "walkthrough"
    }
  ],
  "processing_options": {
    "extract_steps": true,
    "generate_embeddings": true,
    "detect_ui_references": true
  }
}
```

**Response:**
```json
{
  "success": true,
  "knowledge_base": {
    "kb_id": "kb-uuid",
    "kb_name": "Invoice Processing",
    "org_id": "acme-uuid",
    "created_at": "2025-12-10T10:40:00Z"
  },
  "documents_processed": [
    {
      "doc_id": "doc-001",
      "filename": "invoice_sop.pdf",
      "status": "processed",
      "chunks_created": 25,
      "steps_extracted": 12
    },
    {
      "doc_id": "doc-002",
      "filename": "invoice_walkthrough.md",
      "status": "processed",
      "chunks_created": 15,
      "steps_extracted": 8
    }
  ],
  "total_steps": 20,
  "embeddings_generated": 40,
  "processing_time_sec": 45
}
```

**Error Responses:**
| Status | Code | Description |
|--------|------|-------------|
| 400 | `INVALID_FILE_TYPE` | Unsupported document format |
| 413 | `FILE_TOO_LARGE` | Document exceeds size limit |
| 422 | `PARSING_FAILED` | Could not parse document content |

---

### 8.4 GET /org/onboarding-status

**Purpose**: Check organisation onboarding progress.

**Response:**
```json
{
  "org_id": "acme-uuid",
  "org_name": "ACME Corporation",
  "onboarding_status": "in_progress",
  "checklist": {
    "organisation_configured": true,
    "logo_uploaded": true,
    "knowledge_base_uploaded": false,
    "first_user_invited": true,
    "test_session_completed": false
  },
  "completion_percentage": 60,
  "pending_items": [
    "Upload at least one knowledge base document",
    "Complete a test guidance session"
  ]
}
```

---

## 9. Authentication APIs

### 9.1 POST /auth/register

**Purpose**: Register a new user account.

```mermaid
sequenceDiagram
    participant User
    participant API as /auth/register
    participant Auth as Auth Service
    participant DB as Database
    participant Email as Email Service

    User->>API: POST registration data
    API->>Auth: Validate data
    Auth->>DB: Check email uniqueness
    DB-->>Auth: Email available
    Auth->>Auth: Hash password
    Auth->>DB: Create user record
    DB-->>Auth: User created
    Auth->>Email: Send verification email
    Email-->>Auth: Email sent
    Auth-->>API: User profile
    API-->>User: Registration successful
```

**Request:**
```json
{
  "email": "john.doe@acme.com",
  "password": "secure_password_123",
  "full_name": "John Doe",
  "org_id": "acme-uuid",
  "invite_code": "INV-ABC123"
}
```

**Response:**
```json
{
  "success": true,
  "user": {
    "user_id": "user-uuid",
    "email": "john.doe@acme.com",
    "full_name": "John Doe",
    "role": "user",
    "status": "pending_verification",
    "created_at": "2025-12-10T10:30:00Z"
  },
  "organisation": {
    "org_id": "acme-uuid",
    "org_name": "ACME Corporation"
  },
  "verification_email_sent": true,
  "message": "Please check your email to verify your account"
}
```

**Error Responses:**
| Status | Code | Description |
|--------|------|-------------|
| 400 | `INVALID_EMAIL` | Email format is invalid |
| 400 | `WEAK_PASSWORD` | Password doesn't meet requirements |
| 409 | `EMAIL_EXISTS` | Email already registered |
| 404 | `INVALID_INVITE` | Invite code is invalid or expired |
| 404 | `ORG_NOT_FOUND` | Organisation doesn't exist |

---

### 9.2 POST /auth/login

**Purpose**: Authenticate user and obtain access tokens.

**Request:**
```json
{
  "email": "john.doe@acme.com",
  "password": "secure_password_123",
  "device_info": {
    "device_name": "Work Laptop",
    "platform": "windows",
    "app_version": "1.0.0"
  }
}
```

**Response:**
```json
{
  "success": true,
  "user": {
    "user_id": "user-uuid",
    "email": "john.doe@acme.com",
    "full_name": "John Doe",
    "role": "user"
  },
  "organisation": {
    "org_id": "acme-uuid",
    "org_name": "ACME Corporation"
  },
  "tokens": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "Bearer",
    "expires_in": 3600
  },
  "session": {
    "session_id": "session-uuid",
    "device_name": "Work Laptop",
    "created_at": "2025-12-10T10:30:00Z"
  }
}
```

**Error Responses:**
| Status | Code | Description |
|--------|------|-------------|
| 401 | `INVALID_CREDENTIALS` | Email or password incorrect |
| 401 | `ACCOUNT_DISABLED` | User account is disabled |
| 401 | `EMAIL_NOT_VERIFIED` | Email verification pending |
| 429 | `TOO_MANY_ATTEMPTS` | Account temporarily locked |

---

### 9.3 POST /auth/logout

**Purpose**: Invalidate current session and tokens.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "logout_all_devices": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully logged out",
  "sessions_terminated": 1
}
```

---

### 9.4 POST /auth/refresh

**Purpose**: Refresh expired access token using refresh token.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response:**
```json
{
  "success": true,
  "tokens": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...(new)",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...(new)",
    "token_type": "Bearer",
    "expires_in": 3600
  }
}
```

**Error Responses:**
| Status | Code | Description |
|--------|------|-------------|
| 401 | `INVALID_REFRESH_TOKEN` | Refresh token is invalid |
| 401 | `TOKEN_EXPIRED` | Refresh token has expired |
| 401 | `TOKEN_REVOKED` | Token has been revoked |

---

### 9.5 GET /auth/me

**Purpose**: Get current authenticated user's profile.

**Headers:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Response:**
```json
{
  "user": {
    "user_id": "user-uuid",
    "email": "john.doe@acme.com",
    "full_name": "John Doe",
    "role": "user",
    "status": "active",
    "email_verified": true,
    "created_at": "2025-12-10T10:30:00Z",
    "last_login": "2025-12-10T14:00:00Z"
  },
  "organisation": {
    "org_id": "acme-uuid",
    "org_name": "ACME Corporation",
    "role_in_org": "user"
  },
  "preferences": {
    "language": "en",
    "hotkey": "Ctrl+Shift+P",
    "auto_confirm": true,
    "show_tooltips": true
  },
  "stats": {
    "total_sessions": 45,
    "queries_this_month": 120,
    "last_activity": "2025-12-10T14:30:00Z"
  }
}
```

---

### 9.6 POST /auth/verify-email

**Purpose**: Verify user email address with verification token.

**Request:**
```json
{
  "verification_token": "verify-token-abc123"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Email verified successfully",
  "user": {
    "user_id": "user-uuid",
    "email": "john.doe@acme.com",
    "status": "active"
  }
}
```

---

### 9.7 POST /auth/forgot-password

**Purpose**: Request password reset email.

**Request:**
```json
{
  "email": "john.doe@acme.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "If an account exists with this email, a password reset link has been sent"
}
```

---

### 9.8 POST /auth/reset-password

**Purpose**: Reset password using reset token.

**Request:**
```json
{
  "reset_token": "reset-token-xyz789",
  "new_password": "new_secure_password_456"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Password reset successfully",
  "sessions_terminated": 3
}
```

---

## 10. Health APIs

### 10.1 GET /health

**Purpose**: Basic health check.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-10T10:30:00Z",
  "version": "1.0.0"
}
```

---

### 10.2 GET /health/services

**Purpose**: Detailed service health status.

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "database": {
      "status": "healthy",
      "latency_ms": 5
    },
    "vector_db": {
      "status": "healthy",
      "latency_ms": 12,
      "total_vectors": 15000
    },
    "cv_pipeline": {
      "status": "healthy",
      "model_loaded": true,
      "model_version": "yolov8n"
    },
    "ocr_service": {
      "status": "healthy",
      "engine": "paddleocr"
    },
    "ai_engine": {
      "status": "healthy",
      "model": "llama-3-8b",
      "gpu_available": true
    }
  },
  "uptime_sec": 86400
}
```

---

## 11. API Flow Diagram - Complete User Journey

```mermaid
sequenceDiagram
    participant User
    participant Tauri as Tauri App
    participant API as FastAPI
    participant Services as Backend Services

    Note over User,Services: Phase 1 - User Login
    User->>Tauri: Opens Pedagogy App
    User->>Tauri: Enters credentials
    Tauri->>API: POST /auth/login
    API-->>Tauri: tokens + session_id

    Note over User,Services: Phase 2 - User Query
    User->>Tauri: Types "How do I submit invoice?"
    Tauri->>API: POST /query/rag
    API->>Services: Vector search
    Services-->>API: Matching steps
    API-->>Tauri: Instruction steps

    Note over User,Services: Phase 3 - Screen Capture
    User->>Tauri: Navigates to relevant screen
    User->>Tauri: Presses hotkey or clicks Capture
    Tauri->>Tauri: Capture screenshot
    Tauri->>API: POST /capture/context
    API->>Services: CV + OCR processing
    Services-->>API: screen_state
    API-->>Tauri: UI elements detected

    Note over User,Services: Phase 4 - AI Guidance
    Tauri->>API: POST /infer/guidance
    API->>Services: Match elements + Generate guidance
    Services-->>API: halo_targets
    API-->>Tauri: Guidance + halos

    Note over User,Services: Phase 5 - Display Halos
    Tauri->>API: POST /halo/overlay
    Tauri->>User: Shows glowing highlight on Submit button
```

---

## 12. Error Response Format

All API errors follow this standard format:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": {
      "field": "additional context"
    }
  },
  "timestamp": "2025-12-10T10:30:00Z",
  "request_id": "req-uuid"
}
```

### Common Error Codes

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `INVALID_REQUEST` | Malformed request body |
| 400 | `MISSING_FIELD` | Required field missing |
| 401 | `UNAUTHORIZED` | Authentication required |
| 403 | `FORBIDDEN` | Insufficient permissions |
| 404 | `NOT_FOUND` | Resource doesn't exist |
| 409 | `CONFLICT` | Resource state conflict |
| 422 | `VALIDATION_ERROR` | Data validation failed |
| 429 | `RATE_LIMITED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error |
| 503 | `SERVICE_UNAVAILABLE` | Service temporarily down |

---

## 13. API Summary Table

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/capture/context` | POST | Process screenshot |
| `/capture/elements/{id}` | GET | Get detected elements |
| `/query/rag` | POST | Search knowledge base |
| `/query/history/{id}` | GET | Get query history |
| `/infer/guidance` | POST | Generate AI guidance |
| `/infer/steps/{id}` | GET | Get session steps |
| `/halo/overlay` | POST | Display halos |
| `/halo/clear` | POST | Clear halos |
| `/org/profile` | GET | Get organisation profile |
| `/org/onboard` | POST | Complete org onboarding |
| `/org/upload-knowledge` | POST | Upload knowledge base documents |
| `/org/onboarding-status` | GET | Check onboarding progress |
| `/auth/register` | POST | Register new user |
| `/auth/login` | POST | User login |
| `/auth/logout` | POST | User logout |
| `/auth/refresh` | POST | Refresh access token |
| `/auth/me` | GET | Get current user profile |
| `/auth/verify-email` | POST | Verify email address |
| `/auth/forgot-password` | POST | Request password reset |
| `/auth/reset-password` | POST | Reset password |
| `/health` | GET | Basic health check |
| `/health/services` | GET | Detailed health status |

---

## How to View These Diagrams

1. **VS Code**: Install "Markdown Preview Mermaid Support" extension
2. **GitHub**: Push this file - GitHub renders Mermaid natively
3. **Online**: Use [Mermaid Live Editor](https://mermaid.live/)
