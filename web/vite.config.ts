import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served at the domain root on Cloudflare Pages.
export default defineConfig({
  base: '/',
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5188,
    strictPort: true,
  },
})
