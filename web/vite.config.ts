import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Repo name drives the GitHub Pages base path.
export default defineConfig({
  base: '/is-the-mountain-out/',
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5188,
    strictPort: true,
  },
})
