// Re-export all types from a single entry point
export * from './auth';
export * from './organisation';
export * from './api';
export * from './knowledge';
export * from './guidance';
// Detection types - excluding duplicates that are defined in guidance.ts
export {
  type CaptureResult,
  type CaptureResponse,
  type MonitorInfo,
  type MatchMode,
  type WindowPattern,
  type WindowMatchEvent,
  type StartMonitoringRequest,
  type UIElement,
  type TextRegion,
  type ImageSize,
  type ScreenState,
  type DetectionStatus,
  type DetectionSession,
  type AnalyzeScreenRequest,
  type AnalyzeScreenResponse,
  type DetectUIRequest,
  type DetectUIResponse,
  type ExtractTextRequest,
  type ExtractTextResponse,
  type CVHealthResponse,
} from './detection';
