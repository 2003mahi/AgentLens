import React, { useState, useEffect, Suspense, lazy } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import EvaluationOrbFallback from './EvaluationOrbFallback.jsx';

// Lazy-load 3D React Three Fiber component only when needed and compatible
const EvaluationOrb3D = lazy(() => import('./EvaluationOrb3D.jsx'));

function checkWebGLSupport() {
  try {
    const canvas = document.createElement('canvas');
    return !!(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
  } catch (e) {
    return false;
  }
}

export default function EvaluationOrbWidget() {
  const [status, setStatus] = useState('idle');
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const [hasWebGL, setHasWebGL] = useState(true);
  const [is3DEnabled, setIs3DEnabled] = useState(true);

  useEffect(() => {
    // Check reduced motion preference
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReducedMotion(mediaQuery.matches);
    const listener = (e) => setPrefersReducedMotion(e.matches);
    mediaQuery.addEventListener('change', listener);

    // Check WebGL availability
    setHasWebGL(checkWebGLSupport());

    // Listen to platform events from app.js if dispatched
    const handlePlatformEvent = (e) => {
      if (e.detail?.status) {
        setStatus(e.detail.status);
      }
    };
    window.addEventListener('eval-platform-status', handlePlatformEvent);

    return () => {
      mediaQuery.removeEventListener('change', listener);
      window.removeEventListener('eval-platform-status', handlePlatformEvent);
    };
  }, []);

  const statusDescriptions = {
    idle: 'Platform ready. Invariants armed and listening.',
    running: 'Experiment executing. Agent trajectory evaluation active.',
    success: 'Evaluation verified: 100% policy compliance & ground truth match.',
    failed: 'Discrepancy detected: unauthorized action or invariant violation.'
  };

  const statusLabels = {
    idle: 'Core: Ready',
    running: 'Core: Active Run',
    success: 'Core: Pass (1.00)',
    failed: 'Core: Violation'
  };

  const shouldUse3D = is3DEnabled && hasWebGL && !prefersReducedMotion;

  return (
    <motion.div
      className="card eval-orb-card"
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 260, damping: 20 }}
      role="region"
      aria-label="Agent Evaluation Core visualization"
      style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(240px, 320px) 1fr',
        gap: '1.5rem',
        alignItems: 'center',
        padding: '1.5rem',
        background: 'linear-gradient(135deg, rgba(28, 31, 39, 0.95) 0%, rgba(17, 19, 24, 0.98) 100%)',
        borderRadius: '12px',
        border: '1px solid rgba(78, 140, 255, 0.15)',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.35)',
        marginBottom: '1.5rem',
        position: 'relative',
        overflow: 'hidden'
      }}
    >
      {/* Visualizer viewport */}
      <div 
        style={{
          width: '100%',
          height: '240px',
          position: 'relative',
          borderRadius: '8px',
          background: 'radial-gradient(circle at center, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 0.8) 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden'
        }}
      >
        {shouldUse3D ? (
          <Suspense fallback={<EvaluationOrbFallback status={status} reason="Loading 3D core..." />}>
            <EvaluationOrb3D status={status} />
          </Suspense>
        ) : (
          <EvaluationOrbFallback 
            status={status} 
            reason={prefersReducedMotion ? 'Reduced motion active' : !hasWebGL ? 'WebGL unavailable' : '2D mode active'} 
          />
        )}

        {/* Status Chip Overlay */}
        <motion.div
          key={status}
          initial={{ scale: 0.85, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 350, damping: 22 }}
          style={{
            position: 'absolute',
            bottom: '10px',
            left: '10px',
            fontSize: '0.75rem',
            padding: '3px 8px',
            borderRadius: '12px',
            background: 'rgba(15, 23, 42, 0.85)',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            color: '#e2e8f0',
            backdropFilter: 'blur(4px)',
            pointerEvents: 'none'
          }}
        >
          {statusLabels[status]}
        </motion.div>
      </div>

      {/* Control & Telemetry Panel */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#64748b', fontWeight: 600 }}>
              Agent Node Visualizer
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {prefersReducedMotion && (
                <span 
                  title="Reduced motion mode enforced by system"
                  style={{ fontSize: '0.7rem', padding: '2px 6px', background: 'rgba(255,255,255,0.08)', borderRadius: '4px', color: '#94a3b8' }}
                >
                  Reduced Motion
                </span>
              )}
              {hasWebGL && !prefersReducedMotion && (
                <button
                  type="button"
                  onClick={() => setIs3DEnabled(!is3DEnabled)}
                  style={{
                    fontSize: '0.7rem',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    background: is3DEnabled ? 'rgba(78, 140, 255, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(78, 140, 255, 0.3)',
                    color: is3DEnabled ? '#93c5fd' : '#64748b',
                    cursor: 'pointer'
                  }}
                  aria-label="Toggle 3D visualization mode"
                >
                  {is3DEnabled ? '3D Active' : '2D Fallback'}
                </button>
              )}
            </div>
          </div>
          <h3 style={{ margin: '0.3rem 0', fontSize: '1.2rem', color: '#f8fafc', fontWeight: 600 }}>
            Evaluation Core & Trace Pulse
          </h3>
          <p style={{ margin: 0, fontSize: '0.85rem', color: '#94a3b8', lineHeight: 1.4 }}>
            {statusDescriptions[status]}
          </p>
        </div>

        {/* State Interactive Simulation Triggers with Motion Spring Feedback */}
        <div>
          <span style={{ fontSize: '0.75rem', color: '#64748b', display: 'block', marginBottom: '0.4rem' }}>
            Visual Feedback State Simulator:
          </span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {[
              { id: 'idle', label: 'Idle / Ready', color: '#3b82f6' },
              { id: 'running', label: 'Evaluating Attempt', color: '#f59e0b' },
              { id: 'success', label: 'Score Pass', color: '#10b981' },
              { id: 'failed', label: 'Policy Fail', color: '#ef4444' }
            ].map((item) => (
              <motion.button
                key={item.id}
                type="button"
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.95 }}
                transition={{ type: 'spring', stiffness: 400, damping: 17 }}
                onClick={() => setStatus(item.id)}
                style={{
                  padding: '5px 10px',
                  fontSize: '0.75rem',
                  borderRadius: '6px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  border: status === item.id ? `1px solid ${item.color}` : '1px solid rgba(255,255,255,0.1)',
                  background: status === item.id ? `${item.color}22` : 'rgba(255,255,255,0.03)',
                  color: status === item.id ? item.color : '#94a3b8'
                }}
                aria-pressed={status === item.id}
              >
                {item.label}
              </motion.button>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
