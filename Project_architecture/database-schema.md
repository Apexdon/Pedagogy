# Pedagogy - Database Schema Design

## 1. Entity Relationship Diagram (ERD)

```mermaid
erDiagram
    ORGANISATION ||--o{ USERS : has
    ORGANISATION ||--o{ KNOWLEDGE_BASE : owns
    ORGANISATION ||--o{ EMBEDDING_INDEX : owns
    ORGANISATION ||--o{ SESSION : tracks

    USERS ||--o{ SESSION : initiates
    USERS ||--o{ QUERY_HISTORY : makes
    USERS ||--|| USER_SETTINGS : has

    KNOWLEDGE_BASE ||--o{ INSTRUCTION_STEP : contains
    KNOWLEDGE_BASE ||--o{ DOCUMENT : stores

    DOCUMENT ||--o{ DOCUMENT_CHUNK : splits
    DOCUMENT_CHUNK ||--o{ EMBEDDING : has

    INSTRUCTION_STEP ||--o{ STEP_TARGET : references

    SESSION ||--o{ CAPTURE_EVENT : logs
    SESSION ||--o{ GUIDANCE_EVENT : produces

    CAPTURE_EVENT ||--o{ UI_ELEMENT : detects
    CAPTURE_EVENT ||--|| SCREEN_STATE : produces

    GUIDANCE_EVENT ||--o{ HALO_TARGET : generates

    QUERY_HISTORY }o--|| SESSION : belongs

    EMBEDDING_INDEX ||--o{ EMBEDDING : contains

    ORGANISATION {
        uuid org_id PK
        string org_name
        string org_slug UK
        string logo_path
        string primary_color
        timestamp created_at
        timestamp updated_at
        boolean is_active
    }

    USERS {
        uuid user_id PK
        uuid org_id FK
        string email UK
        string name
        string role
        timestamp created_at
        timestamp last_login
        boolean is_active
    }

    USER_SETTINGS {
        uuid settings_id PK
        uuid user_id FK
        string hotkey
        boolean auto_capture_on_query
        json preferences
    }

    KNOWLEDGE_BASE {
        uuid kb_id PK
        uuid org_id FK
        string kb_name
        string description
        string version
        timestamp created_at
        timestamp updated_at
        boolean is_active
    }

    DOCUMENT {
        uuid doc_id PK
        uuid kb_id FK
        string doc_name
        string doc_type
        string file_path
        text content_raw
        int total_chunks
        timestamp uploaded_at
        timestamp processed_at
    }

    DOCUMENT_CHUNK {
        uuid chunk_id PK
        uuid doc_id FK
        int chunk_index
        text chunk_text
        int start_char
        int end_char
        json metadata
    }

    INSTRUCTION_STEP {
        uuid step_id PK
        uuid kb_id FK
        int step_number
        string instruction_text
        string step_type
        string target_element
        json preconditions
        json postconditions
        uuid next_step_id FK
    }

    STEP_TARGET {
        uuid target_id PK
        uuid step_id FK
        string target_type
        string target_label
        string target_selector
        json expected_bbox
        float confidence_threshold
    }

    EMBEDDING_INDEX {
        uuid index_id PK
        uuid org_id FK
        string index_name
        string model_name
        int dimension
        int total_vectors
        timestamp created_at
        timestamp last_updated
    }

    EMBEDDING {
        uuid embedding_id PK
        uuid index_id FK
        uuid chunk_id FK
        blob vector
        json metadata
        timestamp created_at
    }

    SESSION {
        uuid session_id PK
        uuid user_id FK
        uuid org_id FK
        string session_state
        string original_query
        timestamp started_at
        timestamp ended_at
        json session_metadata
    }

    CAPTURE_EVENT {
        uuid capture_id PK
        uuid session_id FK
        int screenshot_width
        int screenshot_height
        float capture_duration_ms
        int elements_detected
        int ocr_texts_extracted
        timestamp captured_at
    }

    SCREEN_STATE {
        uuid state_id PK
        uuid capture_id FK
        json elements_json
        json ocr_results
        json layout_info
        timestamp created_at
    }

    UI_ELEMENT {
        uuid element_id PK
        uuid capture_id FK
        string element_type
        string element_label
        json bbox
        float confidence
        json ocr_text
        json attributes
    }

    GUIDANCE_EVENT {
        uuid guidance_id PK
        uuid session_id FK
        uuid step_id FK
        string guidance_text
        json matched_elements
        timestamp generated_at
    }

    HALO_TARGET {
        uuid halo_id PK
        uuid guidance_id FK
        uuid element_id FK
        string label
        json bbox
        string halo_style
        string tooltip_text
        int display_order
    }

    QUERY_HISTORY {
        uuid query_id PK
        uuid user_id FK
        uuid session_id FK
        text query_text
        json retrieved_steps
        int retrieval_count
        float retrieval_duration_ms
        timestamp queried_at
    }
```

