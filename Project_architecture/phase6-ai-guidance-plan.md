# Phase 6: AI Guidance Engine - Implementation Plan

## Overview

The AI Guidance Engine is the core intelligence layer that connects:
1. **Screen Detection** (Phase 5) - UI elements detected via OmniParser
2. **Knowledge Base** (Phase 3) - RAG system with organization procedures
3. **LLM Reasoning** - Claude/local LLM for contextual guidance generation
4. **Halo Overlay** (Phase 7) - Visual highlighting of target elements

The engine analyzes the current screen state, matches detected UI elements to procedural steps from the knowledge base, and generates step-by-step guidance with visual targeting.

---

## Architecture

```
                    +------------------+
                    |  User Question   |
                    +--------+---------+
                             |
                             v
+----------------+   +-------+--------+   +------------------+
|   RAG System   +-->|  AI Guidance   |<--+  Screen State    |
| (Phase 3)      |   |    Engine      |   | (Phase 5)        |
+----------------+   +-------+--------+   +------------------+
                             |
           +-----------------+-----------------+
           |                 |                 |
           v                 v                 v
    +------+------+   +------+------+   +------+------+
    |   Element   |   |  Guidance   |   |    Halo     |
    |   Matcher   |   |  Generator  |   |   Targets   |
    +-------------+   +-------------+   +-------------+
```

---

## Directory Structure

```
backend/
├── app/
│   ├── ai_engine/
│   │   ├── __init__.py
│   │   ├── matcher.py          # Element-to-instruction matching
│   │   ├── reasoner.py         # LLM-based reasoning
│   │   ├── guidance_generator.py  # Step generation
│   │   ├── step_tracker.py     # Progress tracking
│   │   └── llm_client.py       # LLM provider abstraction
│   ├── api/
│   │   └── guidance.py         # Guidance API endpoints
│   ├── models/
│   │   └── guidance.py         # DB models for sessions/steps
│   ├── schemas/
│   │   └── guidance.py         # Pydantic schemas
│   └── services/
│       └── guidance_service.py # Orchestration service

frontend/
├── src/
│   ├── api/
│   │   └── guidance.ts         # Update with full guidance API
│   ├── types/
│   │   └── guidance.ts         # Update with halo types
│   ├── stores/
│   │   └── guidanceStore.ts    # Guidance state management
│   └── hooks/
│       └── useGuidance.ts      # Guidance hook
```

---

## Implementation Tasks

### Task 6.1: Database Models for Guidance Sessions

**File**: `backend/app/models/guidance.py`

Create models to persist guidance sessions and steps:

```python
# GuidanceSession - Tracks a user's guidance workflow
- session_id (PK)
- user_id (FK)
- org_id (FK)
- query (the user's question)
- status: pending | active | completed | cancelled
- current_step: int
- total_steps: int
- created_at, updated_at

# GuidanceStep - Individual steps in a guidance session
- step_id (PK)
- session_id (FK)
- step_number: int
- instruction: str
- target_element_type: str
- target_element_label: str
- action_type: click | type | select | navigate | verify
- action_value: str (optional - for type actions)
- status: pending | active | completed | skipped
- completed_at: timestamp
- confidence: float

# GuidanceCapture - Screen captures during guidance
- capture_id (PK)
- session_id (FK)
- step_id (FK, nullable)
- screenshot_path: str
- screen_state: JSON (detected elements)
- captured_at: timestamp
```

---

### Task 6.2: LLM Client Abstraction

**File**: `backend/app/ai_engine/llm_client.py`

Support multiple LLM providers (GPT-4.1 as primary):

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import httpx

class LLMClient(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        pass

    @abstractmethod
    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Generate structured JSON response."""
        pass

class OpenAIClient(LLMClient):
    """OpenAI GPT-4.1 API client (primary)"""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4.1",
        max_tokens: int = 1024,
        temperature: float = 0.3
    ):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.base_url = "https://api.openai.com/v1"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                    "temperature": kwargs.get("temperature", self.temperature)
                },
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Generate with JSON mode enabled."""
        import json
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt or "You are a helpful assistant. Respond in JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                    "temperature": kwargs.get("temperature", self.temperature),
                    "response_format": {"type": "json_object"}  # GPT-4.1 JSON mode
                },
                timeout=60.0
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)

