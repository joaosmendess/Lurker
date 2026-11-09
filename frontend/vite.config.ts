import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // The backend's CORS allows exactly http://localhost:5173. If the port were
    // busy, Vite would silently pick 5174 and every API call would fail with a
    // confusing CORS error; strictPort makes it fail loudly instead.
    port: 5173,
    strictPort: true,
  },
})