## 2. SQL Schema Diagram (Tables & Relationships)

```mermaid
flowchart TB
    subgraph CORE["CORE TABLES"]
        direction TB
        ORG["organisations
        ─────────────────
        PK org_id UUID
        org_name VARCHAR
        org_slug VARCHAR UK
        logo_path VARCHAR
        primary_color VARCHAR
        created_at TIMESTAMP
        updated_at TIMESTAMP
        is_active BOOLEAN"]

        USR["users
        ─────────────────
        PK user_id UUID
        FK org_id UUID
        email VARCHAR UK
        name VARCHAR
        role VARCHAR
        created_at TIMESTAMP
        last_login TIMESTAMP
        is_active BOOLEAN"]

        SETTINGS["user_settings
        ─────────────────
        PK settings_id UUID
        FK user_id UUID UK
        hotkey VARCHAR
        auto_capture_on_query BOOLEAN
        preferences JSONB"]
    end

    subgraph KNOWLEDGE["KNOWLEDGE MANAGEMENT"]
        direction TB
        KB["knowledge_bases
        ─────────────────
        PK kb_id UUID
        FK org_id UUID
        kb_name VARCHAR
        description TEXT
        version VARCHAR
        created_at TIMESTAMP
        updated_at TIMESTAMP
        is_active BOOLEAN"]

        DOC["documents
        ─────────────────
        PK doc_id UUID
        FK kb_id UUID
        doc_name VARCHAR
        doc_type VARCHAR
        file_path VARCHAR
        content_raw TEXT
        total_chunks INTEGER
        uploaded_at TIMESTAMP
        processed_at TIMESTAMP"]

        CHUNK["document_chunks
        ─────────────────
        PK chunk_id UUID
        FK doc_id UUID
        chunk_index INTEGER
        chunk_text TEXT
        start_char INTEGER
        end_char INTEGER
        metadata JSONB"]

        STEP["instruction_steps
        ─────────────────
        PK step_id UUID
        FK kb_id UUID
        step_number INTEGER
        instruction_text TEXT
        step_type VARCHAR
        target_element VARCHAR
        preconditions JSONB
        postconditions JSONB
        FK next_step_id UUID"]

        TRGT["step_targets
        ─────────────────
        PK target_id UUID
        FK step_id UUID
        target_type VARCHAR
        target_label VARCHAR
        target_selector VARCHAR
        expected_bbox JSONB
        confidence_threshold DECIMAL"]
    end

    subgraph EMBEDDINGS["EMBEDDINGS & VECTORS"]
        direction TB
        IDX["embedding_indexes
        ─────────────────
        PK index_id UUID
        FK org_id UUID
        index_name VARCHAR
        model_name VARCHAR
        dimension INTEGER
        total_vectors INTEGER
        created_at TIMESTAMP
        last_updated TIMESTAMP"]

        EMB["embeddings
        ─────────────────
        PK embedding_id UUID
        FK index_id UUID
        FK chunk_id UUID
        vector VECTOR
        metadata JSONB
        created_at TIMESTAMP"]
    end

    subgraph RUNTIME["RUNTIME & EVENTS"]
        direction TB
        SESS["sessions
        ─────────────────
        PK session_id UUID
        FK user_id UUID
        session_state VARCHAR
        original_query TEXT
        started_at TIMESTAMP
        ended_at TIMESTAMP
        session_metadata JSONB"]

        CAP_EVT["capture_events
        ─────────────────
        PK capture_id UUID
        FK session_id UUID
        screenshot_width INTEGER
        screenshot_height INTEGER
        capture_duration_ms DECIMAL
        elements_detected INTEGER
        ocr_texts_extracted INTEGER
        captured_at TIMESTAMP"]

        SCREEN["screen_states
        ─────────────────
        PK state_id UUID
        FK capture_id UUID UK
        elements_json JSONB
        ocr_results JSONB
        layout_info JSONB
        created_at TIMESTAMP"]

        UI_EL["ui_elements
        ─────────────────
        PK element_id UUID
        FK capture_id UUID
        element_type VARCHAR
        element_label VARCHAR
        bbox JSONB
        confidence DECIMAL
        ocr_text JSONB
        attributes JSONB"]

        GUIDE["guidance_events
        ─────────────────
        PK guidance_id UUID
        FK session_id UUID
        FK step_id UUID
        guidance_text TEXT
        matched_elements JSONB
        generated_at TIMESTAMP"]

        HALO["halo_targets
        ─────────────────
        PK halo_id UUID
        FK guidance_id UUID
        FK element_id UUID
        label VARCHAR
        bbox JSONB
        halo_style VARCHAR
        tooltip_text TEXT
        display_order INTEGER"]

        QHIST["query_history
        ─────────────────
        PK query_id UUID
        FK user_id UUID
        FK session_id UUID
        query_text TEXT
        retrieved_steps JSONB
        retrieval_count INTEGER
        retrieval_duration_ms DECIMAL
        queried_at TIMESTAMP"]
    end

    %% Relationships
    ORG --> USR
    ORG --> KB
    ORG --> IDX
    USR --> SETTINGS
    USR --> SESS
    USR --> QHIST
    KB --> DOC
    KB --> STEP
    DOC --> CHUNK
    CHUNK --> EMB
    IDX --> EMB
    STEP --> TRGT
    SESS --> CAP_EVT
    SESS --> GUIDE
    SESS --> QHIST
    CAP_EVT --> SCREEN
    CAP_EVT --> UI_EL
    GUIDE --> HALO
    GUIDE --> STEP
    HALO --> UI_EL
```