class OllamaClient(LLMClient):
    """Local Ollama client for offline/air-gapped use"""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3",
        max_tokens: int = 1024,
        temperature: float = 0.3
    ):
        self.base_url = base_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "num_predict": kwargs.get("max_tokens", self.max_tokens),
                        "temperature": kwargs.get("temperature", self.temperature)
                    }
                },
                timeout=120.0
            )
            response.raise_for_status()
            return response.json()["response"]

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        import json
        json_prompt = f"{prompt}\n\nRespond ONLY with valid JSON, no other text."
        response = await self.generate(json_prompt, system_prompt, **kwargs)
        # Extract JSON from response
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
        raise ValueError("Failed to parse JSON from response")

class LLMFactory:
    @staticmethod
    def create(settings) -> LLMClient:
        """Factory to create appropriate LLM client based on settings."""
        if settings.LLM_PROVIDER == "openai":
            return OpenAIClient(
                api_key=settings.OPENAI_API_KEY,
                model=settings.LLM_MODEL,
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE
            )
        elif settings.LLM_PROVIDER == "ollama":
            return OllamaClient(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_MODEL,
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE
            )
        else:
            raise ValueError(f"Unknown LLM provider: {settings.LLM_PROVIDER}")
```

**Configuration** (add to `config.py`):
```python
# AI Engine Configuration
LLM_PROVIDER: str = "openai"  # "openai" | "ollama"
OPENAI_API_KEY: str = ""  # Set via environment variable
LLM_MODEL: str = "gpt-4.1"  # or "gpt-4.1-mini" for faster/cheaper
LLM_MAX_TOKENS: int = 1024
LLM_TEMPERATURE: float = 0.3

# Fallback (Ollama - for offline use)
OLLAMA_BASE_URL: str = "http://localhost:11434"
OLLAMA_MODEL: str = "llama3"
```

---

### Task 6.3: Element Matcher

**File**: `backend/app/ai_engine/matcher.py`

Match detected UI elements to instruction targets:

```python
class ElementMatcher:
    """Matches instruction targets to detected screen elements."""

    def __init__(self, similarity_threshold: float = 0.6):
        self.threshold = similarity_threshold
        self.embedder = Embedder()  # Reuse RAG embedder

    def match_step_to_element(
        self,
        step: GuidanceStep,
        elements: List[UIElement]
    ) -> Optional[MatchResult]:
        """Find the UI element that matches the step's target."""

    def match_by_label(
        self,
        target_label: str,
        elements: List[UIElement]
    ) -> List[MatchResult]:
        """Find elements by label similarity."""
        # Use SequenceMatcher + embedding similarity

    def match_by_type_and_label(
        self,
        target_type: str,
        target_label: str,
        elements: List[UIElement]
    ) -> Optional[MatchResult]:
        """Combined matching by element type and label."""

    def find_nearby_elements(
        self,
        anchor_bbox: BoundingBox,
        elements: List[UIElement],
        radius_px: int = 100
    ) -> List[UIElement]:
        """Find elements near a reference point."""

@dataclass
class MatchResult:
    element: UIElement
    confidence: float
    match_type: str  # "exact" | "fuzzy" | "type_match"
    label_similarity: float
