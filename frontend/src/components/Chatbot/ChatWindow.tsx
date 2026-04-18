import { useState, useRef, useEffect } from 'react'
import { useStock } from '../../context/StockContext'
import { streamChat } from '../../api/client'
import type { Message } from '../../types'

const WELCOME: Message = {
  role: 'assistant',
  content:
    "Good day. I'm your Warren Buffett AI advisor. Search for a stock above, then ask me anything — financial health, investment thesis, ratio interpretation, or general Buffett principles.",
}

export default function ChatWindow({ hideHeader = false }: { hideHeader?: boolean }) {
  const [messages, setMessages] = useState<Message[]>([WELCOME])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const { ticker, ratios } = useStock()
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    const question = input.trim()
    if (!question || streaming) return
    setInput('')

    // Build history from all completed messages (skip the welcome intro)
    const history = messages
      .filter(m => m !== WELCOME && !m.streaming && m.content)
      .map(({ role, content }) => ({ role, content }))

    setMessages(prev => [
      ...prev,
      { role: 'user', content: question },
      { role: 'assistant', content: '', streaming: true },
    ])
    setStreaming(true)

    try {
      await streamChat(question, ticker, ratios, history,
        token => {
          setMessages(prev => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last?.role === 'assistant')
              next[next.length - 1] = { ...last, content: last.content + token }
            return next
          })
        },
        () => {
          setMessages(prev => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last?.role === 'assistant')
              next[next.length - 1] = { ...last, streaming: false }
            return next
          })
          setStreaming(false)
          inputRef.current?.focus()
        },
      )
    } catch {
      setMessages(prev => {
        const next = [...prev]
        next[next.length - 1] = {
          role: 'assistant',
          content: 'An error occurred. Please check your API key and try again.',
          streaming: false,
        }
        return next
      })
      setStreaming(false)
    }
  }

  return (
    <div
      className="h-full flex flex-col overflow-hidden"
      style={{ background: 'transparent' }}
    >
      {/* Header — only shown when not inside ChatDrawer */}
      {!hideHeader && (
        <div
          className="border-b px-4 py-3 flex items-center gap-2.5 flex-shrink-0"
          style={{ borderColor: 'rgba(255,255,255,0.08)', background: 'rgba(28,28,30,0.5)' }}
        >
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center font-bold text-xs flex-shrink-0 text-white"
            style={{ background: '#0A84FF', boxShadow: '0 2px 8px rgba(10,132,255,0.35)' }}
          >
            AI
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold leading-none" style={{ color: '#F5F5F7' }}>AI Advisor</p>
            <p className="text-[10px] mt-0.5" style={{ color: 'rgba(235,235,245,0.3)' }}>
              Buffett Framework · RAG
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full" style={{ background: '#30D158' }} />
            <span className="text-[10px]" style={{ color: 'rgba(235,235,245,0.3)' }}>Live</span>
          </div>
          {ticker && (
            <span
              className="text-[11px] font-mono font-semibold px-2 py-0.5 rounded-md"
              style={{ color: '#0A84FF', background: 'rgba(10,132,255,0.12)', border: '1px solid rgba(10,132,255,0.2)' }}
            >
              {ticker}
            </span>
          )}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2.5">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div
                className="w-6 h-6 rounded-md flex items-center justify-center mr-2 mt-1 flex-shrink-0 text-white font-bold text-[9px]"
                style={{ background: '#0A84FF', flexShrink: 0 }}
              >
                AI
              </div>
            )}
            <div
              className="max-w-[84%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed"
              style={
                msg.role === 'user'
                  ? {
                      borderRadius: '18px 18px 4px 18px',
                      background: '#0A84FF',
                      color: '#ffffff',
                    }
                  : {
                      borderRadius: '18px 18px 18px 4px',
                      background: '#3A3A3C',
                      color: 'rgba(235,235,245,0.75)',
                      border: '1px solid rgba(255,255,255,0.06)',
                    }
              }
            >
              {msg.content === '' && msg.streaming ? (
                <span className="inline-flex gap-1 items-center h-4">
                  {[0, 150, 300].map(delay => (
                    <span
                      key={delay}
                      className="w-1.5 h-1.5 rounded-full animate-bounce"
                      style={{ background: 'rgba(235,235,245,0.3)', animationDelay: `${delay}ms` }}
                    />
                  ))}
                </span>
              ) : (
                <>
                  {msg.content}
                  {msg.streaming && (
                    <span
                      className="inline-block w-0.5 h-3.5 ml-0.5 animate-pulse align-text-bottom"
                      style={{ background: 'rgba(235,235,245,0.6)' }}
                    />
                  )}
                </>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div
        className="border-t p-3 flex gap-2 flex-shrink-0"
        style={{ borderColor: 'rgba(255,255,255,0.08)', background: 'rgba(28,28,30,0.5)' }}
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          placeholder={ticker ? `Ask about ${ticker}…` : 'Ask about investing…'}
          disabled={streaming}
          className="flex-1 rounded-xl px-3 py-2 text-[13px] outline-none transition-all disabled:opacity-40"
          style={{
            background: 'rgba(255,255,255,0.07)',
            border: '1px solid rgba(255,255,255,0.09)',
            color: '#F5F5F7',
          }}
          onFocus={e => (e.target.style.borderColor = 'rgba(10,132,255,0.6)')}
          onBlur={e => (e.target.style.borderColor = 'rgba(255,255,255,0.09)')}
        />
        <button
          onClick={send}
          disabled={streaming || !input.trim()}
          className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 transition-all disabled:opacity-30 disabled:cursor-not-allowed text-white"
          style={{ background: '#0A84FF' }}
          aria-label="Send"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="19" x2="12" y2="5" />
            <polyline points="5 12 12 5 19 12" />
          </svg>
        </button>
      </div>
    </div>
  )
}
