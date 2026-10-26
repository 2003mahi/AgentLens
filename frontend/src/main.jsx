import React from 'react';
import ReactDOM from 'react-dom/client';
import EvaluationOrbWidget from './EvaluationOrbWidget.jsx';

function mountEvaluationOrb() {
  const container = document.getElementById('eval-orb-root');
  if (container && !container._reactRoot) {
    const root = ReactDOM.createRoot(container);
    container._reactRoot = root;
    root.render(
      <React.StrictMode>
        <EvaluationOrbWidget />
      </React.StrictMode>
    );
  }
}

// Enhance UI with spring motion and state dispatch
function enhanceInteractiveElements() {
  // Listen for experiment actions to dispatch visual state feedback
  const originalFetch = window.fetch;
  window.addEventListener('click', (e) => {
    const btn = e.target.closest('button, .btn, .nav-item');
    if (!btn) return;

    if (btn.id === 'btn-run-experiment' || btn.classList.contains('btn-run')) {
      window.dispatchEvent(new CustomEvent('eval-platform-status', { detail: { status: 'running' } }));
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    mountEvaluationOrb();
    enhanceInteractiveElements();
  });
} else {
  mountEvaluationOrb();
  enhanceInteractiveElements();
}
