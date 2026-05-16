import { useState } from 'react'
import { StockProvider } from './context/StockContext'
import { WatchlistProvider } from './context/WatchlistContext'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'
import ChatDrawer from './components/ChatDrawer'
import ErrorBoundary from './components/ErrorBoundary'
import type { Section } from './types'

const VALID_SECTIONS: Section[] = ['ratios', 'chart', 'valuation', 'statements', 'ai', 'agent', 'watchlist']

export default function App() {
  const [section, setSection] = useState<Section>(() => {
    const saved = localStorage.getItem('deepvalue_section')
    return (saved && VALID_SECTIONS.includes(saved as Section)) ? saved as Section : 'ratios'
  })
  const [chatOpen, setChatOpen] = useState(false)

  function handleNavigate(s: Section) {
    setSection(s)
    localStorage.setItem('deepvalue_section', s)
  }

  return (
    <StockProvider>
      <WatchlistProvider>
        <div className="h-screen flex flex-col overflow-hidden" style={{ background: '#1C1C1E' }}>
          <Header />
          <div className="flex-1 flex overflow-hidden min-h-0 relative">
            <Sidebar
              active={section}
              onNavigate={handleNavigate}
              chatOpen={chatOpen}
              onChatToggle={() => setChatOpen(p => !p)}
            />
            <main className="flex-1 overflow-y-auto min-w-0">
              <ErrorBoundary>
                <Dashboard section={section} onNavigate={handleNavigate} />
              </ErrorBoundary>
            </main>
            <ErrorBoundary>
              <ChatDrawer open={chatOpen} onClose={() => setChatOpen(false)} />
            </ErrorBoundary>
          </div>
        </div>
      </WatchlistProvider>
    </StockProvider>
  )
}
