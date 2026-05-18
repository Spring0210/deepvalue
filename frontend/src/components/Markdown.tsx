import type { ReactNode } from 'react'

// Tiny markdown renderer shared by the AI advisor chat and the orchestrator
// final answer. Both produce a fixed output shape (`##`/`###` headings,
// `**bold**`, `-` bullets, blank-line paragraphs), so 50 lines of hand-rolled
// parsing beats pulling in react-markdown + remark + rehype.
//
// Optional citation support: pass a non-empty `citations` array and any inline
// `[1]` / `[2]` tags in the text become clickable chips that fire
// `onCitationClick(n)`. With no citations array, `[n]` renders as plain text.

export type Citation = { id: number; source: string; snippet: string }

type Props = {
  text:             string
  citations?:       Citation[]
  onCitationClick?: (id: number) => void
}

export default function Markdown({ text, citations, onCitationClick }: Props) {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const nodes: ReactNode[] = []
  let bullets: string[] = []
  let paragraph: string[] = []

  const flushBullets = () => {
    if (!bullets.length) return
    nodes.push(
      <ul
        key={`ul-${nodes.length}`}
        className="list-disc ml-5 space-y-1 mb-2 text-[13px] leading-relaxed"
        style={{ color: 'inherit' }}
      >
        {bullets.map((b, i) => (
          <li key={i}>{renderInline(b, citations, onCitationClick)}</li>
        ))}
      </ul>,
    )
    bullets = []
  }
  const flushParagraph = () => {
    if (!paragraph.length) return
    nodes.push(
      <p
        key={`p-${nodes.length}`}
        className="text-[13px] leading-relaxed mb-2"
        style={{ color: 'inherit' }}
      >
        {renderInline(paragraph.join(' '), citations, onCitationClick)}
      </p>,
    )
    paragraph = []
  }
  const flushAll = () => { flushBullets(); flushParagraph() }

  for (const raw of lines) {
    const line = raw.trim()
    if (!line || /^-{3,}$/.test(line)) { flushAll(); continue }

    const h2 = line.match(/^##\s+(.+?)\s*$/)
    const h3 = line.match(/^###\s+(.+?)\s*$/)
    if (h2 || h3) {
      flushAll()
      const heading = (h2?.[1] ?? h3?.[1] ?? '').replace(/\*\*/g, '')
      const isTop = !!h2
      nodes.push(
        <h3
          key={`h-${nodes.length}`}
          className={
            isTop
              ? 'text-[12px] font-bold uppercase tracking-wider mt-3 mb-1.5'
              : 'text-[12px] font-semibold mt-2 mb-1'
          }
          style={{ color: isTop ? '#30D158' : 'rgba(235,235,245,0.85)' }}
        >
          {heading}
        </h3>,
      )
      continue
    }

    const bullet = line.match(/^[-*]\s+(.+)$/)
    if (bullet) { flushParagraph(); bullets.push(bullet[1]); continue }

    flushBullets()
    paragraph.push(line)
  }
  flushAll()

  return <div>{nodes}</div>
}

// Inline parser. Handles `**bold**` segments and, when citations are present,
// `[n]` citation chips. Order matters: scan for the next markup site at each
// position rather than splitting by one pattern first — otherwise `**foo [1]**`
// would lose the citation.
function renderInline(
  text:             string,
  citations?:       Citation[],
  onCitationClick?: (id: number) => void,
): ReactNode[] {
  const parts: ReactNode[] = []
  const citeIds = new Set((citations ?? []).map(c => c.id))
  const boldRe = /\*\*([^*]+)\*\*/g
  const citeRe = /\[(\d+)\]/g
  let i = 0
  let key = 0

  while (i < text.length) {
    boldRe.lastIndex = i
    citeRe.lastIndex = i
    const bm = boldRe.exec(text)
    const cm = citeRe.exec(text)

    // Pick the earlier match; null if neither.
    let next: { type: 'bold' | 'cite'; m: RegExpExecArray } | null = null
    if (bm && (!cm || bm.index <= cm.index)) next = { type: 'bold', m: bm }
    else if (cm)                              next = { type: 'cite', m: cm }

    if (!next) {
      parts.push(text.slice(i))
      break
    }
    if (next.m.index > i) parts.push(text.slice(i, next.m.index))

    if (next.type === 'bold') {
      parts.push(<strong key={key++} style={{ color: '#FFFFFF' }}>{next.m[1]}</strong>)
    } else {
      const n = Number(next.m[1])
      if (citations && citeIds.has(n)) {
        parts.push(
          <button
            key={key++}
            type="button"
            onClick={() => onCitationClick?.(n)}
            className="inline-flex items-center justify-center text-[10px] font-semibold mx-0.5 px-1.5 rounded-full align-baseline transition-colors"
            style={{
              background: 'rgba(10,132,255,0.18)',
              color: '#0A84FF',
              border: '1px solid rgba(10,132,255,0.35)',
              cursor: onCitationClick ? 'pointer' : 'default',
              minWidth: 18,
              lineHeight: '14px',
            }}
            title={`Source ${n}`}
          >
            {n}
          </button>,
        )
      } else {
        // Citation array missing or unknown id — render raw.
        parts.push(next.m[0])
      }
    }
    i = next.m.index + next.m[0].length
  }

  return parts
}
