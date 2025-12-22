/**
 * Detection Preview Component
 *
 * Shows a preview of the captured screen with detected elements overlay.
 */

import { useMemo, useState } from 'react';
import { useDetection } from '@/hooks/useDetection';
import type { UIElement, BoundingBox } from '@/types/detection';

interface DetectionPreviewProps {
  className?: string;
  maxHeight?: number;
  showLabels?: boolean;
  highlightedElementId?: string;
  onElementClick?: (element: UIElement) => void;
}

export function DetectionPreview({
  className = '',
  maxHeight = 400,
  showLabels = true,
  highlightedElementId,
  onElementClick,
}: DetectionPreviewProps) {
  const { capture, screenState, isReady } = useDetection();
  const [hoveredElementId, setHoveredElementId] = useState<string | null>(null);

  // Calculate scale factor for display
  const scale = useMemo(() => {
    if (!screenState?.image_size) return 1;
    return maxHeight / screenState.image_size.height;
  }, [screenState?.image_size, maxHeight]);

  // Scale bounding box coordinates
  const scaleBbox = (bbox: BoundingBox) => ({
    x1: bbox.x1 * scale,
    y1: bbox.y1 * scale,
    x2: bbox.x2 * scale,
    y2: bbox.y2 * scale,
  });

  if (!isReady || !capture || !screenState) {
    return null;
  }

  const displayWidth = screenState.image_size.width * scale;
  const displayHeight = screenState.image_size.height * scale;

  return (
    <div
      className={`detection-preview relative overflow-hidden rounded-lg border border-gray-200 ${className}`}
      style={{ width: displayWidth, height: displayHeight }}
    >
      {/* Screenshot Image */}
      <img
        src={`data:image/png;base64,${capture.image_base64}`}
        alt="Captured screen"
        className="absolute inset-0 w-full h-full object-contain"
      />

      {/* Element Overlays */}
      <div className="absolute inset-0">
        {screenState.elements.map((element) => {
          const scaledBbox = scaleBbox(element.bbox);
          const isHighlighted = element.element_id === highlightedElementId;
          const isHovered = element.element_id === hoveredElementId;

          return (
            <div
              key={element.element_id}
              className={`absolute border-2 rounded transition-all cursor-pointer
                ${
                  isHighlighted
                    ? 'border-blue-500 bg-blue-500/20 shadow-lg shadow-blue-500/50'
                    : isHovered
                      ? 'border-green-400 bg-green-500/10'
                      : 'border-green-500/70'
                }
              `}
              style={{
                left: scaledBbox.x1,
                top: scaledBbox.y1,
                width: scaledBbox.x2 - scaledBbox.x1,
                height: scaledBbox.y2 - scaledBbox.y1,
              }}
              onClick={() => onElementClick?.(element)}
              onMouseEnter={() => setHoveredElementId(element.element_id)}
              onMouseLeave={() => setHoveredElementId(null)}
              title={`${element.type}${element.label ? `: ${element.label}` : ''} (${Math.round(element.confidence * 100)}%)`}
            >
              {/* Label */}
              {showLabels && (isHovered || isHighlighted) && (
                <span className="absolute -top-6 left-0 text-xs px-2 py-1 bg-gray-900 text-white rounded whitespace-nowrap z-10">
                  {element.label || element.type}
                  <span className="ml-1 text-gray-400">
                    {Math.round(element.confidence * 100)}%
                  </span>
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Info Badge */}
      <div className="absolute bottom-2 right-2 bg-black/70 text-white text-xs px-3 py-1.5 rounded-full">
        {screenState.elements.length} elements detected
      </div>
    </div>
  );
}

/**
 * Compact version of DetectionPreview for thumbnails
 */
export function DetectionThumbnail({
  capture,
  screenState,
  onClick,
  className = '',
}: {
  capture: { image_base64: string };
  screenState?: { elements: UIElement[]; image_size: { width: number; height: number } };
  onClick?: () => void;
  className?: string;
}) {
  return (
    <div
      className={`relative cursor-pointer rounded-lg overflow-hidden border border-gray-200 hover:border-blue-400 transition-colors ${className}`}
      onClick={onClick}
    >
      <img
        src={`data:image/png;base64,${capture.image_base64}`}
        alt="Capture thumbnail"
        className="w-full h-full object-cover"
      />
      {screenState && (
        <div className="absolute bottom-1 right-1 bg-black/70 text-white text-xs px-2 py-0.5 rounded">
          {screenState.elements.length} elements
        </div>
      )}
    </div>
  );
}