```

**Type Compatibility Mapping**:
```python
TYPE_COMPATIBILITY = {
    "button": ["link", "icon", "interactive_element"],
    "input": ["text_input", "textbox", "search_box"],
    "dropdown": ["select", "combobox", "menu"],
    "checkbox": ["toggle", "switch"],
    "tab": ["link", "button"],
}
```

---

### Task 6.4: AI Reasoner

**File**: `backend/app/ai_engine/reasoner.py`

LLM-powered reasoning for guidance generation:

```python
class AIReasoner:
    """Uses LLM to reason about screen state and generate guidance."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    async def analyze_context(
        self,
        query: str,
        screen_state: ScreenState,
        rag_results: List[ChunkResult],
        current_step: int = 1
    ) -> GuidanceContext:
        """Analyze screen and RAG results to determine guidance."""

    async def generate_next_step(
        self,
        context: GuidanceContext,
        previous_steps: List[GuidanceStep]
    ) -> GuidanceStep:
        """Generate the next step based on context."""

    async def validate_step_completion(
        self,
        step: GuidanceStep,
        before_state: ScreenState,
        after_state: ScreenState
    ) -> StepValidation:
        """Verify if a step was completed successfully."""

    async def extract_procedure_steps(
        self,
        rag_results: List[ChunkResult],
        query: str
    ) -> List[ProcedureStep]:
        """Extract ordered steps from RAG results."""

@dataclass
class GuidanceContext:
    query: str
    screen_elements: List[UIElement]
    text_regions: List[TextRegion]
    relevant_procedures: List[ProcedureStep]
    current_step_index: int
    detected_application: Optional[str]
```

**LLM Prompt Template**:
```
You are a UI guidance assistant. Analyze the screen and provide step-by-step guidance.

USER QUESTION: {query}

DETECTED UI ELEMENTS:
{formatted_elements}

RELEVANT PROCEDURES FROM KNOWLEDGE BASE:
{formatted_procedures}

CURRENT PROGRESS: Step {current_step} of estimated {total_steps}

Based on the visible UI elements and the procedure steps, determine:
1. What the user should do next
2. Which UI element to interact with
3. What action to take (click, type, select)
4. The expected outcome

Respond in JSON format:
{
  "instruction": "Clear instruction for the user",
  "target_element": {
    "type": "button|input|dropdown|etc",
    "label": "Text or description of element",
    "search_terms": ["alternative", "labels"]
  },
  "action": {
    "type": "click|type|select|navigate",
    "value": "Optional value for type actions"
  },
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of why this is the next step"
}
```

---

### Task 6.5: Guidance Generator

**File**: `backend/app/ai_engine/guidance_generator.py`

Orchestrates the guidance generation pipeline:

```python
class GuidanceGenerator:
    """Generates step-by-step guidance with halo targets."""

    def __init__(
        self,
        reasoner: AIReasoner,
        matcher: ElementMatcher,
        retriever: RAGRetriever
    ):
        self.reasoner = reasoner
        self.matcher = matcher
        self.retriever = retriever

    async def generate_guidance(
        self,
        session: GuidanceSession,
        screen_state: ScreenState,
        query: str
    ) -> GuidanceResponse:
        """Full guidance generation pipeline."""

        # 1. Query RAG for relevant procedures
        rag_results = await self.retriever.retrieve(
            query=query,
            org_id=session.org_id,
            top_k=10
        )

        # 2. Use LLM to reason about context
        context = await self.reasoner.analyze_context(
            query=query,
            screen_state=screen_state,
            rag_results=rag_results.results,
            current_step=session.current_step
        )

        # 3. Generate next step
        next_step = await self.reasoner.generate_next_step(
            context=context,
            previous_steps=session.steps
        )

        # 4. Match step target to screen elements
        match_result = self.matcher.match_step_to_element(
            step=next_step,
            elements=screen_state.elements
        )

        # 5. Create halo target
        halo_target = self._create_halo_target(
            step=next_step,
            match_result=match_result
        )

        return GuidanceResponse(
            session_id=session.session_id,
            current_step=next_step,
            halo_targets=[halo_target] if halo_target else [],
            total_steps=context.estimated_total_steps,
            confidence=next_step.confidence,
            sources=rag_results.results[:3]
        )

    def _create_halo_target(
        self,
        step: GuidanceStep,
        match_result: Optional[MatchResult]
    ) -> Optional[HaloTarget]:
        """Create halo target from step and matched element."""
        if not match_result:
            return None

        return HaloTarget(
            halo_id=str(uuid.uuid4()),
            element_id=match_result.element.element_id,
            label=step.instruction[:50],
            bbox=match_result.element.bbox,
            halo_style=self._get_halo_style(step.action_type),
            tooltip_text=step.instruction,
            confidence=match_result.confidence
        )

    def _get_halo_style(self, action_type: str) -> str:
        """Determine halo style based on action type."""
        return {
            "click": "glow",
            "type": "pulse",
            "select": "outline",
            "navigate": "glow",
            "verify": "outline"
        }.get(action_type, "glow")
```

---

### Task 6.6: Step Tracker

**File**: `backend/app/ai_engine/step_tracker.py`

Track progress through multi-step procedures:

```python
class StepTracker:
    """Tracks progress through guidance steps."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        user_id: str,
        org_id: str,
        query: str
    ) -> GuidanceSession:
        """Create a new guidance session."""

    async def advance_step(
        self,
        session_id: str,
        step_result: StepResult
    ) -> GuidanceSession:
        """Mark current step complete and advance."""

    async def skip_step(
        self,
        session_id: str,
        reason: str
    ) -> GuidanceSession:
        """Skip the current step."""

    async def complete_session(
        self,
        session_id: str
    ) -> GuidanceSession:
        """Mark session as completed."""

    async def get_session(
        self,
        session_id: str
    ) -> Optional[GuidanceSession]:
        """Retrieve session with steps."""

    async def get_active_sessions(
        self,
        user_id: str
    ) -> List[GuidanceSession]:
        """Get user's active guidance sessions."""

