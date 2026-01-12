# Phase 7: Halo Overlay System with Automatic Detection

## Overview

This phase integrates the Halo Overlay System with automatic window detection and screen capture. The goal is to provide a seamless experience where:

1. User asks a question and receives step-by-step guidance
2. System **automatically** detects when user switches to the target application
3. Screen capture and CV analysis happen **automatically** per-step
4. Halo overlay highlights the target UI element on the actual application window

## Current State (What's Already Implemented)

| Component | Location | Status |
|-----------|----------|--------|
| Window Monitor (Rust) | `frontend/src-tauri/src/detection/window_monitor.rs` | Complete |
| Screenshot Capture (Rust) | `frontend/src-tauri/src/detection/screenshot.rs` | Complete |
| Tauri Commands | `frontend/src-tauri/src/commands/detection_commands.rs` | Complete |
| Target App Settings (Backend) | `backend/app/api/organisations.py` | Complete |
| CV Pipeline | `backend/app/services/cv_service.py` | Complete |
| AI Guidance Engine | `backend/app/ai_engine/` | Complete |
| Guidance API | `backend/app/api/guidance.py` | Complete |
| Guidance Store (Frontend) | `frontend/src/stores/guidanceStore.ts` | Complete |
| Guidance Hook (Frontend) | `frontend/src/hooks/useGuidance.ts` | Complete |
| GuidanceSessionPanel | `frontend/src/components/guidance/GuidanceSessionPanel.tsx` | Complete (manual buttons) |

## What Needs to Be Built

### 1. Automatic Detection Flow (Frontend)
- Auto-start window monitoring when guidance session begins
- Auto-trigger screen capture when target window is detected
- Periodic re-capture while guidance is active
- Event-driven updates to the UI

### 2. Halo Overlay Window (Tauri)
- Transparent, click-through overlay window
- Positioned over the target application
- Renders halo highlights at element coordinates
- Auto-updates when target changes

### 3. Halo Rendering Components (Frontend)
- HaloOverlay component for the overlay window
- HaloElement with glow/pulse animations
- Tooltip showing current instruction
- Arrow/pointer to guide user's eye

### 4. Coordination Service (Frontend)
- GuidanceCoordinator hook/service
- Manages the full lifecycle: monitoring -> capture -> analysis -> display
- Handles errors and edge cases gracefully

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AUTOMATIC DETECTION FLOW                          │
└─────────────────────────────────────────────────────────────────────────────┘

 User asks question
        │
        ▼
┌───────────────────┐
│ Generate Guidance │  Backend: /guidance/generate
│   (LLM + RAG)     │  Returns: steps[], session_id
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Start Monitoring │  Tauri: start_window_monitoring()
│  (Window Pattern) │  Pattern from org's target_window_pattern
└───────────────────┘
        │
        ▼ (polling every 500ms)
┌───────────────────┐
│ Window Detected?  │──No──► Continue polling
│ (Pattern Match)   │
└───────────────────┘
        │ Yes
        ▼
┌───────────────────┐
│ Capture Window    │  Tauri: capture_window_by_pattern()
│ (Screenshot)      │  Returns: base64 image
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  CV Analysis      │  Backend: via /guidance/sessions/{id}/capture
│  (UI + OCR)       │  Returns: elements[], text_regions[]
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ Element Matching  │  Backend: ElementMatcher
│ (Step → Element)  │  Returns: target bbox, confidence
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ Update Halo       │  Tauri: update_halo_position()
│ Overlay           │  Positions overlay at target element
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ User Completes    │  User clicks "Next" or auto-advances
│ Step              │
└───────────────────┘
        │
        ▼
   Next Step / Complete
