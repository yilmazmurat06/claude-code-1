import { createRequire } from 'module';
import { useRef, useCallback } from 'react';

globalThis.require = createRequire(import.meta.url);

// Polyfill useEffectEvent which was removed from React 19 stable
// but is used extensively in Claude Code's codebase
if (!import.meta.resolve) {
  // React's useEffectEvent polyfill
  const react = await import('react');
  if (!react.useEffectEvent) {
    react.useEffectEvent = (callback) => {
      const ref = useRef(null);
      ref.current = callback;
      return useCallback((...args) => ref.current(...args), []);
    };
  }
}
