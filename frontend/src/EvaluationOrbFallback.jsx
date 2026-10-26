import React from 'react';

export default function EvaluationOrbFallback({ status = 'idle', reason = '' }) {
  const statusColors = {
    idle: { primary: '#4e8cff', secondary: '#2563eb', glow: 'rgba(78, 140, 255, 0.35)' },
    running: { primary: '#f59e0b', secondary: '#8b5cf6', glow: 'rgba(245, 158, 11, 0.4)' },
    success: { primary: '#10b981', secondary: '#059669', glow: 'rgba(16, 185, 129, 0.4)' },
    failed: { primary: '#ef4444', secondary: '#b91c1c', glow: 'rgba(239, 68, 68, 0.4)' }
  };

  const current = statusColors[status] || statusColors.idle;

  return (
    <div 
      className="orb-fallback-wrapper"
      role="img"
      aria-label={`Evaluation Orb visualizer in ${status} state: ${reason || 'Static fallback'}`}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        minHeight: '220px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden'
      }}
    >
      <div
        className="orb-glow-core"
        style={{
          width: '110px',
          height: '110px',
          borderRadius: '50%',
          background: `radial-gradient(circle at 35% 35%, #ffffff 0%, ${current.primary} 45%, ${current.secondary} 85%, #0f172a 100%)`,
          boxShadow: `0 0 35px ${current.glow}, inset 0 0 20px rgba(255, 255, 255, 0.4)`,
          border: '1px solid rgba(255, 255, 255, 0.25)',
          transition: 'all 0.4s ease',
          position: 'relative',
          zIndex: 2
        }}
      />
      
      {/* Outer subtle orbital ring */}
      <div
        className="orb-orbit-ring"
        style={{
          position: 'absolute',
          width: '180px',
          height: '180px',
          borderRadius: '50%',
          border: `1.5px dashed ${current.primary}`,
          opacity: 0.45,
          zIndex: 1
        }}
      />

      {/* Orbiting nodes */}
      <div
        style={{
          position: 'absolute',
          width: '10px',
          height: '10px',
          borderRadius: '50%',
          backgroundColor: current.primary,
          boxShadow: `0 0 8px ${current.primary}`,
          top: '30px',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 3
        }}
      />
    </div>
  );
}