@dataclass
class StepResult:
    completed: bool
    screen_changed: bool
    matched_element_id: Optional[str]
    user_action: Optional[str]
    timestamp: datetime
```

---

### Task 6.7: Guidance API Endpoints

**File**: `backend/app/api/guidance.py`

REST API for guidance operations:

```python
router = APIRouter(prefix="/guidance", tags=["AI Guidance"])

# Session Management
@router.post("/sessions", response_model=SessionResponse)
async def create_guidance_session(request: CreateSessionRequest):
    """Start a new guidance session."""

@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str):
    """Get session details with steps."""

@router.post("/sessions/{session_id}/cancel")
async def cancel_session(session_id: str):
    """Cancel an active session."""

# Guidance Generation
@router.post("/generate", response_model=GuidanceResponse)
async def generate_guidance(request: GuidanceRequest):
    """
    Generate guidance for the current screen state.

    Request includes:
    - session_id: Active session
    - screen_state: Current ScreenState from CV analysis
    - query: User's original question (optional, uses session query)

    Returns:
    - Current step instruction
    - Halo targets for UI highlighting
    - Confidence score
    - Sources from knowledge base
    """

# Step Management
@router.post("/sessions/{session_id}/steps/{step_id}/complete")
async def complete_step(session_id: str, step_id: str, request: CompleteStepRequest):
    """Mark a step as completed."""

@router.post("/sessions/{session_id}/steps/{step_id}/skip")
async def skip_step(session_id: str, step_id: str, request: SkipStepRequest):
    """Skip the current step."""

# Screen Analysis Integration
@router.post("/analyze-and-guide", response_model=GuidanceResponse)
async def analyze_and_guide(request: AnalyzeAndGuideRequest):
    """
    Combined endpoint: Analyze screenshot and generate guidance in one call.

    Request includes:
    - session_id: Active session
    - image: Base64 screenshot
    - query: Optional query override

    This is a convenience endpoint that:
    1. Runs CV analysis on the screenshot
    2. Generates guidance based on screen state
    3. Returns guidance with halo targets
    """
```

---

### Task 6.8: Pydantic Schemas

**File**: `backend/app/schemas/guidance.py`

```python
# Request Schemas
class CreateSessionRequest(BaseModel):
    query: str
    org_id: str
    kb_id: Optional[str] = None

class GuidanceRequest(BaseModel):
    session_id: str
    screen_state: ScreenStateSchema
    query: Optional[str] = None

class AnalyzeAndGuideRequest(BaseModel):
    session_id: str
    image: str  # Base64 encoded
    resize: bool = True
    query: Optional[str] = None

class CompleteStepRequest(BaseModel):
    screen_state: Optional[ScreenStateSchema] = None
    user_feedback: Optional[str] = None

class SkipStepRequest(BaseModel):
    reason: Optional[str] = None

# Response Schemas
class HaloTarget(BaseModel):
    halo_id: str
    element_id: str
    label: str
    bbox: BoundingBoxSchema
    halo_style: Literal["glow", "pulse", "outline"]
    tooltip_text: str
    confidence: float

class GuidanceStep(BaseModel):
    step_id: str
    step_number: int
    instruction: str
    target_element_type: Optional[str]
    target_element_label: Optional[str]
    action_type: Literal["click", "type", "select", "navigate", "verify"]
    action_value: Optional[str]
    status: Literal["pending", "active", "completed", "skipped"]
    confidence: float

class GuidanceResponse(BaseModel):
    session_id: str
    current_step: GuidanceStep
    halo_targets: List[HaloTarget]
    progress: GuidanceProgress
    confidence: float
    sources: List[ChunkResult]
    message: Optional[str] = None

class GuidanceProgress(BaseModel):
    current_step: int
    total_steps: int
    completed_steps: int
    percentage: float

class SessionResponse(BaseModel):
    session_id: str
    status: str
    query: str
    created_at: datetime
    current_step: int
    total_steps: int

class SessionDetailResponse(SessionResponse):
    steps: List[GuidanceStep]
    captures: List[CaptureInfo]
```

---

### Task 6.9: Frontend Integration

**File**: `frontend/src/stores/guidanceStore.ts`

```typescript
interface GuidanceState {
  session: GuidanceSession | null;
  currentStep: GuidanceStep | null;
  haloTargets: HaloTarget[];
  isLoading: boolean;
  error: string | null;

