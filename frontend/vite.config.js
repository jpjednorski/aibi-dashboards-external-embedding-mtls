import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    // No proxy - frontend will make direct calls to https://localhost:443
    // This allows the browser to present the client certificate to nginx
  }
})


