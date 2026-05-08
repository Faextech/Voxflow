import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  base: '/',   // assets served from root — /assets/index-xxx.js
  server: {
    port: 5173,
    proxy: {
      '/api':       { target: 'http://localhost:5000', changeOrigin: true },
      '/auth':      { target: 'http://localhost:5000', changeOrigin: true },
      '/socket.io': { target: 'http://localhost:5000', changeOrigin: true, ws: true },
    },
  },
  build: {
    outDir: '../app/static/react',
    emptyOutDir: true,
  },
})