  // Actions
  startSession: (query: string, kbId?: string) => Promise<void>;
  generateGuidance: (screenState: ScreenState) => Promise<void>;
  completeStep: (stepId: string) => Promise<void>;
  skipStep: (stepId: string, reason?: string) => Promise<void>;
  cancelSession: () => Promise<void>;
  clearError: () => void;
}
```

**File**: `frontend/src/hooks/useGuidance.ts`

```typescript
export function useGuidance() {
  const store = useGuidanceStore();
  const { screenState } = useDetection();

  // Auto-generate guidance when screen state changes
  useEffect(() => {
    if (store.session && screenState && store.session.status === 'active') {
      store.generateGuidance(screenState);
    }
  }, [screenState, store.session?.session_id]);

  return {
    ...store,
    isActive: store.session?.status === 'active',
    progress: calculateProgress(store.session),
  };
}
```

**File**: `frontend/src/api/guidance.ts` (updated)

```typescript
// Session Management
export const createGuidanceSession = (request: CreateSessionRequest) =>
  apiClient.post<SessionResponse>('/guidance/sessions', request);

export const getSession = (sessionId: string) =>
  apiClient.get<SessionDetailResponse>(`/guidance/sessions/${sessionId}`);

export const cancelSession = (sessionId: string) =>
  apiClient.post(`/guidance/sessions/${sessionId}/cancel`);

// Guidance Generation
export const generateGuidance = (request: GuidanceRequest) =>
  apiClient.post<GuidanceResponse>('/guidance/generate', request);

export const analyzeAndGuide = (request: AnalyzeAndGuideRequest) =>
  apiClient.post<GuidanceResponse>('/guidance/analyze-and-guide', request);

// Step Management
export const completeStep = (sessionId: string, stepId: string, request?: CompleteStepRequest) =>
  apiClient.post(`/guidance/sessions/${sessionId}/steps/${stepId}/complete`, request);

export const skipStep = (sessionId: string, stepId: string, reason?: string) =>
  apiClient.post(`/guidance/sessions/${sessionId}/steps/${stepId}/skip`, { reason });
```

---

## Implementation Order

1. **Database Models** (Task 6.1)
   - Create guidance session and step models
   - Run migrations

2. **LLM Client** (Task 6.2)
   - Implement Claude API client
   - Add Ollama fallback
   - Configure environment variables

3. **Element Matcher** (Task 6.3)
   - Label similarity matching
   - Type compatibility
   - Position-based fallbacks

4. **AI Reasoner** (Task 6.4)
   - Prompt engineering
   - JSON parsing
   - Error handling

5. **Guidance Generator** (Task 6.5)
   - Pipeline orchestration
   - Halo target creation

6. **Step Tracker** (Task 6.6)
   - Session management
   - Progress tracking

7. **API Endpoints** (Task 6.7)
   - REST API implementation
   - Request validation

8. **Schemas** (Task 6.8)
   - Pydantic models
   - API documentation

9. **Frontend Integration** (Task 6.9)
   - Zustand store
   - React hooks
   - API client updates

---

## Configuration Requirements

Add to `.env`:
```env
# AI Engine (OpenAI GPT-4.1)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4.1
LLM_MAX_TOKENS=1024
LLM_TEMPERATURE=0.3

# Fallback (Ollama - for offline use)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Matching
ELEMENT_MATCH_THRESHOLD=0.6
EMBEDDING_SIMILARITY_WEIGHT=0.5
```

Add to `backend/requirements.txt`:
```
openai>=1.0.0  # OpenAI GPT-4.1 client
```

---

## Testing Strategy

1. **Unit Tests**
   - ElementMatcher similarity calculations
   - LLM response parsing
   - Step tracking state transitions

2. **Integration Tests**
   - Full guidance pipeline
   - API endpoint validation
   - Database operations

3. **Mock Data**
   - Sample screen states with elements
   - Test procedures for RAG
   - Expected guidance outputs

---

## Success Criteria

- [ ] User can ask a question and receive step-by-step guidance
- [ ] Detected UI elements are matched to instruction targets
- [ ] Halo targets are generated for matched elements
- [ ] Progress is tracked across multiple steps
- [ ] RAG results are used to inform guidance
- [ ] LLM generates contextually appropriate instructions
- [ ] API responds within 2 seconds for guidance generation
- [ ] Frontend displays guidance with halo targets