```

---

## Implementation Plan

### Step 1: Halo Overlay Window (Tauri/Rust)

**Files to create/modify:**

```
frontend/src-tauri/
├── src/
│   ├── lib.rs                    # Add overlay window + halo commands
│   ├── overlay/
│   │   ├── mod.rs                # Overlay module
│   │   ├── window.rs             # Overlay window management
│   │   └── halo.rs               # Halo rendering logic
│   └── commands/
│       └── halo_commands.rs      # Halo-related Tauri commands
```

**Key Rust structs:**

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HaloTarget {
    pub target_id: String,
    pub bbox: BoundingBox,
    pub element_type: String,
    pub label: Option<String>,
    pub step_number: i32,
    pub action_type: String,
    pub instruction: String,
    pub halo_style: HaloStyle,  // glow, pulse, outline
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoundingBox {
    pub x1: i32,
    pub y1: i32,
    pub x2: i32,
    pub y2: i32,
}

pub enum HaloStyle {
    Glow,
    Pulse,
    Outline,
}
```

**Tauri commands to add:**

```rust
#[tauri::command]
async fn create_overlay_window(app: AppHandle) -> Result<(), String>;

#[tauri::command]
async fn show_halo(app: AppHandle, target: HaloTarget) -> Result<(), String>;

#[tauri::command]
async fn hide_halo(app: AppHandle) -> Result<(), String>;

#[tauri::command]
async fn update_halo_position(app: AppHandle, target: HaloTarget) -> Result<(), String>;

#[tauri::command]
async fn destroy_overlay_window(app: AppHandle) -> Result<(), String>;
```

---

### Step 2: Overlay Window HTML/React Component

**Files to create:**

```
frontend/
├── overlay.html                  # Entry point for overlay window
├── src/
│   ├── overlay/
│   │   ├── main.tsx              # Overlay React entry
│   │   ├── OverlayApp.tsx        # Main overlay component
│   │   ├── HaloElement.tsx       # Single halo rendering
│   │   ├── InstructionTooltip.tsx # Floating instruction
│   │   └── styles.css            # Halo animations
```

**HaloElement.tsx:**

```tsx
interface HaloElementProps {
  target: HaloTarget;
}

export function HaloElement({ target }: HaloElementProps) {
  const { bbox, halo_style, instruction, label } = target;

  return (
    <div
      className={`halo-element halo-${halo_style}`}
      style={{
        position: 'absolute',
        left: bbox.x1,
        top: bbox.y1,
        width: bbox.x2 - bbox.x1,
        height: bbox.y2 - bbox.y1,
      }}
    >
      <div className="halo-border" />
      <InstructionTooltip text={instruction} />
    </div>
  );
}
```

**Halo CSS animations:**

```css
.halo-glow .halo-border {
  border: 3px solid #4F46E5;
  box-shadow: 0 0 15px #4F46E5, 0 0 30px #4F46E5;
  animation: glow-pulse 1.5s ease-in-out infinite;
}

@keyframes glow-pulse {
  0%, 100% { box-shadow: 0 0 15px #4F46E5, 0 0 30px #4F46E5; }
  50% { box-shadow: 0 0 25px #4F46E5, 0 0 50px #4F46E5; }
}
```

---

### Step 3: Guidance Coordinator (Frontend Service)

**File:** `frontend/src/services/GuidanceCoordinator.ts`

This service orchestrates the entire automatic detection flow:

```typescript
class GuidanceCoordinator {
  private monitoringActive = false;
  private captureInterval: number | null = null;

  // Called when guidance session starts
  async startGuidance(sessionId: string, targetPattern: string) {
    // 1. Start window monitoring via Tauri
    await invoke('start_window_monitoring', {
      patterns: [{ pattern: targetPattern, mode: 'contains' }],
      pollIntervalMs: 500
    });

    // 2. Create overlay window
    await invoke('create_overlay_window');

    // 3. Listen for window match events
    await listen('window-matched', this.onWindowMatched);

    // 4. Start periodic capture (every 2 seconds while active)
    this.startPeriodicCapture(sessionId);

    this.monitoringActive = true;
  }

  private async onWindowMatched(event: WindowMatchEvent) {
    // Window is now in focus - trigger immediate capture
    await this.captureAndAnalyze();
  }

  private async captureAndAnalyze() {
    // 1. Capture screenshot via Tauri
    const screenshot = await invoke('capture_screenshot');

    // 2. Send to backend for CV analysis
    const response = await captureStep(this.sessionId);

    // 3. Update halo overlay with new target
    if (response.target) {
      await invoke('update_halo_position', { target: response.target });
    }
  }

  private startPeriodicCapture(sessionId: string) {
    this.captureInterval = setInterval(async () => {
      if (this.monitoringActive) {
        await this.captureAndAnalyze();
      }
    }, 2000); // Re-capture every 2 seconds
  }

  async stopGuidance() {
    await invoke('stop_window_monitoring');
    await invoke('destroy_overlay_window');
    if (this.captureInterval) clearInterval(this.captureInterval);
    this.monitoringActive = false;
  }
}
```

