import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { ErrorBoundary } from './runtime';
import { PreferencesProvider } from '../shared/preferences';
import '../shared/styles';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <PreferencesProvider>
        <App />
      </PreferencesProvider>
    </ErrorBoundary>
  </StrictMode>,
);
