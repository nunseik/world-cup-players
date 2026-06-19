import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/v1': {
        target: 'http://136.248.99.64',
        changeOrigin: true,
      },
    },
  },
})
