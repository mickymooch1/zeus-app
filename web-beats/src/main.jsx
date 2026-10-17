import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './i18n.js'
import App from './App.jsx'
import { initConsentMode } from './utils/adsConsent'
import { isIOSWebView } from './hooks/useIsIOSWebView'

// Consent Mode v2 defaults (all denied) before anything else runs; Google's tag
// only loads if this visitor has already clicked Accept on the cookie banner.
initConsentMode({ blocked: isIOSWebView })

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
