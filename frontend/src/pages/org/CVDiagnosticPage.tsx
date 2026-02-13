/**
 * CVDiagnosticPage
 *
 * Diagnostic tool for testing and understanding CV pipeline performance.
 * Upload an image and see detailed timing breakdown for OCR and UI detection.
 */

import { useState, useRef } from 'react';
import { Card, CardBody, CardHeader, Button, Loading } from '@/components/ui';
import { runDiagnostic } from '@/api/detection';
import type { DiagnosticResponse, TimingStep } from '@/types/detection';

export function CVDiagnosticPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DiagnosticResponse | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [runOCR, setRunOCR] = useState(true);
  const [runDetection, setRunDetection] = useState(true);
  const [resize, setResize] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      setError('Please select a valid image file');
      return;
    }

    // Convert to base64
    const reader = new FileReader();
    reader.onload = (e) => {
      const base64 = e.target?.result as string;
      setImagePreview(base64);
      setError(null);
      setResult(null);
    };
    reader.readAsDataURL(file);
  };

  const handleRunDiagnostic = async () => {
    if (!imagePreview) {
      setError('Please select an image first');
      return;
    }

    if (!runOCR && !runDetection) {
      setError('Please select at least one analysis type (OCR or Detection)');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await runDiagnostic({
        image: imagePreview,
        resize,
        run_ocr: runOCR,
        run_detection: runDetection,
      });
      setResult(response);
    } catch (err) {
      console.error('Diagnostic failed:', err);
      setError(err instanceof Error ? err.message : 'Diagnostic analysis failed');
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = () => {
    setImagePreview(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const formatTime = (ms: number) => {
    if (ms >= 1000) {
      return `${(ms / 1000).toFixed(2)}s`;
    }
    return `${ms.toFixed(0)}ms`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">CV Pipeline Diagnostic</h1>
        <p className="text-gray-600 mt-1">
          Upload an image to analyze CV pipeline performance with detailed timing breakdown
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Input */}
        <div className="space-y-4">
          {/* Image Upload Card */}
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold text-gray-900">Input Image</h2>
            </CardHeader>
            <CardBody>
              {/* File Input */}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileSelect}
                className="hidden"
              />

              {imagePreview ? (
                <div className="space-y-4">
                  {/* Preview */}
                  <div className="relative border rounded-lg overflow-hidden bg-gray-100">
                    <img
                      src={imagePreview}
                      alt="Preview"
                      className="w-full h-auto max-h-[400px] object-contain"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      Change Image
                    </Button>
                    <Button variant="ghost" onClick={handleClear}>
                      Clear
                    </Button>
                  </div>
                </div>
              ) : (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-primary-400 hover:bg-gray-50 transition-colors"
                >
                  <svg
                    className="mx-auto h-12 w-12 text-gray-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                    />
                  </svg>
                  <p className="mt-2 text-gray-600">Click to upload an image</p>
                  <p className="text-sm text-gray-400">PNG, JPG, BMP supported</p>
                </div>
              )}
            </CardBody>
          </Card>

          {/* Options Card */}
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold text-gray-900">Analysis Options</h2>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                {/* Checkboxes */}
                <div className="space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={runOCR}
                      onChange={(e) => setRunOCR(e.target.checked)}
                      className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-gray-700">Run OCR (Text Extraction)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={runDetection}
                      onChange={(e) => setRunDetection(e.target.checked)}
                      className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-gray-700">Run UI Detection (YOLO/OmniParser)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={resize}
                      onChange={(e) => setResize(e.target.checked)}
                      className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-gray-700">Resize large images</span>
                  </label>
                </div>

                {/* Run Button */}
                <Button
                  onClick={handleRunDiagnostic}
                  disabled={!imagePreview || isLoading}
                  className="w-full"
                >
                  {isLoading ? (
                    <>
                      <Loading size="sm" className="mr-2" />
                      Analyzing...
                    </>
                  ) : (
                    'Run Diagnostic'
                  )}
                </Button>
              </div>
            </CardBody>
          </Card>

          {/* Error Display */}
          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}
        </div>

        {/* Right Column: Results */}
        <div className="space-y-4">
          {result ? (
            <>
              {/* Summary Card */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-gray-900">Analysis Summary</h2>
                    <span className="text-2xl font-bold text-primary-600">
                      {formatTime(result.total_time_ms)}
                    </span>
                  </div>
                </CardHeader>
                <CardBody>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500">Image Size</span>
                      <p className="font-medium">
                        {result.image_size.width} x {result.image_size.height}
                      </p>
                    </div>
                    <div>
                      <span className="text-gray-500">Preprocessing</span>
                      <p className="font-medium">{formatTime(result.preprocessing_time_ms)}</p>
                    </div>
                    {result.ocr_result && (
                      <>
                        <div>
                          <span className="text-gray-500">OCR Total</span>
                          <p className="font-medium text-blue-600">
                            {formatTime(result.ocr_result.total_time_ms)}
                          </p>
                        </div>
                        <div>
                          <span className="text-gray-500">Text Regions</span>
                          <p className="font-medium">{result.ocr_result.text_region_count}</p>
                        </div>
                      </>
                    )}
                    {result.detection_result && (
                      <>
                        <div>
                          <span className="text-gray-500">Detection Total</span>
                          <p className="font-medium text-green-600">
                            {formatTime(result.detection_result.total_time_ms)}
                          </p>
                        </div>
                        <div>
                          <span className="text-gray-500">UI Elements</span>
                          <p className="font-medium">{result.detection_result.element_count}</p>
                        </div>
                      </>
                    )}
                  </div>
                </CardBody>
              </Card>

              {/* OCR Timing Breakdown */}
              {result.ocr_result && (
                <Card>
                  <CardHeader>
                    <h2 className="text-lg font-semibold text-gray-900">OCR Timing Breakdown</h2>
                  </CardHeader>
                  <CardBody>
                    <TimingBreakdown steps={result.ocr_result.timing_steps} />

                    {/* Engine Info */}
                    <div className="mt-4 pt-4 border-t">
                      <h3 className="text-sm font-medium text-gray-700 mb-2">Engine Info</h3>
                      <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                        {JSON.stringify(result.ocr_result.engine_info, null, 2)}
                      </pre>
                    </div>

                    {/* Text Regions Preview */}
                    {result.ocr_result.text_regions.length > 0 && (
                      <div className="mt-4 pt-4 border-t">
                        <h3 className="text-sm font-medium text-gray-700 mb-2">
                          Extracted Text ({result.ocr_result.text_region_count} regions)
                        </h3>
                        <div className="max-h-48 overflow-y-auto space-y-1">
                          {result.ocr_result.text_regions.map((region, i) => (
                            <div
                              key={i}
                              className="text-xs p-2 bg-gray-50 rounded flex justify-between"
                            >
                              <span className="truncate flex-1">{region.text}</span>
                              <span className="text-gray-400 ml-2">
                                {(region.confidence * 100).toFixed(0)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardBody>
                </Card>
              )}

              {/* Detection Timing Breakdown */}
              {result.detection_result && (
                <Card>
                  <CardHeader>
                    <h2 className="text-lg font-semibold text-gray-900">Detection Timing Breakdown</h2>
                  </CardHeader>
                  <CardBody>
                    <TimingBreakdown steps={result.detection_result.timing_steps} />

                    {/* Model Info */}
                    <div className="mt-4 pt-4 border-t">
                      <h3 className="text-sm font-medium text-gray-700 mb-2">Model Info</h3>
                      <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                        {JSON.stringify(result.detection_result.model_info, null, 2)}
                      </pre>
                    </div>

                    {/* UI Elements Preview */}
                    {result.detection_result.elements.length > 0 && (
                      <div className="mt-4 pt-4 border-t">
                        <h3 className="text-sm font-medium text-gray-700 mb-2">
                          Detected Elements ({result.detection_result.element_count})
                        </h3>
                        <div className="max-h-48 overflow-y-auto space-y-1">
                          {result.detection_result.elements.map((elem, i) => (
                            <div
                              key={i}
                              className="text-xs p-2 bg-gray-50 rounded flex justify-between"
                            >
                              <span>
                                <span className="font-medium">{elem.type}</span>
                                {elem.label && (
                                  <span className="text-gray-500 ml-2">"{elem.label}"</span>
                                )}
                              </span>
                              <span className="text-gray-400">
                                {(elem.confidence * 100).toFixed(0)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardBody>
                </Card>
              )}

              {/* Raw Summary Data */}
              <Card>
                <CardHeader>
                  <h2 className="text-lg font-semibold text-gray-900">Raw Summary</h2>
                </CardHeader>
                <CardBody>
                  <pre className="text-xs bg-gray-50 p-3 rounded overflow-x-auto">
                    {JSON.stringify(result.summary, null, 2)}
                  </pre>
                </CardBody>
              </Card>
            </>
          ) : (
            <Card>
              <CardBody className="py-12">
                <div className="text-center text-gray-400">
                  <svg
                    className="mx-auto h-12 w-12 mb-3"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                    />
                  </svg>
                  <p className="text-lg font-medium">No Results Yet</p>
                  <p className="text-sm mt-1">Upload an image and run diagnostic to see results</p>
                </div>
              </CardBody>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

// Timing Breakdown Component
function TimingBreakdown({ steps }: { steps: TimingStep[] }) {
  if (steps.length === 0) {
    return <p className="text-sm text-gray-500">No timing data available</p>;
  }

  // Calculate total for percentage bars
  const totalDuration = steps.reduce((sum, step) => sum + step.duration_ms, 0);

  return (
    <div className="space-y-3">
      {steps.map((step, i) => {
        const percentage = (step.duration_ms / totalDuration) * 100;

        return (
          <div key={i} className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="font-medium text-gray-700">{step.name}</span>
              <span className="text-gray-600">
                {step.duration_ms >= 1000
                  ? `${(step.duration_ms / 1000).toFixed(2)}s`
                  : `${step.duration_ms.toFixed(0)}ms`}
              </span>
            </div>
            {/* Progress Bar */}
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary-500 transition-all"
                style={{ width: `${Math.max(percentage, 1)}%` }}
              />
            </div>
            {/* Details */}
            {step.details && Object.keys(step.details).length > 0 && (
              <p className="text-xs text-gray-500">
                {step.details.description as string || ''}
                {step.details.regions_processed !== undefined && (
                  <span className="ml-2">({step.details.regions_processed} regions)</span>
                )}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
