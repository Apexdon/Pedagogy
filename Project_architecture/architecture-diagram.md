# Pedagogy - Complete System Architecture

## 1. High-Level System Overview

```mermaid
flowchart TB
    subgraph User["👤 USER"]
        U[User]
        TargetApp[Target Application<br/>Salesforce/CRM/etc.]
    end

    subgraph TauriApp["🖥️ TAURI DESKTOP APP"]
        subgraph ReactFrontend["Frontend (React + TypeScript)"]
            subgraph Pages["Pages"]
                GP[GuidancePage]
                HP[HistoryPage]
                PP[ProfilePage]
            end

            subgraph Components["Components"]
                GQP[GuidanceQueryPanel]
                GSP[GuidanceSessionPanel]
                HaloComp[HaloOverlay Component]
            end

            subgraph StateLayer["State Management (Zustand)"]
                GuidanceStore[guidanceStore]
                DetectionStore[detectionStore]
                AuthStore[authStore]
            end

            subgraph Hooks["Hooks"]
                UseGuidance[useGuidance]
                UseGuidanceCoord[useGuidanceCoordinator]
                UseDetection[useDetection]
            end

            subgraph Services["Frontend Services"]
                GuidanceCoord[GuidanceCoordinator<br/>Singleton]
            end

            subgraph APIClients["API Clients (Axios)"]
                GuidanceAPI[guidance.ts]
                DetectionAPI[detection.ts]
                HaloAPI[halo.ts]
                KnowledgeAPI[knowledge.ts]
            end
        end

        subgraph RustLayer["Rust Core Layer"]
            subgraph TauriCommands["Tauri Commands"]
                DetectionCmds[detection_commands.rs]
                HaloCmds[halo_commands.rs]
                SidepanelCmds[sidepanel_commands.rs]
            end

            subgraph RustModules["Rust Modules"]
                DetectionMod[Detection Module<br/>Window Monitor]
                OverlayMod[Overlay Module<br/>Halo Renderer]
                SidepanelMod[Sidepanel Module]
            end

            OverlayWindow[Overlay Window<br/>Transparent]
            SidepanelWindow[Sidepanel Window]
        end
    end

    subgraph Backend["🐍 PYTHON FASTAPI BACKEND"]
        subgraph APIRoutes["API Routes"]
            GuidanceRoute[/guidance<br/>Session Management]
            KnowledgeRoute[/knowledge<br/>RAG & Upload]
            CaptureRoute[/capture<br/>CV Analysis]
            OrgRoute[/organisations<br/>Config]
            AuthRoute[/auth<br/>Authentication]
        end

        subgraph AIEngine["AI Engine"]
            GuidanceGen[GuidanceGenerator<br/>Orchestrator]
            AIReasoner[AIReasoner<br/>LLM Integration]
            ElementMatcher[ElementMatcher<br/>Fuzzy Matching]
            StepTracker[StepTracker<br/>Session State]
        end

        subgraph LLMClients["LLM Clients"]
            OpenAIClient[OpenAI Client<br/>GPT-4.1]
            OllamaClient[Ollama Client<br/>Local LLM]
        end

        subgraph CVPipeline["CV Pipeline"]
            CVService[CVService]
            OmniParser[OmniParser v2<br/>UI Detection]
            YOLOv11[YOLO v11<br/>Fallback]
            EasyOCR[EasyOCR<br/>Text Extraction]
        end

        subgraph RAGSystem["RAG System"]
            KnowledgeService[KnowledgeService]
            SentenceTransformers[SentenceTransformers<br/>all-MiniLM-L6-v2]
            ChromaDB[(ChromaDB<br/>Vector Store)]
        end

        subgraph DataLayer["Data Layer"]
            SQLite[(SQLite/PostgreSQL<br/>Sessions, Users, Orgs)]
            FileStorage[File Storage<br/>Uploads, Screenshots]
        end
    end

    %% User Interactions
    U -->|Query & Actions| GP
    U -->|Views| TargetApp
    TargetApp -.->|Captured| DetectionMod

    %% Frontend Flow
    GP --> GQP
    GP --> GSP
    GSP --> HaloComp
    GQP --> UseGuidance
    GSP --> UseGuidanceCoord
    UseGuidance --> GuidanceStore
    UseGuidanceCoord --> GuidanceCoord
    GuidanceCoord --> GuidanceStore
    GuidanceStore --> GuidanceAPI

    %% Tauri IPC
    GuidanceCoord -->|invoke| DetectionCmds
    GuidanceCoord -->|invoke| HaloCmds
    DetectionCmds --> DetectionMod
    HaloCmds --> OverlayMod
    OverlayMod --> OverlayWindow
    OverlayWindow -.->|Overlay on| TargetApp

    %% Frontend to Backend HTTP
    GuidanceAPI -->|HTTP| GuidanceRoute
    KnowledgeAPI -->|HTTP| KnowledgeRoute
    DetectionAPI -->|HTTP| CaptureRoute

    %% Backend Internal Flow
    GuidanceRoute --> GuidanceGen
    GuidanceGen --> AIReasoner
    GuidanceGen --> ElementMatcher
    GuidanceGen --> StepTracker
    AIReasoner --> OpenAIClient
    AIReasoner --> OllamaClient
    StepTracker --> SQLite

    GuidanceRoute --> CVService
    CVService --> OmniParser
    CVService --> YOLOv11
    CVService --> EasyOCR

    KnowledgeRoute --> KnowledgeService
    KnowledgeService --> SentenceTransformers
    KnowledgeService --> ChromaDB
```

