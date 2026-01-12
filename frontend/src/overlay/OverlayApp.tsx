import React, { useEffect, useState, useCallback } from 'react';
import { listen, emit } from '@tauri-apps/api/event';
import { Halo } from './Halo';
import type { HaloTarget, HaloEventPayload } from './types';
import { HALO_EVENTS } from './types';

/**
 * Main overlay application component
 * Listens for halo events from the Rust backend and renders highlights
 */
export const OverlayApp: React.FC = () => {
  const [currentTarget, setCurrentTarget] = useState<HaloTarget | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [isEntering, setIsEntering] = useState(false);
  const [isExiting, setIsExiting] = useState(false);

  /**
   * Handle show halo event
   */
  const handleShowHalo = useCallback((payload: HaloEventPayload) => {
    if (payload.target) {
      setCurrentTarget(payload.target);
      setIsEntering(true);
      setIsVisible(true);

      // Remove entering animation after it completes
      setTimeout(() => {
        setIsEntering(false);
      }, 300);
    }
  }, []);

  /**
   * Handle hide halo event
   */
  const handleHideHalo = useCallback(() => {
    setIsExiting(true);

    // Wait for exit animation to complete before hiding
    setTimeout(() => {
      setIsVisible(false);
      setIsExiting(false);
      setCurrentTarget(null);
    }, 300);
  }, []);

  /**
   * Handle update halo event
   */
  const handleUpdateHalo = useCallback((payload: HaloEventPayload) => {
    if (payload.target) {
      // Smooth transition to new position
      setCurrentTarget(payload.target);
      if (!isVisible) {
        setIsVisible(true);
        setIsEntering(true);
        setTimeout(() => setIsEntering(false), 300);
      }
    }
  }, [isVisible]);

  /**
   * Setup event listeners
   */
  useEffect(() => {
    const setupListeners = async () => {
      // Listen for show halo events
      const unlistenShow = await listen<HaloEventPayload>(
        HALO_EVENTS.SHOW,
        (event) => {
          console.log('Halo show event:', event.payload);
          handleShowHalo(event.payload);
        }
      );

      // Listen for hide halo events
      const unlistenHide = await listen<HaloEventPayload>(
        HALO_EVENTS.HIDE,
        () => {
          console.log('Halo hide event');
          handleHideHalo();
        }
      );

      // Listen for update halo events
      const unlistenUpdate = await listen<HaloEventPayload>(
        HALO_EVENTS.UPDATE,
        (event) => {
          console.log('Halo update event:', event.payload);
          handleUpdateHalo(event.payload);
        }
      );

      // Emit ready event to signal overlay is initialized
      await emit(HALO_EVENTS.READY, { ready: true });
      console.log('Overlay ready');

      // Cleanup on unmount
      return () => {
        unlistenShow();
        unlistenHide();
        unlistenUpdate();
      };
    };

    setupListeners().catch(console.error);
  }, [handleShowHalo, handleHideHalo, handleUpdateHalo]);

  return (
    <div className="overlay-container">
      {currentTarget && (
        <Halo
          target={currentTarget}
          isVisible={isVisible}
          isEntering={isEntering}
          isExiting={isExiting}
        />
      )}
    </div>
  );
};

export default OverlayApp;
