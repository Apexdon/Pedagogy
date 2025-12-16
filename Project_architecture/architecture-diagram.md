# Pedagogy - High-Level End-to-End Architecture Diagram

## 1. Complete System Architecture

```mermaid
flowchart TB
    subgraph USER["👤 USER LAYER"]
        U[User]
        Screen[User's Screen<br/>Websites/Apps/PDFs]
    end

    subgraph TAURI["🖥️ TAURI DESKTOP APP"]
        subgraph Frontend["Frontend (React + TypeScript)"]
            ChatUI[Chat Window UI]
            SearchBar["Ask Pedagogy" Search Bar]
            Settings[Settings & Onboarding]
            HaloCanvas[Halo Overlay Canvas]
        end

        subgraph RustCore["Rust Core Layer"]
            ScreenCapture[Screenshot Capture<br/>High DPI]
            HotkeyListener[Hotkey Listener<br/>Ctrl+Shift+P]
            FileAccess[Local File Access]
            APIBridge[Frontend ↔ Backend Bridge]
        end
    end

    subgraph FASTAPI["🐍 PYTHON FASTAPI BACKEND"]
        Router[Request Router]

        subgraph Endpoints["API Endpoints"]
            E1[POST /capture/context]
            E2[POST /query/rag]
            E3[POST /infer/guidance]
            E4[POST /halo/overlay]
        end

        SessionMgr[Session Manager]
    end

    subgraph CV["🔍 COMPUTER VISION PIPELINE"]
        subgraph Preprocess["Preprocessing"]
            Resize[Resize to Fixed Resolution]
            Normalize[Color Normalization]
            Contrast[Contrast Amplification]
        end

        subgraph Detection["Detection"]
            YOLO[YOLOv8/v11<br/>UI Element Detection]
            OCR[EasyOCR<br/>Text Extraction]
        end

        ContextEngine[UI Context Engine<br/>Fuse YOLO + OCR]
    end

    subgraph RAG["📚 RAG KNOWLEDGE SYSTEM"]
        subgraph KnowledgeStore["Knowledge Store"]
            JSONKb[JSON Knowledge Base<br/>SOPs, Manuals, Walkthroughs]
            VectorDB[(ChromaDB / FAISS<br/>Vector Database)]
        end

        Embedder[SentenceTransformers<br/>Embedding Generator]
        Retriever[Semantic Retriever<br/>Top-K Matching]
    end

    subgraph AI["🧠 AI MATCHING ENGINE"]
        LLM[LLM<br/>GPT-4.1 or Claude 3.5 Sonnet
]
        Matcher[Label Proximity Matcher]
        GuidanceGen[Guidance Generator]
    end

    subgraph ORG["🏢 ORGANISATION DATA"]
        OrgData[(Organisation<br/>Knowledge Base + Vectors + Config)]
    end

    %% User Interactions
    U -->|Types Query| ChatUI
    U -->|Views| Screen
    U -->|Presses Hotkey| HotkeyListener

    %% Frontend to Rust
    ChatUI --> APIBridge
    SearchBar --> APIBridge

    %% Rust Operations
    ScreenCapture -->|Capture| Screen
    HotkeyListener --> ScreenCapture

    %% Rust to Backend
    APIBridge --> Router
    ScreenCapture --> E1

    %% Backend Routing
    Router --> Endpoints
    SessionMgr --> ORG

    %% CV Pipeline
    E1 --> Preprocess
    Preprocess --> YOLO
    Preprocess --> OCR
    YOLO --> ContextEngine
    OCR --> ContextEngine

    %% RAG Pipeline
    E2 --> Embedder
    Embedder --> VectorDB
    VectorDB --> Retriever
    JSONKb --> Retriever

    %% AI Processing
    ContextEngine --> LLM
    Retriever --> LLM
    LLM --> Matcher
    Matcher --> GuidanceGen

    %% Output
    GuidanceGen --> E4
    E4 --> APIBridge
    APIBridge --> HaloCanvas
    HaloCanvas -->|Overlay| Screen
```

## 2. End-to-End User Flow

```mermaid
sequenceDiagram
    autonumber
    participant U as 👤 User
    participant UI as 🖥️ React UI
    participant Rust as ⚙️ Rust Core
    participant API as 🐍 FastAPI
    participant RAG as 📚 RAG System
    participant CV as 🔍 CV Pipeline
    participant AI as 🧠 AI Engine
    participant Halo as ✨ Halo Overlay

    Note over U,Halo: PHASE 1: User Login
    U->>UI: Opens Pedagogy Desktop App
    U->>UI: Logs in with credentials
    UI->>API: POST /auth/login
    API-->>UI: Authentication successful

    Note over U,Halo: PHASE 2: Query Submission
    U->>UI: Types question: "How do I submit an invoice?"
    UI->>Rust: Send query via Tauri Command
    Rust->>API: POST /query/rag

    Note over U,Halo: PHASE 3: Knowledge Retrieval
    API->>RAG: Search organisation's knowledge base
    RAG->>RAG: Embed user query
    RAG->>RAG: Vector search in org's embeddings
    RAG->>RAG: Semantic filter top-K matches
    RAG-->>API: Relevant instruction steps
    API-->>UI: Ready to capture screen

    Note over U,Halo: PHASE 4: Screen Capture & Analysis
    U->>UI: Navigates to relevant screen
    U->>Rust: Presses hotkey (Ctrl+Shift+P) or clicks Capture
    Rust->>Rust: Capture full-res screenshot
    Rust->>API: POST /capture/context (screenshot + query)
    API->>CV: Process screenshot
    CV->>CV: Preprocess (resize, normalize, contrast)
    par Parallel Processing
        CV->>CV: YOLO detects UI elements
        CV->>CV: PaddleOCR extracts text
    end
    CV->>CV: Fuse into screen-state JSON
    CV-->>API: UI Context ready

    Note over U,Halo: PHASE 5: AI Reasoning
    API->>AI: Merge CV context + RAG results + query
    AI->>AI: Match screen elements to instructions
    AI->>AI: Determine next action
    AI->>AI: Generate halo targets with bboxes
    AI-->>API: Guidance response

    Note over U,Halo: PHASE 6: Halo Rendering
    API->>Rust: POST /halo/overlay (halo_targets)
    Rust->>UI: Pass halo data
    UI->>Halo: Draw glowing borders
    UI->>Halo: Show tooltips
    Halo-->>U: Visual guidance on screen!
```