## 2. Complete Data Flow Sequence

```mermaid
sequenceDiagram
    autonumber
    participant U as 👤 User
    participant UI as 🖥️ React UI
    participant Store as 📦 Zustand Store
    participant Coord as 🎯 GuidanceCoordinator
    participant Tauri as ⚙️ Tauri (Rust)
    participant API as 🐍 FastAPI
    participant RAG as 📚 RAG System
    participant CV as 🔍 CV Pipeline
    participant LLM as 🧠 LLM (GPT-4.1)
    participant DB as 💾 Database

    Note over U,DB: PHASE 1: Guidance Generation
    U->>UI: Types "How do I submit an invoice?"
    UI->>Store: generate(query)
    Store->>API: POST /guidance/generate

    API->>RAG: Query knowledge base
    RAG->>RAG: Embed query (SentenceTransformers)
    RAG->>RAG: Vector search ChromaDB
    RAG-->>API: Relevant documentation chunks

    API->>LLM: Generate steps (query + RAG context)
    Note right of LLM: Structured prompt with<br/>JSON output format
    LLM-->>API: Steps array with targets

    API->>DB: Create GuidanceSession
    API->>DB: Create GuidanceSteps
    API-->>Store: {session_id, steps[], status}
    Store-->>UI: Display guidance steps

    Note over U,DB: PHASE 2: Start Visual Guidance
    U->>UI: Clicks "Start Visual Guidance"
    UI->>Coord: initialize(session, steps)
    Coord->>API: GET /organisations/{id}
    API-->>Coord: {target_window_pattern, target_app_name}

    Coord->>Tauri: start_window_monitoring(pattern)
    Tauri->>Tauri: Poll for matching window

    Note over U,DB: PHASE 3: Window Detection & Capture
    Tauri-->>Coord: window-match event (window found!)
    Coord->>Tauri: capture_screen()
    Tauri->>Tauri: High DPI screenshot
    Tauri-->>Coord: Base64 PNG

    Coord->>API: POST /guidance/sessions/{id}/capture
    Note right of API: Optional: Tauri screenshot<br/>or backend window capture

    Note over U,DB: PHASE 4: CV Analysis
    API->>CV: analyze_screen(image)

    par Parallel Processing
        CV->>CV: OmniParser detects UI elements
        CV->>CV: EasyOCR extracts text
    end

    CV->>CV: Fuse labels (associate text with elements)
    CV-->>API: DetectedElements[] + TextRegions[]

    Note over U,DB: PHASE 5: Element Matching
    API->>API: ElementMatcher.match()
    Note right of API: Label similarity (fuzzy)<br/>Type compatibility<br/>Keyword presence

    API-->>Coord: HaloTarget {bbox, element, confidence}

    Note over U,DB: PHASE 6: Halo Display
    Coord->>Tauri: show_halo(target)
    Tauri->>Tauri: Create/update overlay window
    Tauri-->>U: Visual highlight on target element!

    Note over U,DB: PHASE 7: Step Completion
    U->>UI: Clicks "Next Step" (or completes action)
    UI->>Store: advance()
    Store->>API: POST /sessions/{id}/advance
    API->>DB: Mark step COMPLETED, next step CURRENT
    API-->>Store: Updated session state

    Coord->>Coord: Re-capture for next step
    Note over Coord,DB: Loop back to Phase 3
```

