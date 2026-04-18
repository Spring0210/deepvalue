import { useState } from 'react'
import { StockProvider } from './context/StockContext'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'
import ChatDrawer from './components/ChatDrawer'
import ErrorBoundary from './components/ErrorBoundary'
import type { Section } from './types'

export default function App() {
  const [section, setSection]   = useState<Section>('ratios')
  const [chatOpen, setChatOpen] = useState(false)

  return (
    <StockProvider>
      <div className="h-screen flex flex-col overflow-hidden" style={{ background: '#1C1C1E' }}>
        <Header />
        <div className="flex-1 flex overflow-hidden min-h-0 relative">
          <Sidebar
            active={section}
            onNavigate={setSection}
            chatOpen={chatOpen}
            onChatToggle={() => setChatOpen(p => !p)}
          />
          <main className="flex-1 overflow-y-auto min-w-0">
            <ErrorBoundary>
              <Dashboard section={section} />
            </ErrorBoundary>
          </main>
          <ErrorBoundary>
            <ChatDrawer open={chatOpen} onClose={() => setChatOpen(false)} />
          </ErrorBoundary>
        </div>
      </div>
    </StockProvider>
  )
}
