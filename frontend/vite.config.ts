import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backend = 'http://localhost:8000'

// `vite build` writes to ./dist, which the FastAPI backend serves.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': backend, '/evidence': backend } },
})