---

### Step 4: Hook Integration

**File:** `frontend/src/hooks/useGuidanceCoordinator.ts`

```typescript
export function useGuidanceCoordinator() {
  const coordinator = useRef(new GuidanceCoordinator());
  const { sessionId, status, currentStep } = useGuidanceStore();
  const { targetWindowPattern } = useOrgSettings();

  // Auto-start when session becomes active
  useEffect(() => {
    if (status === 'active' && sessionId && targetWindowPattern) {
      coordinator.current.startGuidance(sessionId, targetWindowPattern);
    }

    return () => {
      coordinator.current.stopGuidance();
    };
  }, [status, sessionId, targetWindowPattern]);

  // Re-capture when step changes
  useEffect(() => {
    if (status === 'active' && currentStep > 0) {
      coordinator.current.captureAndAnalyze();
    }
  }, [currentStep, status]);

  return {
    isMonitoring: coordinator.current.isActive(),
    forceCapture: () => coordinator.current.captureAndAnalyze(),
  };
}
```

---

### Step 5: Update GuidanceSessionPanel

**Modify:** `frontend/src/components/guidance/GuidanceSessionPanel.tsx`

Remove the manual "Start Visual Guidance" button and replace with automatic status display:

```tsx
// Before (manual):
<Button onClick={startVisualGuidance}>Start Visual Guidance</Button>

// After (automatic):
<div className="visual-guidance-status">
  {isMonitoring ? (
    <span className="status-active">
      <span className="pulse-dot" />
      Watching for {targetAppName}...
    </span>
  ) : (
    <span className="status-waiting">
      Configure target app in Settings
    </span>
  )}
</div>
```

---

### Step 6: Backend Enhancements

**Modify:** `backend/app/api/guidance.py`

Add endpoint to get org's target app settings along with session:

```python
@router.get("/sessions/{session_id}/target-config")
async def get_session_target_config(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(get_current_org_membership),
):
    """Get target app configuration for a guidance session."""
    org = await db.get(Organisation, membership.org_id)

    return {
        "target_app_name": org.target_app_name,
        "target_window_pattern": org.target_window_pattern,
        "target_process_name": org.target_process_name,
        "is_configured": org.has_target_app_configured,
    }
```

---

## File Changes Summary

### New Files

| File | Description |
|------|-------------|
| `frontend/src-tauri/src/overlay/mod.rs` | Overlay module declaration |
| `frontend/src-tauri/src/overlay/window.rs` | Overlay window creation/management |
| `frontend/src-tauri/src/overlay/halo.rs` | Halo state and rendering logic |
| `frontend/src-tauri/src/commands/halo_commands.rs` | Halo Tauri commands |
| `frontend/overlay.html` | Overlay window entry point |
| `frontend/src/overlay/main.tsx` | Overlay React entry |
| `frontend/src/overlay/OverlayApp.tsx` | Main overlay component |
| `frontend/src/overlay/HaloElement.tsx` | Halo rendering component |
| `frontend/src/overlay/InstructionTooltip.tsx` | Floating instruction tooltip |
| `frontend/src/overlay/styles.css` | Halo animations |
| `frontend/src/services/GuidanceCoordinator.ts` | Orchestration service |
| `frontend/src/hooks/useGuidanceCoordinator.ts` | React hook for coordinator |

