/**
 * Detection Status Component
 *
 * Displays the current detection status and provides controls.
 */

import { useDetection } from '@/hooks/useDetection';
import { Button, Loading } from '@/components/ui';

interface DetectionStatusProps {
  className?: string;
  showDetails?: boolean;
}

export function DetectionStatus({
  className = '',
  showDetails = false,
}: DetectionStatusProps) {
  const {
    status,
    screenState,
    error,
    isCapturing,
    isAnalyzing,
    startCapture,
    resetSession,
    clearError,
  } = useDetection();

  const getStatusColor = () => {
    switch (status) {
      case 'capturing':
      case 'analyzing':
        return 'bg-blue-500';
      case 'ready':
        return 'bg-green-500';
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-gray-400';
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'idle':
        return 'Ready to capture';
      case 'capturing':
        return 'Capturing screen...';
      case 'analyzing':
        return 'Analyzing...';
      case 'ready':
        return `Detected ${screenState?.elements.length ?? 0} elements`;
      case 'error':
        return `Error: ${error}`;
      default:
        return 'Unknown';
    }
  };

  return (
    <div className={`detection-status ${className}`}>
      {/* Status Indicator */}
      <div className="flex items-center gap-3 p-4 bg-white rounded-lg shadow-sm border border-gray-200">
        <div className={`w-3 h-3 rounded-full ${getStatusColor()}`} />
        <span className="text-sm font-medium text-gray-700">{getStatusText()}</span>

        {/* Action Buttons */}
        <div className="ml-auto flex gap-2">
          {status === 'idle' && (
            <Button onClick={startCapture} size="sm">
              Capture (Ctrl+Shift+P)
            </Button>
          )}

          {status === 'ready' && (
            <Button variant="secondary" size="sm" onClick={resetSession}>
              New Capture
            </Button>
          )}

          {status === 'error' && (
            <Button variant="secondary" size="sm" onClick={clearError}>
              Dismiss
            </Button>
          )}
        </div>
      </div>

      {/* Details Panel */}
      {showDetails && status === 'ready' && screenState && (
        <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <h4 className="font-medium text-gray-900 mb-3">Analysis Results</h4>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Elements Detected:</span>
              <span className="ml-2 font-medium text-gray-900">
                {screenState.elements.length}
              </span>
            </div>
            <div>
              <span className="text-gray-500">Text Regions:</span>
              <span className="ml-2 font-medium text-gray-900">
                {screenState.text_regions.length}
              </span>
            </div>
            <div>
              <span className="text-gray-500">Image Size:</span>
              <span className="ml-2 font-medium text-gray-900">
                {screenState.image_size.width} x {screenState.image_size.height}
              </span>
            </div>
            <div>
              <span className="text-gray-500">Processing Time:</span>
              <span className="ml-2 font-medium text-gray-900">
                {screenState.processing_time_ms.toFixed(0)}ms
              </span>
            </div>
          </div>

          {/* Element Types Summary */}
          {screenState.elements.length > 0 && (
            <div className="mt-4">
              <span className="text-gray-500 text-sm">Element Types:</span>
              <div className="flex flex-wrap gap-2 mt-2">
                {Object.entries(
                  screenState.elements.reduce(
                    (acc, el) => {
                      acc[el.type] = (acc[el.type] || 0) + 1;
                      return acc;
                    },
                    {} as Record<string, number>
                  )
                ).map(([type, count]) => (
                  <span
                    key={type}
                    className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full"
                  >
                    {type}: {count}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Loading Indicator */}
      {(isCapturing || isAnalyzing) && (
        <div className="mt-4 flex items-center justify-center">
          <Loading size="md" />
          <span className="ml-2 text-sm text-gray-600">
            {isCapturing ? 'Capturing screen...' : 'Analyzing with AI...'}
          </span>
        </div>
      )}
    </div>
  );
}
