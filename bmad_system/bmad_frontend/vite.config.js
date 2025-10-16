import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import fs from 'fs'
import dotenv from 'dotenv'

// https://vite.dev/config/
// Load parent .env (bmad_system/.env) if present to drive ports/hosts
const rootDir = path.resolve(__dirname, '..')
const rootEnvPath = path.join(rootDir, '.env')
let rootEnv = {}
try {
  if (fs.existsSync(rootEnvPath)) {
    const parsed = dotenv.parse(fs.readFileSync(rootEnvPath))
    rootEnv = parsed || {}
  }
} catch (_) {}

const FRONTEND_PORT = Number(process.env.VITE_FRONTEND_PORT || rootEnv.FRONTEND_PORT || 5005)

export default defineConfig({
  plugins: [react(),tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: FRONTEND_PORT,
    strictPort: true,
    host: true
  },
  preview: {
    port: FRONTEND_PORT,
    strictPort: true,
    host: true
  },
  define: {
    'import.meta.env.VITE_FRONTEND_PORT': JSON.stringify(String(FRONTEND_PORT)),
    'import.meta.env.VITE_FRONTEND_HOST': JSON.stringify(process.env.VITE_FRONTEND_HOST || rootEnv.FRONTEND_HOST || ''),
    'import.meta.env.VITE_BACKEND_HOST': JSON.stringify(process.env.VITE_BACKEND_HOST || rootEnv.BACKEND_HOST || ''),
    'import.meta.env.VITE_BACKEND_PORT': JSON.stringify(process.env.VITE_BACKEND_PORT || rootEnv.BACKEND_PORT || ''),
    'import.meta.env.VITE_API_BASE_URL': JSON.stringify(process.env.VITE_API_BASE_URL || rootEnv.API_BASE_URL || '')
  }
})
