import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { MotionConfig } from 'framer-motion';
import { App } from './App';
import { ErrorBoundary } from './runtime';
import { PreferencesProvider } from '../shared/preferences';
import '../shared/styles';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <ErrorBoundary>
        <PreferencesProvider>
          <App />
        </PreferencesProvider>
      </ErrorBoundary>
    </MotionConfig>
  </StrictMode>,
);
