import StockSearch from './StockSearch'

export default function Header() {
  return (
    <header
      className="border-b px-5 py-3 flex items-center justify-between flex-shrink-0"
      style={{
        background: 'rgba(28,28,30,0.92)',
        borderColor: 'rgba(255,255,255,0.08)',
        backdropFilter: 'blur(20px) saturate(180%)',
        WebkitBackdropFilter: 'blur(20px) saturate(180%)',
      }}
    >
      <div className="flex items-center gap-2.5">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center select-none flex-shrink-0"
          style={{ background: '#0A84FF', boxShadow: '0 2px 8px rgba(10,132,255,0.4)' }}
        >
          <span className="text-white font-bold text-sm">D</span>
        </div>
        <div>
          <h1 className="font-semibold text-[15px] leading-none tracking-tight" style={{ color: '#F5F5F7' }}>
            DeepValue
          </h1>
          <p className="text-[11px] mt-0.5" style={{ color: 'rgba(235,235,245,0.4)' }}>
            Investment Analyzer
          </p>
        </div>
      </div>

      <StockSearch />
    </header>
  )
}
