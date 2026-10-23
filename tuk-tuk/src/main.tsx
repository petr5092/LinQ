import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './prototype.css'
import App from './App'
import { TooltipProvider } from '@/components/ui/tooltip'
document.documentElement.classList.remove('dark')
document.documentElement.classList.add('light')
document.documentElement.dataset.theme = 'hr-vision'
createRoot(document.getElementById('root')!).render(<StrictMode><TooltipProvider><App /></TooltipProvider></StrictMode>)
