import ChatWindow from './Chatbot/ChatWindow'

interface Props {
  open: boolean
  onClose: () => void
}

export default function ChatDrawer({ open, onClose }: Props) {
  return (
    <>
      {/* Backdrop — fixed, full viewport, click to close */}
      <div
        onClick={onClose}
        style={{
          position:           'fixed',
          inset:              0,
          zIndex:             200,
          background:         'rgba(0,0,0,0.5)',
          backdropFilter:     'blur(4px)',
          WebkitBackdropFilter: 'blur(4px)',
          opacity:            open ? 1 : 0,
          pointerEvents:      open ? 'auto' : 'none',
          transition:         'opacity 0.25s ease',
        }}
      />

      {/* Drawer panel — fixed to right edge of viewport */}
      <div
        style={{
          position:       'fixed',
          top:            0,
          right:          0,
          bottom:         0,
          zIndex:         201,
          width:          420,
          display:        'flex',
          flexDirection:  'column',
          background:     '#1C1C1E',
          borderLeft:     '1px solid rgba(255,255,255,0.1)',
          boxShadow:      '-16px 0 48px rgba(0,0,0,0.6)',
          transform:      open ? 'translateX(0)' : 'translateX(100%)',
          transition:     'transform 0.28s cubic-bezier(0.4, 0, 0.2, 1)',
        }}
      >
        {/* Drawer header */}
        <div
          className="flex items-center justify-between px-4 flex-shrink-0"
          style={{
            height: 56,
            borderBottom: '1px solid rgba(255,255,255,0.08)',
            background: 'rgba(28,28,30,0.9)',
          }}
        >
          <div className="flex items-center gap-2.5">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center font-bold text-xs text-white"
              style={{ background: '#0A84FF', boxShadow: '0 2px 8px rgba(10,132,255,0.35)' }}
            >
              AI
            </div>
            <div>
              <p className="text-sm font-semibold leading-none" style={{ color: '#F5F5F7' }}>AI Advisor</p>
              <p className="text-[10px] mt-0.5" style={{ color: 'rgba(235,235,245,0.3)' }}>
                Buffett Framework · RAG
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full" style={{ background: '#30D158' }} />
              <span className="text-[10px]" style={{ color: 'rgba(235,235,245,0.3)' }}>Live</span>
            </div>
            <button
              onClick={onClose}
              className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ color: 'rgba(235,235,245,0.5)', background: 'rgba(255,255,255,0.08)' }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>

        {/* Chat window fills remaining height */}
        <div style={{ flex: 1, minHeight: 0 }}>
          <ChatWindow hideHeader />
        </div>
      </div>
    </>
  )
}
