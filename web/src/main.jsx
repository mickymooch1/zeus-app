import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import AdPoster from './pages/AdPoster.jsx'
import './pages/AdPoster.css'

const root = createRoot(document.getElementById('root'))

if (window.location.pathname === '/ad-poster') {
  // Render completely isolated — no index.css, no AuthProvider, no layout wrapper
  root.render(
    <StrictMode>
      <AdPoster />
    </StrictMode>
  )
} else {
  root.render(
    <StrictMode>
      <App />
    </StrictMode>
  )
}