## 3. SQL DDL Statements

```sql
-- =============================================
-- PEDAGOGY DATABASE SCHEMA
-- PostgreSQL with pgvector extension
-- =============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- =============================================
-- CORE ORGANISATION TABLES
-- =============================================

CREATE TABLE organisations (
    org_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_name VARCHAR(255) NOT NULL,
    org_slug VARCHAR(100) UNIQUE NOT NULL,
    logo_path VARCHAR(500),
    primary_color VARCHAR(7) DEFAULT '#3B82F6',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_organisations_slug ON organisations(org_slug);
CREATE INDEX idx_organisations_active ON organisations(is_active);

-- =============================================
-- USER TABLES
-- =============================================

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('admin', 'user', 'viewer')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_users_org ON users(org_id);
CREATE INDEX idx_users_email ON users(email);

CREATE TABLE user_settings (
    settings_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    hotkey VARCHAR(50) DEFAULT 'Ctrl+Shift+P',
    auto_capture_on_query BOOLEAN DEFAULT FALSE,
    preferences JSONB DEFAULT '{}'::jsonb
);

-- =============================================
-- KNOWLEDGE BASE TABLES
-- =============================================

CREATE TABLE knowledge_bases (
    kb_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    kb_name VARCHAR(255) NOT NULL,
    description TEXT,
    version VARCHAR(50) DEFAULT '1.0.0',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_knowledge_bases_org ON knowledge_bases(org_id);

CREATE TABLE documents (
    doc_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kb_id UUID NOT NULL REFERENCES knowledge_bases(kb_id) ON DELETE CASCADE,
    doc_name VARCHAR(255) NOT NULL,
    doc_type VARCHAR(50) NOT NULL CHECK (doc_type IN ('sop', 'manual', 'walkthrough', 'ui_description', 'other')),
    file_path VARCHAR(500),
    content_raw TEXT,
    total_chunks INTEGER DEFAULT 0,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_documents_kb ON documents(kb_id);
CREATE INDEX idx_documents_type ON documents(doc_type);

CREATE TABLE document_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    doc_id UUID NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    UNIQUE(doc_id, chunk_index)
);

CREATE INDEX idx_document_chunks_doc ON document_chunks(doc_id);

-- =============================================
-- INSTRUCTION STEP TABLES
-- =============================================

CREATE TABLE instruction_steps (
    step_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kb_id UUID NOT NULL REFERENCES knowledge_bases(kb_id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    instruction_text TEXT NOT NULL,
    step_type VARCHAR(50) NOT NULL CHECK (step_type IN ('navigation', 'input', 'click', 'select', 'verify', 'wait', 'other')),
    target_element VARCHAR(255),
    preconditions JSONB DEFAULT '[]'::jsonb,
    postconditions JSONB DEFAULT '[]'::jsonb,
    next_step_id UUID REFERENCES instruction_steps(step_id) ON DELETE SET NULL
);

CREATE INDEX idx_instruction_steps_kb ON instruction_steps(kb_id);
CREATE INDEX idx_instruction_steps_number ON instruction_steps(kb_id, step_number);

CREATE TABLE step_targets (
    target_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    step_id UUID NOT NULL REFERENCES instruction_steps(step_id) ON DELETE CASCADE,
    target_type VARCHAR(50) NOT NULL CHECK (target_type IN ('button', 'input', 'dropdown', 'checkbox', 'link', 'text', 'menu', 'tab', 'other')),
    target_label VARCHAR(255),
    target_selector VARCHAR(255),
    expected_bbox JSONB,
    confidence_threshold DECIMAL(3,2) DEFAULT 0.80 CHECK (confidence_threshold >= 0 AND confidence_threshold <= 1)
);

CREATE INDEX idx_step_targets_step ON step_targets(step_id);

-- =============================================
-- EMBEDDING TABLES (Vector Search)
-- =============================================

CREATE TABLE embedding_indexes (
    index_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    index_name VARCHAR(255) NOT NULL,
    model_name VARCHAR(100) NOT NULL DEFAULT 'all-MiniLM-L6-v2',
    dimension INTEGER NOT NULL DEFAULT 384,
    total_vectors INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_embedding_indexes_org ON embedding_indexes(org_id);

CREATE TABLE embeddings (
    embedding_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    index_id UUID NOT NULL REFERENCES embedding_indexes(index_id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES document_chunks(chunk_id) ON DELETE CASCADE,
    vector VECTOR(384),  -- Adjust dimension based on model
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_embeddings_index ON embeddings(index_id);
CREATE INDEX idx_embeddings_chunk ON embeddings(chunk_id);
CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);

-- =============================================
-- SESSION & EVENT TABLES
-- =============================================

CREATE TABLE sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    session_state VARCHAR(20) NOT NULL DEFAULT 'idle' CHECK (session_state IN ('idle', 'querying', 'ready', 'capturing', 'guiding', 'completed', 'cancelled')),
    original_query TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE,
    session_metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_state ON sessions(session_state);
CREATE INDEX idx_sessions_started ON sessions(started_at DESC);

CREATE TABLE capture_events (
    capture_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    screenshot_width INTEGER NOT NULL,
    screenshot_height INTEGER NOT NULL,
    capture_duration_ms DECIMAL(10,2),
    elements_detected INTEGER DEFAULT 0,
    ocr_texts_extracted INTEGER DEFAULT 0,
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_capture_events_session ON capture_events(session_id);

CREATE TABLE screen_states (
    state_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    capture_id UUID UNIQUE NOT NULL REFERENCES capture_events(capture_id) ON DELETE CASCADE,
    elements_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    ocr_results JSONB NOT NULL DEFAULT '[]'::jsonb,
    layout_info JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ui_elements (
    element_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    capture_id UUID NOT NULL REFERENCES capture_events(capture_id) ON DELETE CASCADE,
    element_type VARCHAR(50) NOT NULL CHECK (element_type IN ('button', 'input', 'dropdown', 'checkbox', 'text', 'link', 'menu', 'tab', 'table', 'modal', 'other')),
    element_label VARCHAR(255),
    bbox JSONB NOT NULL,
    confidence DECIMAL(3,2) CHECK (confidence >= 0 AND confidence <= 1),
    ocr_text JSONB,
    attributes JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_ui_elements_capture ON ui_elements(capture_id);
CREATE INDEX idx_ui_elements_type ON ui_elements(element_type);

-- =============================================
-- GUIDANCE & HALO TABLES
-- =============================================

CREATE TABLE guidance_events (
    guidance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    step_id UUID REFERENCES instruction_steps(step_id) ON DELETE SET NULL,
    guidance_text TEXT NOT NULL,
    matched_elements JSONB DEFAULT '[]'::jsonb,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_guidance_events_session ON guidance_events(session_id);

CREATE TABLE halo_targets (
    halo_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    guidance_id UUID NOT NULL REFERENCES guidance_events(guidance_id) ON DELETE CASCADE,
    element_id UUID REFERENCES ui_elements(element_id) ON DELETE SET NULL,
    label VARCHAR(255) NOT NULL,
    bbox JSONB NOT NULL,
    halo_style VARCHAR(50) DEFAULT 'glow' CHECK (halo_style IN ('glow', 'border', 'pulse', 'arrow', 'highlight')),
    tooltip_text TEXT,
    display_order INTEGER DEFAULT 0
);

CREATE INDEX idx_halo_targets_guidance ON halo_targets(guidance_id);

-- =============================================
-- QUERY HISTORY TABLE
-- =============================================

CREATE TABLE query_history (
    query_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(session_id) ON DELETE SET NULL,
    query_text TEXT NOT NULL,
    retrieved_steps JSONB DEFAULT '[]'::jsonb,
    retrieval_count INTEGER DEFAULT 0,
    retrieval_duration_ms DECIMAL(10,2),
    queried_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_query_history_user ON query_history(user_id);
CREATE INDEX idx_query_history_session ON query_history(session_id);
CREATE INDEX idx_query_history_queried ON query_history(queried_at DESC);

-- =============================================
-- HELPER FUNCTIONS & TRIGGERS
-- =============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
CREATE TRIGGER update_organisations_updated_at
    BEFORE UPDATE ON organisations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_knowledge_bases_updated_at
    BEFORE UPDATE ON knowledge_bases
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_embedding_indexes_updated_at
    BEFORE UPDATE ON embedding_indexes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to update document chunk count
CREATE OR REPLACE FUNCTION update_document_chunk_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE documents SET total_chunks = total_chunks + 1 WHERE doc_id = NEW.doc_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE documents SET total_chunks = total_chunks - 1 WHERE doc_id = OLD.doc_id;
    END IF;
    RETURN NULL;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_chunk_count
    AFTER INSERT OR DELETE ON document_chunks
    FOR EACH ROW EXECUTE FUNCTION update_document_chunk_count();

-- Function to update embedding vector count
CREATE OR REPLACE FUNCTION update_embedding_vector_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE embedding_indexes SET total_vectors = total_vectors + 1, last_updated = CURRENT_TIMESTAMP WHERE index_id = NEW.index_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE embedding_indexes SET total_vectors = total_vectors - 1, last_updated = CURRENT_TIMESTAMP WHERE index_id = OLD.index_id;
    END IF;
    RETURN NULL;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_vector_count
    AFTER INSERT OR DELETE ON embeddings
    FOR EACH ROW EXECUTE FUNCTION update_embedding_vector_count();

-- =============================================
-- VIEWS FOR COMMON QUERIES
-- =============================================

-- View: Organisation summary with stats
CREATE VIEW v_organisation_summary AS
SELECT
    o.org_id,
    o.org_name,
    o.org_slug,
    o.is_active,
    COUNT(DISTINCT u.user_id) AS user_count,
    COUNT(DISTINCT kb.kb_id) AS knowledge_base_count,
    COUNT(DISTINCT s.session_id) AS total_sessions,
    MAX(s.started_at) AS last_session_at
FROM organisations o
LEFT JOIN users u ON o.org_id = u.org_id
LEFT JOIN knowledge_bases kb ON o.org_id = kb.org_id
LEFT JOIN sessions s ON s.user_id = u.user_id
GROUP BY o.org_id, o.org_name, o.org_slug, o.is_active;

-- View: Session details with events
CREATE VIEW v_session_details AS
SELECT
    s.session_id,
    s.session_state,
    s.original_query,
    s.started_at,
    s.ended_at,
    u.name AS user_name,
    o.org_name,
    COUNT(DISTINCT ce.capture_id) AS capture_events,
    COUNT(DISTINCT ge.guidance_id) AS guidance_events
FROM sessions s
JOIN users u ON s.user_id = u.user_id
JOIN organisations o ON u.org_id = o.org_id
LEFT JOIN capture_events ce ON s.session_id = ce.session_id
LEFT JOIN guidance_events ge ON s.session_id = ge.session_id
GROUP BY s.session_id, s.session_state, s.original_query, s.started_at, s.ended_at, u.name, o.org_name;

-- =============================================
-- SAMPLE VECTOR SEARCH FUNCTION
-- =============================================

-- Function for semantic search
CREATE OR REPLACE FUNCTION search_similar_chunks(
    p_org_id UUID,
    p_query_vector VECTOR(384),
    p_limit INTEGER DEFAULT 5
)
RETURNS TABLE (
    chunk_id UUID,
    chunk_text TEXT,
    doc_name VARCHAR(255),
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.chunk_id,
        dc.chunk_text,
        d.doc_name,
        1 - (e.vector <=> p_query_vector) AS similarity
    FROM embeddings e
    JOIN embedding_indexes ei ON e.index_id = ei.index_id
    JOIN document_chunks dc ON e.chunk_id = dc.chunk_id
    JOIN documents d ON dc.doc_id = d.doc_id
    WHERE ei.org_id = p_org_id
    ORDER BY e.vector <=> p_query_vector
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;
```

