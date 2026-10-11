import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// TRIPWRIGHT_BACKEND points the dev server at another backend, such as a test one on its own port.
const backend = process.env.TRIPWRIGHT_BACKEND ?? 'http://localhost:8000'

// `vite build` writes to ./dist, which the FastAPI backend serves.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': backend, '/evidence': backend } },
})