## 3. State Machine Diagram

```mermaid
stateDiagram-v2
    [*] --> IDLE: App launches

    IDLE --> QUERYING: User submits query

    QUERYING --> READY: RAG returns relevant steps
    QUERYING --> IDLE: No results found

    READY --> CAPTURING: User triggers capture
    READY --> QUERYING: User modifies query
    READY --> IDLE: User cancels

    CAPTURING --> GUIDING: Analysis complete
    CAPTURING --> READY: CV/OCR failed (retry)

    GUIDING --> GUIDING: User completes step (next step)
    GUIDING --> CAPTURING: User recaptures screen
    GUIDING --> QUERYING: User asks new question
    GUIDING --> IDLE: Task complete / Cancel

    note right of IDLE
        User hasn't asked anything
    end note

    note right of READY
        Waiting for user to navigate
        and trigger screen capture
    end note

    note right of GUIDING
        Halos displayed
        Step-by-step tracking
    end note
```

## 4. Component Interaction Diagram

```mermaid
flowchart LR
    subgraph Desktop["Desktop Environment"]
        App1[Browser]
        App2[Spreadsheet]
        App3[PDF Viewer]
    end

    subgraph Pedagogy["Pedagogy App"]
        subgraph Layer1["Presentation Layer"]
            React[React UI]
            Canvas[Halo Canvas]
        end

        subgraph Layer2["Core Layer"]
            Rust[Rust Engine]
        end

        subgraph Layer3["Backend Layer"]
            FastAPI[FastAPI Server]
        end

        subgraph Layer4["Intelligence Layer"]
            CV[CV Pipeline]
            RAG[RAG System]
            AI[AI Engine]
        end

        subgraph Layer5["Data Layer"]
            OrgConfig[(Org Config)]
            Vectors[(Vector DB)]
            KB[(Knowledge Base)]
        end
    end

    Desktop <-->|Screen Capture| Rust
    Canvas -->|Overlay| Desktop

    React <--> Rust
    Rust <--> FastAPI
    FastAPI <--> CV
    FastAPI <--> RAG
    FastAPI <--> AI

    CV --> AI
    RAG --> AI

    RAG <--> Vectors
    RAG <--> KB
    FastAPI <--> OrgConfig
```

## 5. Data Flow Diagram

```mermaid
flowchart TD
    subgraph Input["📥 INPUT"]
        Query[User Query]
        Screenshot[Screenshot]
        OrgContext[Org Context]
    end

    subgraph Processing["⚙️ PROCESSING"]
        subgraph CVProcess["CV Processing"]
            IMG[Image] --> PRE[Preprocess]
            PRE --> DET[YOLO Detection]
            PRE --> TXT[OCR Extraction]
            DET --> FUSE[Fusion]
            TXT --> FUSE
        end

        subgraph RAGProcess["RAG Processing"]
            QRY[Query] --> EMB[Embed]
            EMB --> SEARCH[Vector Search]
            SEARCH --> FILTER[Semantic Filter]
        end

        subgraph AIProcess["AI Processing"]
            CTX[Screen Context] --> MERGE[Merge]
            STEPS[Retrieved Steps] --> MERGE
            MERGE --> MATCH[Element Matching]
            MATCH --> GEN[Generate Guidance]
        end
    end

    subgraph Output["📤 OUTPUT"]
        Halos[Halo Targets]
        Instructions[Step Instructions]
        Tooltips[UI Tooltips]
    end

    Query --> QRY
    Screenshot --> IMG
    OrgContext --> SEARCH

    FUSE --> CTX
    FILTER --> STEPS

    GEN --> Halos
    GEN --> Instructions
    GEN --> Tooltips
```

## 6. Capture Trigger Flow

```mermaid
flowchart TD
    Start([User Submits Query]) --> RAG[RAG Retrieves Steps]
    RAG --> Ready[Ready State]

    Ready --> Navigate[User Navigates to Screen]
    Navigate --> Trigger{Capture Trigger}

    Trigger -->|Hotkey| Capture[Capture Screenshot]
    Trigger -->|UI Button| Capture
    Trigger -->|Auto-capture| Capture

    Capture --> Process[CV Pipeline Processes]
    Process --> AI[AI Generates Guidance]
    AI --> Halo([Display Halos])

    Halo --> Next{User Action}
    Next -->|Next Step| Capture
    Next -->|New Query| Start
    Next -->|Done| End([Session Complete])
```

## How to View These Diagrams

1. **VS Code**: Install "Markdown Preview Mermaid Support" extension
2. **GitHub**: Paste this file - GitHub renders Mermaid natively
3. **Online**: Use [Mermaid Live Editor](https://mermaid.live/)
4. **Export**: Use Mermaid CLI to export as PNG/SVG
