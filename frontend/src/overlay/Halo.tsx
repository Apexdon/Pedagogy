import React, { useMemo } from 'react';
import type { HaloTarget, HaloStyleType } from './types';
import { toRenderBounds } from './types';

interface HaloProps {
  target: HaloTarget;
  isVisible: boolean;
  isEntering?: boolean;
  isExiting?: boolean;
}

/**
 * Get CSS class for animation style
 */
const getAnimationClass = (animation: HaloStyleType): string => {
  switch (animation) {
    case 'pulse':
      return 'halo-pulse';
    case 'outline':
      return 'halo-outline';
    case 'arrow':
      return 'halo-arrow';
    case 'glow':
    default:
      return 'halo-glow';
  }
};

/**
 * Halo component - renders a highlight around a target element
 *
 * Receives HaloTarget from Rust with bbox in x1,y1,x2,y2 format
 */
export const Halo: React.FC<HaloProps> = ({
  target,
  isVisible,
  isEntering = false,
  isExiting = false,
}) => {
  // Convert Rust bbox format to render bounds
  const bounds = useMemo(() => toRenderBounds(target.bbox), [target.bbox]);

  const style = useMemo(() => ({
    left: `${bounds.x}px`,
    top: `${bounds.y}px`,
    width: `${bounds.width}px`,
    height: `${bounds.height}px`,
    borderWidth: '3px',
    opacity: isVisible ? 1 : 0,
  }), [bounds, isVisible]);

  const className = useMemo(() => {
    const classes = [
      'halo',
      getAnimationClass(target.halo_style),
      'halo-blue', // Default color
    ];

    if (isEntering) classes.push('halo-entering');
    if (isExiting) classes.push('halo-exiting');

    return classes.join(' ');
  }, [target.halo_style, isEntering, isExiting]);

  if (!isVisible && !isExiting) {
    return null;
  }

  return (
    <div className={className} style={style}>
      {/* Step number indicator */}
      {target.step_number !== undefined && target.step_number > 0 && (
        <div className="step-indicator">
          {target.step_number}
        </div>
      )}

      {/* Label tooltip - show instruction */}
      {target.instruction && (
        <div className="halo-label">
          {target.label || target.instruction}
        </div>
      )}
    </div>
  );
};

export default Halo;
