import type { Section } from '../types'

interface Props {
  active: Section
  onNavigate: (s: Section) => void
  chatOpen: boolean
  onChatToggle: () => void
}

// ── SVG icon wrappers (functions, not module-level JSX) ──────────────────────
function BarChartIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="12" width="4" height="9" rx="1"/>
      <rect x="9.5" y="7" width="4" height="14" rx="1"/>
      <rect x="16" y="3" width="4" height="18" rx="1"/>
    </svg>
  )
}

function LineChartIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  )
}

function ValuationIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="1" x2="12" y2="23"/>
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
    </svg>
  )
}

function TableIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2"/>
      <line x1="3" y1="9" x2="21" y2="9"/>
      <line x1="3" y1="15" x2="21" y2="15"/>
      <line x1="9" y1="9" x2="9" y2="21"/>
    </svg>
  )
}

function AIIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
    </svg>
  )
}

function ChatIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  )
}

// ── Nav item ─────────────────────────────────────────────────────────────────
interface NavItemProps {
  label: string
  icon: React.ReactNode
  isActive: boolean
  onClick: () => void
}

function NavItem({ label, icon, isActive, onClick }: NavItemProps) {
  return (
    <button
      onClick={onClick}
      title={label}
      className="flex flex-col items-center justify-center gap-1.5 rounded-xl transition-all"
      style={{
        width:      56,
        paddingTop: 10,
        paddingBottom: 10,
        background: isActive ? 'rgba(10,132,255,0.2)' : 'transparent',
        color:      isActive ? '#0A84FF' : 'rgba(235,235,245,0.45)',
        border:     isActive ? '1px solid rgba(10,132,255,0.35)' : '1px solid transparent',
        cursor:     'pointer',
      }}
      onMouseEnter={e => {
        if (!isActive) {
          const el = e.currentTarget as HTMLElement
          el.style.background = 'rgba(255,255,255,0.07)'
          el.style.color = 'rgba(235,235,245,0.8)'
        }
      }}
      onMouseLeave={e => {
        if (!isActive) {
          const el = e.currentTarget as HTMLElement
          el.style.background = 'transparent'
          el.style.color = 'rgba(235,235,245,0.45)'
        }
      }}
    >
      {icon}
      <span style={{ fontSize: 9, fontWeight: 500, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
        {label}
      </span>
    </button>
  )
}

// ── Sidebar ───────────────────────────────────────────────────────────────────
const NAV: { id: Section; label: string; icon: () => React.ReactNode }[] = [
  { id: 'ratios',     label: 'Ratios',      icon: BarChartIcon  },
  { id: 'chart',      label: 'Chart',       icon: LineChartIcon },
  { id: 'valuation',  label: 'Valuation',   icon: ValuationIcon },
  { id: 'statements', label: 'Statements',  icon: TableIcon     },
  { id: 'ai',         label: 'AI Pick',     icon: AIIcon        },
]

export default function Sidebar({ active, onNavigate, chatOpen, onChatToggle }: Props) {
  return (
    <nav
      style={{
        width:        72,
        flexShrink:   0,
        display:      'flex',
        flexDirection:'column',
        alignItems:   'center',
        paddingTop:   12,
        paddingBottom:12,
        gap:          4,
        background:   '#111113',
        borderRight:  '1px solid rgba(255,255,255,0.1)',
        height:       '100%',
      }}
    >
      {NAV.map(item => (
        <NavItem
          key={item.id}
          label={item.label}
          icon={<item.icon />}
          isActive={active === item.id}
          onClick={() => onNavigate(item.id)}
        />
      ))}

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Divider */}
      <div style={{ width: 40, height: 1, background: 'rgba(255,255,255,0.08)', marginBottom: 4 }} />

      {/* Chat toggle */}
      <NavItem
        label="Chat"
        icon={<ChatIcon />}
        isActive={chatOpen}
        onClick={onChatToggle}
      />
    </nav>
  )
}
