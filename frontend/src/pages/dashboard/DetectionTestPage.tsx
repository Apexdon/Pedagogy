/**
 * Detection Test Page
 *
 * A simple page to test Phase 5 detection features:
 * - Screen capture
 * - Window monitoring with auto-capture
 * - CV analysis
 */

import { useState } from 'react';
import { Card, CardBody, CardHeader, Button, Input } from '@/components/ui';
import { useDetection } from '@/hooks/useDetection';
import * as detectionApi from '@/api/detection';
import type { WindowInfo, MonitorInfo, WindowPattern } from '@/types/detection';

export function DetectionTestPage() {
  const [patternInput, setPatternInput] = useState('');
  const [patterns, setPatterns] = useState<WindowPattern[]>([]);

  const {
    status,
    capture,
    screenState,
    error,
    isCapturing,
    isAnalyzing,
    isMonitoring,
    autoCapture,
    lastMatchedWindow,
    captureIntervalMs,
    startCapture,
    resetSession,
    startMonitoring,
    stopMonitoring,
    setAutoCapture,
    setWindowPatterns,
    setCaptureInterval,
  } = useDetection();

  const [activeWindow, setActiveWindow] = useState<WindowInfo | null>(null);
  const [monitors, setMonitors] = useState<MonitorInfo[]>([]);
  const [cvHealth, setCvHealth] = useState<{ status: string } | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  // Test: Get active window title
  const handleGetActiveWindow = async () => {
    setTestError(null);
    try {
      const info = await detectionApi.getActiveWindowTitle();
      setActiveWindow(info);
    } catch (err) {
      setTestError(`Failed to get active window: ${err}`);
    }
  };

  // Test: Get monitors
  const handleGetMonitors = async () => {
    setTestError(null);
    try {
      const monitorList = await detectionApi.getMonitors();
      setMonitors(monitorList);
    } catch (err) {
      setTestError(`Failed to get monitors: ${err}`);
    }
  };

  // Test: Check CV health
  const handleCheckCVHealth = async () => {
    setTestError(null);
    try {
      const health = await detectionApi.getCVHealth();
      setCvHealth(health);
    } catch (err) {
      setTestError(`CV health check failed: ${err}`);
    }
  };

  // Test: Capture and analyze
  const handleCaptureAndAnalyze = async () => {
    setTestError(null);
    try {
      await startCapture();
    } catch (err) {
      setTestError(`Capture failed: ${err}`);
    }
  };

  // Add a window pattern
  const handleAddPattern = () => {
    if (!patternInput.trim()) return;
    const newPatterns = [...patterns, { pattern: patternInput.trim(), mode: 'contains' as const }];
    setPatterns(newPatterns);
    setWindowPatterns(newPatterns);
    setPatternInput('');
  };

  // Remove a pattern
  const handleRemovePattern = (index: number) => {
    const newPatterns = patterns.filter((_, i) => i !== index);
    setPatterns(newPatterns);
    setWindowPatterns(newPatterns);
  };

  // Toggle monitoring
  const handleToggleMonitoring = async () => {
    if (isMonitoring) {
      await stopMonitoring();
    } else {
      await startMonitoring();
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Detection Test</h1>
        <p className="text-gray-600 mt-1">
          Test Phase 5 detection features - screen capture, window monitoring, and CV analysis.
        </p>
      </div>

      {/* Error Display */}
      {(error || testError) && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error || testError}
        </div>
      )}

      {/* Window Monitoring Configuration */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold">Window Monitoring (Auto-Detection)</h2>
        </CardHeader>
        <CardBody>
          <div className="space-y-4">
            {/* Pattern Input */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Add Window Pattern (matches window title)
              </label>
              <div className="flex gap-2">
                <Input
                  value={patternInput}
                  onChange={(e) => setPatternInput(e.target.value)}
                  placeholder="e.g., Excel, Chrome, Visual Studio"
                  className="flex-1"
                  onKeyDown={(e) => e.key === 'Enter' && handleAddPattern()}
                />
                <Button onClick={handleAddPattern} variant="secondary">
                  Add
                </Button>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                When a window containing this text is active, auto-capture will trigger
              </p>
            </div>

            {/* Pattern List */}
            {patterns.length > 0 && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Active Patterns ({patterns.length})
                </label>
                <div className="flex flex-wrap gap-2">
                  {patterns.map((p, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
                    >
                      {p.pattern}
                      <button
                        onClick={() => handleRemovePattern(i)}
                        className="hover:text-blue-600"
                      >
                        x
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Controls */}
            <div className="flex flex-wrap items-center gap-4 pt-2 border-t">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={autoCapture}
                  onChange={(e) => setAutoCapture(e.target.checked)}
                  className="rounded border-gray-300"
                />
                <span className="text-sm">Auto-capture when window matches</span>
              </label>

              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-600">Interval:</span>
                <select
                  value={captureIntervalMs}
                  onChange={(e) => setCaptureInterval(Number(e.target.value))}
                  className="text-sm border rounded px-2 py-1"
                >
                  <option value={3000}>3 seconds</option>
                  <option value={5000}>5 seconds</option>
                  <option value={10000}>10 seconds</option>
                  <option value={30000}>30 seconds</option>
                </select>
              </div>

              <Button
                onClick={handleToggleMonitoring}
                disabled={patterns.length === 0}
                variant={isMonitoring ? 'secondary' : 'primary'}
              >
                {isMonitoring ? 'Stop Monitoring' : 'Start Monitoring'}
              </Button>
            </div>

            {/* Monitoring Status */}
            <div className="flex items-center gap-4 text-sm">
              <span className={`flex items-center gap-1 ${isMonitoring ? 'text-green-600' : 'text-gray-500'}`}>
                <span className={`w-2 h-2 rounded-full ${isMonitoring ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
                {isMonitoring ? 'Monitoring active' : 'Not monitoring'}
              </span>
              {lastMatchedWindow && (
                <span className="text-blue-600">
                  Last match: "{lastMatchedWindow.window_info.title}"
                </span>
              )}
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Manual Test Controls */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold">Manual Test Controls</h2>
        </CardHeader>
        <CardBody>
          <div className="flex flex-wrap gap-3">
            <Button onClick={handleGetActiveWindow} variant="secondary">
              Get Active Window
            </Button>
            <Button onClick={handleGetMonitors} variant="secondary">
              Get Monitors
            </Button>
            <Button onClick={handleCheckCVHealth} variant="secondary">
              Check CV Health
            </Button>
            <Button
              onClick={handleCaptureAndAnalyze}
              disabled={isCapturing || isAnalyzing}
            >
              {isCapturing ? 'Capturing...' : isAnalyzing ? 'Analyzing...' : 'Capture & Analyze'}
            </Button>
            <Button onClick={resetSession} variant="ghost">
              Reset
            </Button>
          </div>
        </CardBody>
      </Card>

      {/* Status */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold">Detection Status</h2>
        </CardHeader>
        <CardBody>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="font-medium">Status:</span>
              <span className={`px-2 py-1 rounded text-sm ${
                status === 'idle' ? 'bg-gray-100 text-gray-700' :
                status === 'capturing' ? 'bg-blue-100 text-blue-700' :
                status === 'analyzing' ? 'bg-yellow-100 text-yellow-700' :
                status === 'ready' ? 'bg-green-100 text-green-700' :
                'bg-red-100 text-red-700'
              }`}>
                {status}
              </span>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Active Window Info */}
      {activeWindow && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Active Window</h2>
          </CardHeader>
          <CardBody>
            <pre className="bg-gray-50 p-3 rounded text-sm overflow-auto">
              {JSON.stringify(activeWindow, null, 2)}
            </pre>
          </CardBody>
        </Card>
      )}

      {/* Monitors Info */}
      {monitors.length > 0 && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Monitors ({monitors.length})</h2>
          </CardHeader>
          <CardBody>
            <pre className="bg-gray-50 p-3 rounded text-sm overflow-auto">
              {JSON.stringify(monitors, null, 2)}
            </pre>
          </CardBody>
        </Card>
      )}

      {/* CV Health */}
      {cvHealth && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">CV Pipeline Health</h2>
          </CardHeader>
          <CardBody>
            <pre className="bg-gray-50 p-3 rounded text-sm overflow-auto">
              {JSON.stringify(cvHealth, null, 2)}
            </pre>
          </CardBody>
        </Card>
      )}

      {/* Screenshot Preview */}
      {capture && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Screenshot Preview</h2>
          </CardHeader>
          <CardBody>
            <div className="space-y-3">
              <div className="text-sm text-gray-600">
                Size: {capture.width} x {capture.height} | Monitor: {capture.monitor_name}
              </div>
              <div className="border rounded-lg overflow-hidden">
                <img
                  src={`data:image/png;base64,${capture.image_base64}`}
                  alt="Screenshot"
                  className="max-w-full h-auto"
                  style={{ maxHeight: '400px', objectFit: 'contain' }}
                />
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Analysis Results */}
      {screenState && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">CV Analysis Results</h2>
          </CardHeader>
          <CardBody>
            <div className="space-y-4">
              {/* UI Elements */}
              <div>
                <h3 className="font-medium mb-2">
                  Detected UI Elements ({screenState.elements?.length || 0})
                </h3>
                <pre className="bg-gray-50 p-3 rounded text-sm overflow-auto max-h-64">
                  {JSON.stringify(screenState.elements, null, 2)}
                </pre>
              </div>

              {/* Text Regions */}
              {screenState.text_regions && screenState.text_regions.length > 0 && (
                <div>
                  <h3 className="font-medium mb-2">Extracted Text Regions ({screenState.text_regions.length})</h3>
                  <pre className="bg-gray-50 p-3 rounded text-sm overflow-auto max-h-64 whitespace-pre-wrap">
                    {screenState.text_regions.map(r => r.text).join('\n')}
                  </pre>
                </div>
              )}
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