## 3. Component Architecture Layers

```mermaid
flowchart LR
    subgraph Presentation["PRESENTATION LAYER"]
        direction TB
        Pages[Pages<br/>GuidancePage, HistoryPage]
        Components[Components<br/>Panels, Overlays, UI]
    end

    subgraph State["STATE LAYER"]
        direction TB
        Zustand[Zustand Stores<br/>guidance, detection, auth]
        Hooks[React Hooks<br/>useGuidance, useGuidanceCoordinator]
    end

    subgraph Orchestration["ORCHESTRATION LAYER"]
        direction TB
        Coordinator[GuidanceCoordinator<br/>Session lifecycle, Capture loop]
        APIClient[API Clients<br/>Axios HTTP calls]
    end

    subgraph Desktop["DESKTOP LAYER (Tauri/Rust)"]
        direction TB
        Commands[Tauri Commands<br/>IPC Bridge]
        Detection[Window Detection<br/>Pattern matching, Polling]
        Capture[Screen Capture<br/>High DPI, Region capture]
        Overlay[Overlay Window<br/>Transparent, Always-on-top]
    end

    subgraph API["API LAYER (FastAPI)"]
        direction TB
        Routes[REST Endpoints<br/>/guidance, /capture, /knowledge]
        Services[Services<br/>CVService, KnowledgeService]
    end

    subgraph AI["AI LAYER"]
        direction TB
        Generator[GuidanceGenerator<br/>Orchestration]
        Reasoner[AIReasoner<br/>LLM prompting]
        Matcher[ElementMatcher<br/>Fuzzy matching]
        Tracker[StepTracker<br/>Session state]
    end

    subgraph ML["ML LAYER"]
        direction TB
        LLM[LLM Clients<br/>OpenAI, Ollama]
        CV[CV Pipeline<br/>OmniParser, YOLO, EasyOCR]
        RAG[RAG System<br/>Embeddings, ChromaDB]
    end

    subgraph Data["DATA LAYER"]
        direction TB
        SQL[(SQLite/PostgreSQL)]
        Vector[(ChromaDB)]
        Files[File Storage]
    end

    Presentation --> State
    State --> Orchestration
    Orchestration --> Desktop
    Orchestration --> API
    API --> AI
    AI --> ML
    ML --> Data
    API --> Data
```

## 4. Session State Machine

```mermaid
stateDiagram-v2
    [*] --> Idle: App Start

    Idle --> Generating: User submits query
    Generating --> Active: Steps generated successfully
    Generating --> Error: Generation failed

    Active --> VisualActive: Start visual guidance
    Active --> Paused: User pauses
    Active --> Completed: All steps completed
    Active --> Abandoned: User abandons

    VisualActive --> WindowSearching: Initialize coordinator
    WindowSearching --> Capturing: Window found
    WindowSearching --> VisualActive: Window lost

    Capturing --> Matching: CV analysis complete
    Matching --> HaloDisplayed: Match found (confidence > 0.6)
    Matching --> Capturing: No match, retry

    HaloDisplayed --> Capturing: User advances step
    HaloDisplayed --> Paused: User pauses
    HaloDisplayed --> Completed: Final step completed

    state VisualActive {
        WindowSearching --> Capturing
        Capturing --> Matching
        Matching --> HaloDisplayed
        HaloDisplayed --> Capturing
    }

    Paused --> Active: Resume
    Paused --> VisualActive: Resume with visual
    Paused --> Abandoned: User abandons

    Error --> Idle: Reset
    Completed --> Idle: New session
    Abandoned --> Idle: New session
```