## 4. Table Relationships Summary

```mermaid
flowchart TD
    subgraph Core["Core Entities"]
        ORG[organisations]
        USER[users]
        SETTINGS[user_settings]
    end

    subgraph Knowledge["Knowledge Management"]
        KB[knowledge_bases]
        DOC[documents]
        CHUNK[document_chunks]
        STEP[instruction_steps]
        TARGET[step_targets]
    end

    subgraph Embeddings["Embeddings & Vectors"]
        INDEX[embedding_indexes]
        EMB[embeddings]
    end

    subgraph Runtime["Runtime Events"]
        SESSION[sessions]
        CAPTURE[capture_events]
        SCREEN[screen_states]
        ELEMENT[ui_elements]
        GUIDANCE[guidance_events]
        HALO[halo_targets]
        QUERY[query_history]
    end

    ORG --> USER
    ORG --> KB
    ORG --> INDEX

    USER --> SETTINGS
    USER --> SESSION
    USER --> QUERY

    KB --> DOC
    KB --> STEP
    DOC --> CHUNK
    CHUNK --> EMB
    STEP --> TARGET
    INDEX --> EMB

    SESSION --> CAPTURE
    SESSION --> GUIDANCE
    SESSION --> QUERY

    CAPTURE --> SCREEN
    CAPTURE --> ELEMENT

    GUIDANCE --> HALO
    GUIDANCE -.-> STEP

    HALO -.-> ELEMENT
```

