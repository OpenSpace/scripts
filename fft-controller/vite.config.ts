import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// The app talks directly to OpenSpace's WebSocket interface (ws://host:4682)
// from the browser, so no dev-server proxy is needed.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173
  }
});