## 5. Element Matching Algorithm Flow

```mermaid
flowchart TD
    Input["Input: Current Step + Detected Elements"]

    Input --> ExtractTarget["Extract Step Target Info"]
    ExtractTarget --> TargetSpec["target_element_type: 'button'<br/>target_element_label: 'Create'<br/>action_type: 'click'<br/>keywords: ['create', 'new']"]

    TargetSpec --> Loop["For Each Detected Element"]

    subgraph Scoring["Scoring Pipeline"]
        Loop --> NormalizeType["Normalize Element Type<br/>(btn→button, img→icon)"]

        NormalizeType --> LabelScore["1. Label Similarity Score"]
        LabelScore --> LabelCalc["Exact match: 1.0<br/>Contains: 0.9<br/>Fuzzy (SequenceMatcher): 0.0-1.0"]

        LabelCalc --> TypeScore["2. Type Compatibility Score"]
        TypeScore --> TypeMatrix["Compatibility Matrix:<br/>click→[button, link, icon] ✓<br/>type→[input, textfield] ✓<br/>select→[dropdown, combobox] ✓"]

        TypeMatrix --> KeywordScore["3. Keyword Bonus"]
        KeywordScore --> KeywordCalc["Each keyword in label: +0.1"]

        KeywordCalc --> CombineScore["Combine Weighted Scores<br/>total = 0.5×label + 0.3×type + 0.2×keyword"]
    end

    CombineScore --> NextElem{More Elements?}
    NextElem -->|Yes| Loop
    NextElem -->|No| SelectBest["Select Highest Score"]

    SelectBest --> ThresholdCheck{Confidence > 0.6?}
    ThresholdCheck -->|Yes| ReturnTarget["Return HaloTarget<br/>{bbox, element, confidence, reasons}"]
    ThresholdCheck -->|No| NoMatch["Return: No match found"]
```

## 6. GuidanceCoordinator Lifecycle

```mermaid
flowchart TD
    Start([User clicks Start Visual Guidance])

    Start --> Init["initialize(session, steps)"]
    Init --> LoadOrg["Load org target app settings"]
    LoadOrg --> CreateOverlay["Create overlay window (Tauri)"]
    CreateOverlay --> StartMonitor["Start window monitoring"]

    StartMonitor --> WaitWindow{Window Match?}
    WaitWindow -->|No, polling...| WaitWindow
    WaitWindow -->|Yes| EmitFound["Emit: target_window_found"]

    EmitFound --> CaptureScreen["Capture screenshot"]
    CaptureScreen --> SendToBackend["POST /sessions/{id}/capture"]
    SendToBackend --> CVAnalysis["Backend: CV analysis"]
    CVAnalysis --> Matching["Backend: Element matching"]

    Matching --> MatchResult{Match Found?}
    MatchResult -->|Yes| ShowHalo["show_halo(target)"]
    MatchResult -->|No, confidence < 0.6| RetryCapture["Retry after delay"]
    RetryCapture --> CaptureScreen

    ShowHalo --> WaitAction{User Action?}
    WaitAction -->|Advance| AdvanceStep["POST /sessions/{id}/advance"]
    WaitAction -->|Skip| SkipStep["POST /sessions/{id}/skip"]
    WaitAction -->|Pause| PauseSession["pause()"]

    AdvanceStep --> MoreSteps{More Steps?}
    SkipStep --> MoreSteps
    MoreSteps -->|Yes| CaptureScreen
    MoreSteps -->|No| Complete["Session COMPLETED"]

    PauseSession --> WaitResume{Resume?}
    WaitResume -->|Yes| CaptureScreen
    WaitResume -->|No, Abandon| Cleanup

    Complete --> Cleanup["Stop monitoring, Destroy overlay"]
    Cleanup --> End([End])

    %% Window Lost Path
    WaitWindow -->|Window Lost| EmitLost["Emit: target_window_lost"]
    EmitLost --> WaitWindow
```