### Modified Files

| File | Changes |
|------|---------|
| `frontend/src-tauri/src/lib.rs` | Add overlay window setup, register halo commands |
| `frontend/src-tauri/tauri.conf.json` | Add overlay window config |
| `frontend/src/components/guidance/GuidanceSessionPanel.tsx` | Replace manual buttons with auto status |
| `frontend/src/pages/dashboard/GuidancePage.tsx` | Integrate useGuidanceCoordinator |
| `frontend/vite.config.ts` | Add overlay entry point |
| `backend/app/api/guidance.py` | Add target-config endpoint |

---

## Implementation Order

### Phase 7.1: Overlay Window Infrastructure (Tauri)
1. Create overlay window module in Rust
2. Implement transparent, click-through window
3. Add Tauri commands for show/hide/update halo
4. Test overlay window creation

### Phase 7.2: Overlay React Components
1. Create overlay.html entry point
2. Build OverlayApp, HaloElement, InstructionTooltip
3. Add CSS animations for glow/pulse effects
4. Configure Vite for multi-page build

### Phase 7.3: Guidance Coordinator Service
1. Create GuidanceCoordinator class
2. Implement window monitoring integration
3. Add periodic capture logic
4. Handle edge cases (window not found, errors)

### Phase 7.4: Frontend Integration
1. Create useGuidanceCoordinator hook
2. Update GuidanceSessionPanel for auto mode
3. Update GuidancePage to use coordinator
4. Add visual feedback for monitoring status

### Phase 7.5: Backend Enhancements
1. Add target-config endpoint
2. Optimize capture endpoint for frequent calls
3. Add caching for repeated element matching

### Phase 7.6: Testing & Polish
1. Test end-to-end flow
2. Optimize capture frequency
3. Handle multi-monitor setups
4. Add error recovery

---

## Configuration

### Tauri Window Config

Add to `frontend/src-tauri/tauri.conf.json`:

```json
{
  "tauri": {
    "windows": [
      {
        "label": "main",
        "title": "Pedagogy",
        "width": 400,
        "height": 700
      },
      {
        "label": "overlay",
        "title": "",
        "url": "overlay.html",
        "transparent": true,
        "decorations": false,
        "alwaysOnTop": true,
        "skipTaskbar": true,
        "fullscreen": true,
        "visible": false,
        "resizable": false
      }
    ]
  }
}
```

### Vite Multi-Page Config

```typescript
// vite.config.ts
export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        overlay: resolve(__dirname, 'overlay.html'),
      },
    },
  },
});
```

---

## Success Criteria

1. **Automatic Detection**: User does NOT need to click "Start Visual Guidance"
2. **Seamless Experience**: Overlay appears when user switches to target app
3. **Accurate Highlighting**: Halo correctly highlights the target element
4. **Real-time Updates**: Halo updates as screen changes
5. **Performance**: Capture + analysis < 1 second
6. **Reliability**: Graceful handling of edge cases

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Performance: Frequent captures slow down system | Adaptive polling: increase interval when screen is stable |
| CV accuracy: Wrong element highlighted | Show confidence score, allow manual correction |
| Multi-monitor: Overlay on wrong screen | Detect target window's monitor, position overlay accordingly |
| User switches apps: Overlay persists | Listen for window-blur events, hide overlay when target loses focus |
| Backend slow: LLM analysis takes too long | Separate capture (fast) from analysis (async), show "analyzing..." state |

---

## Timeline Estimate

| Phase | Effort |
|-------|--------|
| 7.1 Overlay Window Infrastructure | Medium |
| 7.2 Overlay React Components | Low |
| 7.3 Guidance Coordinator Service | Medium |
| 7.4 Frontend Integration | Low |
| 7.5 Backend Enhancements | Low |
| 7.6 Testing & Polish | Medium |

---

## Next Steps

1. Review and approve this plan
2. Start with Phase 7.1 (Overlay Window Infrastructure)
3. Iterate through remaining phases
4. Continuous testing throughout