## 5. Data Flow Through Tables
These are tables (Runtime Tables) that get data during a guidance session not Setup/Static Tables

```mermaid
sequenceDiagram
    participant Client
    participant Session as sessions
    participant Query as query_history
    participant Embeddings as embeddings
    participant Steps as instruction_steps
    participant Capture as capture_events
    participant Elements as ui_elements
    participant Guidance as guidance_events
    participant Halos as halo_targets

    Client->>Session: Create new session
    Client->>Query: Submit user query
    Query->>Embeddings: Vector similarity search
    Embeddings-->>Query: Return matching chunks
    Query->>Steps: Retrieve instruction steps

    Note over Session: State: ready

    Client->>Capture: Trigger screen capture
    Capture->>Elements: Store detected UI elements

    Note over Session: State: capturing

    Steps->>Guidance: Generate guidance
    Guidance->>Halos: Create halo targets
    Halos->>Elements: Link to UI elements

    Note over Session: State: guiding

    Halos-->>Client: Return halo_targets for rendering
```

## 6. Tables Overview

| Category | Table | Description |
|----------|-------|-------------|
| **Core** | `organisations` | Organisation configuration (single per deployment) |
| **Core** | `users` | User accounts linked to the organisation |
| **Core** | `user_settings` | Per-user UI and capture preferences |
| **Knowledge** | `knowledge_bases` | Organisation knowledge containers |
| **Knowledge** | `documents` | SOPs, manuals, walkthroughs |
| **Knowledge** | `document_chunks` | Chunked text for embedding |
| **Knowledge** | `instruction_steps` | Step-by-step guidance instructions |
| **Knowledge** | `step_targets` | UI elements each step targets |
| **Embeddings** | `embedding_indexes` | Vector index metadata |
| **Embeddings** | `embeddings` | Vector embeddings for RAG search |
| **Runtime** | `sessions` | User guidance sessions |
| **Runtime** | `capture_events` | Screenshot capture metadata |
| **Runtime** | `screen_states` | Captured screen analysis results |
| **Runtime** | `ui_elements` | Detected UI elements per capture |
| **Runtime** | `guidance_events` | Generated guidance records |
| **Runtime** | `halo_targets` | Halo overlay instructions |
| **Runtime** | `query_history` | User query logs with results |

## How to View These Diagrams

1. **VS Code**: Install "Markdown Preview Mermaid Support" extension
2. **GitHub**: Push this file - GitHub renders Mermaid natively
3. **Online**: Use [Mermaid Live Editor](https://mermaid.live/)
4. **Database Tools**: Import the SQL DDL into PostgreSQL or use tools like dbdiagram.io