## 7. API Endpoints Map

```mermaid
flowchart LR
    subgraph Auth["/auth"]
        direction TB
        A1["POST /login"]
        A2["POST /register"]
        A3["POST /refresh"]
    end

    subgraph Guidance["/guidance"]
        direction TB
        G1["POST /generate<br/>Create session + steps"]
        G2["GET /sessions<br/>List user sessions"]
        G3["GET /sessions/{id}<br/>Get session details"]
        G4["GET /sessions/{id}/state<br/>Lightweight state poll"]
        G5["POST /sessions/{id}/start<br/>Start active guidance"]
        G6["POST /sessions/{id}/capture<br/>Capture & analyze"]
        G7["POST /sessions/{id}/advance<br/>Next step"]
        G8["POST /sessions/{id}/skip<br/>Skip step"]
        G9["POST /sessions/{id}/goto/{n}<br/>Jump to step"]
        G10["POST /sessions/{id}/pause"]
        G11["POST /sessions/{id}/resume"]
        G12["POST /sessions/{id}/abandon"]
    end

    subgraph Knowledge["/knowledge"]
        direction TB
        K1["GET /knowledge-bases<br/>List KBs"]
        K2["POST /knowledge-bases<br/>Create KB"]
        K3["POST /upload-knowledge<br/>Upload docs"]
        K4["POST /query/rag<br/>Semantic search"]
    end

    subgraph Capture["/capture"]
        direction TB
        C1["POST /analyze<br/>Full CV analysis"]
        C2["POST /detect-ui<br/>UI detection only"]
        C3["POST /extract-text<br/>OCR only"]
    end

    subgraph Orgs["/organisations"]
        direction TB
        O1["CRUD operations"]
        O2["Target app config"]
    end
```

## 8. Technology Stack Mind Map

```mermaid
mindmap
    root((Pedagogy))
        Frontend
            React 18
            TypeScript
            Zustand
                guidanceStore
                detectionStore
                authStore
            TanStack Query
            Axios
            Vite
        Desktop
            Tauri 2.x
            Rust
            Window APIs
                Monitoring
                Capture
            Overlay Rendering
            Sidepanel
        Backend
            Python 3.10+
            FastAPI
            SQLAlchemy Async
            Pydantic v2
            Uvicorn
        AI/ML
            LLM
                OpenAI GPT-4.1
                Ollama (Local)
            Computer Vision
                OmniParser v2
                YOLO v11
                EasyOCR
            RAG
                SentenceTransformers
                all-MiniLM-L6-v2
        Storage
            SQLite (Dev)
            PostgreSQL (Prod)
            ChromaDB (Vectors)
            File System (Uploads)
```

## 9. Database Schema Relationships

```mermaid
erDiagram
    User ||--o{ GuidanceSession : creates
    User }o--|| Organisation : belongs_to
    Organisation ||--o{ KnowledgeBase : has
    Organisation ||--o{ GuidanceSession : owns

    GuidanceSession ||--o{ GuidanceStep : contains
    GuidanceSession ||--o{ GuidanceCapture : has

    GuidanceSession {
        uuid session_id PK
        uuid user_id FK
        uuid org_id FK
        string query
        enum status
        int current_step
        int total_steps
        uuid kb_id FK
        json rag_context
        datetime created_at
    }

    GuidanceStep {
        uuid step_id PK
        uuid session_id FK
        int step_number
        string instruction
        string target_element_type
        string target_element_label
        json target_bbox
        enum action_type
        string action_value
        float match_confidence
        enum status
    }

    GuidanceCapture {
        uuid capture_id PK
        uuid session_id FK
        uuid step_id FK
        enum capture_type
        string screenshot_path
        json screen_state
        int element_count
        int processing_time_ms
    }

    Organisation {
        uuid org_id PK
        string org_name
        string target_app_name
        string target_window_pattern
        string target_process_name
    }

    KnowledgeBase {
        uuid kb_id PK
        uuid org_id FK
        string name
        string description
        int document_count
        int chunk_count
    }
```

