import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { watchViewport } from './lib/viewport'

// 화면을 그리기 전에 실제 화면 높이부터 잡는다 (iPhone 홈 화면 앱 대응)
watchViewport()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
