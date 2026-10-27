import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // 개발 중에는 /api 요청을 FastAPI 서버로 넘긴다 (CORS 설정 없이 동작)
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
