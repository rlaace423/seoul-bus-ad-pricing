import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base: './' so the static build works under any subpath (e.g. Cloudflare Pages).
export default defineConfig({
  base: './',
  plugins: [react()],
})
