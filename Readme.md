
PEDAGOGY – Technical Architecture (Tauri + Python + CV + RAG)

1. SYSTEM OVERVIEW
Pedagogy is a desktop AI assistant that analyzes what the user is viewing (websites, desktop apps, spreadsheets, PDFs), interprets the UI visually (no DOM access), retrieves organisation-specific knowledge, and provides step-by-step guidance with halo overlays.
Its architecture is composed of 5 primary layers:
Tauri App (Frontend + Rust Core)


Local Python FastAPI Backend


Computer Vision & OCR Pipeline


RAG Retrieval System (Local Embeddings + Vector DB)


AI Reasoning + Guidance Generation



2. ARCHITECTURE LAYERS IN DETAIL

2.1 TAURI DESKTOP APP LAYER
Tech stack
Tauri (Rust core + Webview frontend)


Frontend: React + Typescript


Rust sidecar binaries for privileged operations


Responsibilities
Provides the UI/UX for the assistant


Displays chat window, search interface, halo overlays


Sends commands to backend (OCR, CV, RAG)


Shows results and instructions to user


Executes secure screenshot capture via Rust


Modules
Frontend Webview (React)
Chat window UI


“Ask Pedagogy” search bar


Settings & onboarding interface


Transparent halo overlay canvas


Rust Layer
Captures screenshots (high DPI)


Ensures sandboxed security


Manages local file access


Bridges between frontend ↔ Python backend



Data Flow (Frontend → Backend)
User Query → React UI → Tauri Command → FastAPI → CV + RAG → Guidance → React UI → Show Halos


2.2 PYTHON FASTAPI BACKEND LAYER
Tech stack
FastAPI


uvicorn


Pydantic for schemas


BackgroundTasks for async CV processing


Responsibilities
Receives screenshot + user query


Routes request to OCR/CV pipeline


Retrieves organization-specific knowledge (RAG)


Generates instruction guidance


Returns halo bounding boxes


Core Endpoints
POST /capture/context      → CV segmentation + OCR
POST /query/rag            → search JSON KB + vector DB
POST /infer/guidance       → combine context + RAG into final steps
POST /halo/overlay         → send halo instructions to Tauri


3. COMPUTER VISION & OCR PIPELINE
Tech stack
YOLOv8 / YOLOv11 (UI element detection)


PaddleOCR (high accuracy text extraction)


OpenCV (image preprocessing)


LayoutParser (optional layout segmentation)



3.1 Detection Targets
Pedagogy identifies:
Text blocks


Input fields


Buttons


Checkboxes


Dropdowns


Tables


Menu items


Modal dialogs




3.2 Processing Pipeline
3.2.1 Screenshot Preprocessing
Resize to fixed resolution


Normalize color + reduce noise


Contrast amplification



3.2.2 UI Element Detection (YOLO)
The YOLO model returns:
{
  "bbox": [x1, y1, x2, y2],
  "confidence": 0.92,
  "class": "input_field"
}

3.2.3 OCR Extraction
Crop regions detected as text-containing


Run PaddleOCR


Output structured text mapping


3.2.4 UI Context Engine
Fuse YOLO + OCR outputs


Tag elements with semantic meaning


Build a screen-state JSON
 Example output:


{
  "elements": [
    { "type": "button", "label": "Save", "bbox": [...] },
    { "type": "text", "content": "Logistics", "bbox": [...] },
    { "type": "input", "id": "#shippingMethod", "bbox": [...] }
  ]
}


4. RAG KNOWLEDGE SYSTEM
Tech stack
ChromaDB or FAISS


SentenceTransformers (all-MiniLM or better)


Local JSON KB per organisation



4.1 Knowledge Source
Each organisation provides either of the following:
SOPs


Manuals


Walkthroughs


Screenshots


UI descriptions


All converted into JSON structures like:
{
  "step_number": 1,
  "instruction": "Click Logistics Tab",
  "target": "logistics",
  "type": "navigation"
}


4.2 Embedding Pipeline
Convert JSON instructions → text chunks


Create embeddings using SentenceTransformers


Store in a vector db


Index by organisation ID



4.3 Retrieval Flow
User Query → Embed → Vector Search → Top K Matches → Semantic Filter → Return


5. AI REASONING ENGINE
Tech stack
Local LLM (e.g., Llama-3, Mistral)


Or cloud LLM (OpenAI, Claude) depending on requirement


Tasks
Merge user’s query with CV context + RAG results


Identify which screen elements match instruction steps


Determine next logical action


Generate halo mapping instructions



6. HALO RENDERING SYSTEM (NO DOM ACCESS)
Tech stack
Tauri overlay window


HTML Canvas / SVG overlay


YOLO bounding box → Pixel mapping


Operation
Backend returns:


{
  "halo_targets": [
    { "label": "Shipping Method Dropdown", "bbox": [...] }
  ]
}

Tauri frontend draws halos:


glowing borders


highlight animations


text tooltips


This overlay appears above the client’s real UI, without DOM access.

7. SINGLE-ORGANISATION DEPLOYMENT MODEL

Pedagogy is deployed as a personalized instance for each organisation. When an organisation purchases Pedagogy, they receive a dedicated deployment configured specifically for their needs.

7.1 Deployment Architecture
Each organisation gets:
 Its own Pedagogy instance
 Its own JSON knowledge base (pre-loaded during onboarding)
 Its own embeddings (generated from their documents)
 Organisation-specific branding and configuration

7.2 Onboarding Process
When an organisation is onboarded:
 Admin configures organisation profile (name, branding, settings)
 Knowledge base documents are uploaded (SOPs, manuals, walkthroughs)
 System generates embeddings from uploaded documents
 Users are invited to register under this organisation

7.3 User Experience
 Users authenticate against their organisation's Pedagogy instance
 All queries automatically use the organisation's knowledge base
 No organisation detection needed - context is always known
 Simplified flow: Query → Capture → Guidance



8. SECURITY MODEL
No data leaves the machine
Screenshots processed locally
Never stored
Only bounding box metadata survives


Organisation isolation
Each org’s JSON and embeddings stored separately
Prevents keylogging or illegal scraping claims



9. END-TO-END FLOW (Simplified Single-Organisation)

9.1 FLOW OVERVIEW

User Opens Pedagogy (desktop)
        ↓
User logs in (authenticated against their org's instance)
        ↓
User asks a question
        ↓
User presses capture hotkey OR clicks capture button
        ↓
Rust engine captures full-resolution screenshot
        ↓
FastAPI receives screenshot + query (org context implicit)
        ↓
OCR + YOLO detect UI elements
        ↓
Context Engine builds screen state
        ↓
RAG finds relevant instruction steps from org's knowledge base
        ↓
AI determines next instruction
        ↓
FastAPI sends halo targets to Tauri
        ↓
Halo overlay draws on user's screen


9.2 STATE MACHINE

The guidance system operates as a simple state machine:

┌──────────────┐
│    IDLE      │ ← User hasn't asked anything
└──────┬───────┘
       │ User submits query
       ▼
┌──────────────┐
│   QUERYING   │ ← Processing query via RAG
└──────┬───────┘
       │ User triggers capture (hotkey/button)
       ▼
┌──────────────┐
│  CAPTURING   │ ← Full screenshot + CV pipeline
└──────┬───────┘
       │ Analysis complete
       ▼
┌──────────────┐
│   GUIDING    │ ← Halos displayed, tracking steps
└──────┬───────┘
       │ User completes task / asks new question
       ▼
     (back to IDLE or QUERYING)


9.3 ORGANISATION PROFILE SCHEMA

Each organisation's deployment is configured with:

{
  "org_id": "acme_corp",
  "org_name": "ACME Corporation",

  "branding": {
    "logo_path": "assets/logo.png",
    "primary_color": "#FF5733"
  },

  "settings": {
    "hotkey": "Ctrl+Shift+P",
    "auto_capture_on_query": false,
    "default_language": "en"
  },

  "knowledge_base_path": "kb/",
  "embeddings_path": "vectors/"
}


9.4 CAPTURE TRIGGER OPTIONS

Users can trigger screen capture via:
 Hotkey: Ctrl+Shift+P (configurable)
 UI Button: "Capture Screen" button in chat interface
 Auto-capture: Optional setting to capture immediately after query

The capture flow:
 User asks question: "How do I submit an invoice?"
 User navigates to relevant screen
 User presses hotkey or clicks capture
 Pedagogy analyzes screen and provides guidance


9.5 FRONTEND FLOW

React UI guides user through the simplified process:

┌────────────────────────────────────────────────────────────┐
│  Ask Pedagogy: [How do I submit an invoice?    ] [Ask]    │
└────────────────────────────────────────────────────────────┘

           ↓ (after query)

┌────────────────────────────────────────────────────────────┐
│  📋 Query: "How do I submit an invoice?"                   │
│  ────────────────────────────────────────────────────────  │
│  Navigate to the screen you need help with, then:          │
│                                                            │
│  [📸 Capture Screen]  or press Ctrl+Shift+P               │
└────────────────────────────────────────────────────────────┘

           ↓ (after capture + analysis)

┌────────────────────────────────────────────────────────────┐
│  ✓ Step 1 of 5: Click the "Invoices" tab                  │
│  ────────────────────────────────────────────────────────  │
│  [Highlighted on your screen]                              │
│                                                            │
│  [Next Step]  [Recapture]  [Done]                         │
└────────────────────────────────────────────────────────────┘