## 10. Complete User Journey Flow

```mermaid
flowchart TD
    Start([User Opens Pedagogy App])

    Start --> Login[Login / Authentication]
    Login --> Dashboard[View Dashboard]
    Dashboard --> AskQuery["Enter Query:<br/>'How do I submit an invoice?'"]

    AskQuery --> Generate["Backend: Generate Guidance"]

    subgraph Generation["Guidance Generation"]
        Generate --> RAGSearch[RAG: Search knowledge base]
        RAGSearch --> LLMCall[LLM: Generate structured steps]
        LLMCall --> SaveSession[Save session to database]
    end

    SaveSession --> DisplaySteps[Display steps in UI]

    DisplaySteps --> StartVisual{Start Visual Guidance?}
    StartVisual -->|No| ManualMode[Manual step-by-step navigation]
    StartVisual -->|Yes| InitCoord[Initialize GuidanceCoordinator]

    InitCoord --> LoadTargetApp[Load org's target app settings]
    LoadTargetApp --> StartMonitor[Start window monitoring]

    StartMonitor --> WindowLoop{Target Window Found?}
    WindowLoop -->|No| WindowLoop
    WindowLoop -->|Yes| CaptureScreen[Capture screenshot]

    CaptureScreen --> CVAnalyze["CV Pipeline:<br/>OmniParser + EasyOCR"]
    CVAnalyze --> MatchElement[Match step target to UI element]

    MatchElement --> ConfidenceCheck{Confidence > 0.6?}
    ConfidenceCheck -->|No| RetryCapture[Retry after 2 seconds]
    RetryCapture --> CaptureScreen
    ConfidenceCheck -->|Yes| ShowHalo[Display Halo highlight]

    ShowHalo --> UserAction{User completes action}
    UserAction -->|Advance| NextStep[Move to next step]
    UserAction -->|Skip| SkipStep[Skip current step]
    UserAction -->|Pause| PauseSession[Pause session]

    NextStep --> MoreSteps{More steps?}
    SkipStep --> MoreSteps
    MoreSteps -->|Yes| CaptureScreen
    MoreSteps -->|No| Complete[Session completed!]

    PauseSession --> Resume{Resume?}
    Resume -->|Yes| CaptureScreen
    Resume -->|No| Abandon[Abandon session]

    ManualMode --> ManualNext[User clicks through steps]
    ManualNext --> ManualDone{All done?}
    ManualDone -->|No| ManualNext
    ManualDone -->|Yes| Complete

    Complete --> History[Save to session history]
    Abandon --> History
    History --> End([End])
```

---

## How to View These Diagrams

1. **VS Code**: Install "Markdown Preview Mermaid Support" extension
2. **GitHub**: GitHub renders Mermaid natively in markdown files
3. **Online**: Use [Mermaid Live Editor](https://mermaid.live/)
4. **Export**: Use Mermaid CLI (`mmdc`) to export as PNG/SVG

---

## Key Files Reference

| Layer | Key Files |
|-------|-----------|
| **Frontend Pages** | `src/pages/dashboard/GuidancePage.tsx` |
| **Frontend Components** | `src/components/guidance/GuidanceSessionPanel.tsx`, `GuidanceQueryPanel.tsx` |
| **State Management** | `src/stores/guidanceStore.ts`, `detectionStore.ts` |
| **Coordinator** | `src/services/GuidanceCoordinator.ts` |
| **API Clients** | `src/api/guidance.ts`, `detection.ts`, `halo.ts` |
| **Tauri Commands** | `src-tauri/src/commands/detection_commands.rs`, `halo_commands.rs` |
| **Backend Routes** | `backend/app/api/guidance.py`, `knowledge.py`, `cv_analysis.py` |
| **AI Engine** | `backend/app/ai_engine/guidance_generator.py`, `matcher.py`, `reasoner.py` |
| **Services** | `backend/app/services/cv_service.py`, `knowledge_service.py` |
| **Models** | `backend/app/models/guidance.py`, `organisation.py` |
