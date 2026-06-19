import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { PlayerStatOut, TournamentOut } from '../types'

// ─── Team metadata ───────────────────────────────────────────────────────────

const TEAM_META: Record<string, { color: string; flag: string; abbr: string }> = {
  'Argentina': { color: '#4aa3df', flag: '🇦🇷', abbr: 'ARG' },
  'Australia': { color: '#e0a82e', flag: '🇦🇺', abbr: 'AUS' },
  'Austria': { color: '#d13e3e', flag: '🇦🇹', abbr: 'AUT' },
  'Belgium': { color: '#e63946', flag: '🇧🇪', abbr: 'BEL' },
  'Bolivia': { color: '#0d6b3c', flag: '🇧🇴', abbr: 'BOL' },
  'Brazil': { color: '#1f9e57', flag: '🇧🇷', abbr: 'BRA' },
  'Bulgaria': { color: '#1f8045', flag: '🇧🇬', abbr: 'BUL' },
  'Cameroon': { color: '#1f8045', flag: '🇨🇲', abbr: 'CMR' },
  'Cameroun': { color: '#1f8045', flag: '🇨🇲', abbr: 'CMR' },
  'Canada': { color: '#d13e3e', flag: '🇨🇦', abbr: 'CAN' },
  'Chile': { color: '#d13e3e', flag: '🇨🇱', abbr: 'CHI' },
  'China': { color: '#d13e3e', flag: '🇨🇳', abbr: 'CHN' },
  'Colombia': { color: '#e0a82e', flag: '🇨🇴', abbr: 'COL' },
  'Costa Rica': { color: '#3554c9', flag: '🇨🇷', abbr: 'CRC' },
  'Croatia': { color: '#e63946', flag: '🇭🇷', abbr: 'CRO' },
  'Cuba': { color: '#d13e3e', flag: '🇨🇺', abbr: 'CUB' },
  'Czech Republic': { color: '#d13e3e', flag: '🇨🇿', abbr: 'CZE' },
  'Denmark': { color: '#c21e2e', flag: '🇩🇰', abbr: 'DEN' },
  'East Germany': { color: '#e0a82e', flag: '🇩🇪', abbr: 'GDR' },
  'Ecuador': { color: '#e0a82e', flag: '🇪🇨', abbr: 'ECU' },
  'Egypt': { color: '#d13e3e', flag: '🇪🇬', abbr: 'EGY' },
  'El Salvador': { color: '#003580', flag: '🇸🇻', abbr: 'SLV' },
  'England': { color: '#c0392b', flag: '🏴󠁧󠁢󠁥󠁮󠁧󠁿', abbr: 'ENG' },
  'France': { color: '#3554c9', flag: '🇫🇷', abbr: 'FRA' },
  'Germany': { color: '#e0a82e', flag: '🇩🇪', abbr: 'GER' },
  'Ghana': { color: '#cf9900', flag: '🇬🇭', abbr: 'GHA' },
  'Greece': { color: '#4aa3df', flag: '🇬🇷', abbr: 'GRE' },
  'Haiti': { color: '#003580', flag: '🇭🇹', abbr: 'HAI' },
  'Honduras': { color: '#4aa3df', flag: '🇭🇳', abbr: 'HON' },
  'Hungary': { color: '#d13e3e', flag: '🇭🇺', abbr: 'HUN' },
  'Indonesia': { color: '#d13e3e', flag: '🇮🇩', abbr: 'IDN' },
  'Iran': { color: '#1f8045', flag: '🇮🇷', abbr: 'IRN' },
  'Iraq': { color: '#1f8045', flag: '🇮🇶', abbr: 'IRQ' },
  'Ireland': { color: '#1f8045', flag: '🇮🇪', abbr: 'IRL' },
  'Italy': { color: '#1a6bb5', flag: '🇮🇹', abbr: 'ITA' },
  "Ivory Coast": { color: '#e0a82e', flag: '🇨🇮', abbr: 'CIV' },
  "Côte d'Ivoire": { color: '#e0a82e', flag: '🇨🇮', abbr: 'CIV' },
  'Jamaica': { color: '#e0a82e', flag: '🇯🇲', abbr: 'JAM' },
  'Japan': { color: '#003580', flag: '🇯🇵', abbr: 'JPN' },
  'Kuwait': { color: '#1f8045', flag: '🇰🇼', abbr: 'KUW' },
  'Mexico': { color: '#1f8045', flag: '🇲🇽', abbr: 'MEX' },
  'Morocco': { color: '#c1272d', flag: '🇲🇦', abbr: 'MAR' },
  'Netherlands': { color: '#e65c00', flag: '🇳🇱', abbr: 'NED' },
  'New Zealand': { color: '#1a3a6b', flag: '🇳🇿', abbr: 'NZL' },
  'Nigeria': { color: '#008751', flag: '🇳🇬', abbr: 'NGA' },
  'North Korea': { color: '#d13e3e', flag: '🇰🇵', abbr: 'PRK' },
  'Northern Ireland': { color: '#4aa3df', flag: '🏴󠁧󠁢󠁮󠁩󠁲󠁿', abbr: 'NIR' },
  'Norway': { color: '#d13e3e', flag: '🇳🇴', abbr: 'NOR' },
  'Panama': { color: '#d13e3e', flag: '🇵🇦', abbr: 'PAN' },
  'Paraguay': { color: '#d13e3e', flag: '🇵🇾', abbr: 'PAR' },
  'Peru': { color: '#d13e3e', flag: '🇵🇪', abbr: 'PER' },
  'Poland': { color: '#d13e3e', flag: '🇵🇱', abbr: 'POL' },
  'Portugal': { color: '#d13e3e', flag: '🇵🇹', abbr: 'POR' },
  'Qatar': { color: '#7a1528', flag: '🇶🇦', abbr: 'QAT' },
  'Republic of Ireland': { color: '#1f8045', flag: '🇮🇪', abbr: 'IRL' },
  'Romania': { color: '#e0a82e', flag: '🇷🇴', abbr: 'ROU' },
  'Russia': { color: '#d13e3e', flag: '🇷🇺', abbr: 'RUS' },
  'Saudi Arabia': { color: '#1f8045', flag: '🇸🇦', abbr: 'KSA' },
  'Scotland': { color: '#4aa3df', flag: '🏴󠁧󠁢󠁳󠁣󠁴󠁿', abbr: 'SCO' },
  'Senegal': { color: '#1f9e57', flag: '🇸🇳', abbr: 'SEN' },
  'Serbia': { color: '#d13e3e', flag: '🇷🇸', abbr: 'SRB' },
  'Slovakia': { color: '#4aa3df', flag: '🇸🇰', abbr: 'SVK' },
  'Slovenia': { color: '#4aa3df', flag: '🇸🇮', abbr: 'SVN' },
  'South Africa': { color: '#1f8045', flag: '🇿🇦', abbr: 'RSA' },
  'South Korea': { color: '#d13e3e', flag: '🇰🇷', abbr: 'KOR' },
  'Soviet Union': { color: '#d13e3e', flag: '🇷🇺', abbr: 'URS' },
  'Spain': { color: '#c0392b', flag: '🇪🇸', abbr: 'ESP' },
  'Sweden': { color: '#e0a82e', flag: '🇸🇪', abbr: 'SWE' },
  'Switzerland': { color: '#d13e3e', flag: '🇨🇭', abbr: 'SUI' },
  'Togo': { color: '#1f8045', flag: '🇹🇬', abbr: 'TOG' },
  'Trinidad and Tobago': { color: '#d13e3e', flag: '🇹🇹', abbr: 'TRI' },
  'Tunisia': { color: '#d13e3e', flag: '🇹🇳', abbr: 'TUN' },
  'Turkey': { color: '#d13e3e', flag: '🇹🇷', abbr: 'TUR' },
  'Ukraine': { color: '#e0a82e', flag: '🇺🇦', abbr: 'UKR' },
  'United Arab Emirates': { color: '#1f8045', flag: '🇦🇪', abbr: 'UAE' },
  'United States': { color: '#1a3a6b', flag: '🇺🇸', abbr: 'USA' },
  'Uruguay': { color: '#4a90d9', flag: '🇺🇾', abbr: 'URU' },
  'USA': { color: '#1a3a6b', flag: '🇺🇸', abbr: 'USA' },
  'Wales': { color: '#d13e3e', flag: '🏴󠁧󠁢󠁷󠁬󠁳󠁿', abbr: 'WAL' },
  'West Germany': { color: '#e0a82e', flag: '🇩🇪', abbr: 'FRG' },
  'Yugoslavia': { color: '#003580', flag: '🇷🇸', abbr: 'YUG' },
  'Zaire': { color: '#1f8045', flag: '🇨🇩', abbr: 'ZAI' },
  'Zaïre': { color: '#1f8045', flag: '🇨🇩', abbr: 'ZAI' },
}

function hashColor(name: string): string {
  let h = 0
  for (let i = 0; i < name.length; i++) {
    h = (h << 5) - h + name.charCodeAt(i)
    h = h & h
  }
  return `hsl(${Math.abs(h) % 360}, 55%, 45%)`
}

function getTeamMeta(name: string | null) {
  if (!name) return { color: '#6b7280', flag: '🏴', abbr: '???' }
  return TEAM_META[name] ?? {
    color: hashColor(name),
    flag: '🏴',
    abbr: name.substring(0, 3).toUpperCase(),
  }
}

function getAvatar(position: string | null): string {
  if (position === 'GK') return '🧤'
  if (position === 'FW') return '⚽'
  if (position === 'MF') return '🎯'
  if (position === 'DF') return '🛡️'
  return '🧑'
}

// ─── Types ───────────────────────────────────────────────────────────────────

type TeamMeta = ReturnType<typeof getTeamMeta>

// ─── StickerCard ─────────────────────────────────────────────────────────────

function StickerCard({
  stat,
  teamMeta,
  collected,
  flipped,
  isDuplicate,
  onFlip,
  onCollect,
  onToggleDup,
  onZoom,
}: {
  stat: PlayerStatOut
  teamMeta: TeamMeta
  collected: boolean
  flipped: boolean
  isDuplicate: boolean
  onFlip: () => void
  onCollect: () => void
  onToggleDup: (e: React.MouseEvent) => void
  onZoom: (e: React.MouseEvent) => void
}) {
  function handleClick() {
    if (!collected) onCollect()
    else onFlip()
  }

  const faceStyle: React.CSSProperties = {
    position: 'absolute',
    inset: 0,
    backfaceVisibility: 'hidden',
    WebkitBackfaceVisibility: 'hidden' as React.CSSProperties['WebkitBackfaceVisibility'],
    borderRadius: 13,
    boxShadow: '0 6px 18px rgba(0,0,0,.35)',
    overflow: 'hidden',
  }

  return (
    <div
      onClick={handleClick}
      style={{ position: 'relative', aspectRatio: '5/7', cursor: 'pointer', perspective: '1000px' }}
    >
      <div style={{
        position: 'relative', width: '100%', height: '100%',
        transition: 'transform .5s cubic-bezier(.4,.2,.2,1)',
        transformStyle: 'preserve-3d',
        transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
      }}>

        {/* FRONT */}
        <div style={faceStyle}>
          <div style={{ position: 'absolute', inset: 0, borderRadius: 13, background: '#fff' }} />

          {/* Team banner */}
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, height: 46,
            background: teamMeta.color, borderRadius: '13px 13px 0 0',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '0 12px',
          }}>
            <span style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 10, color: 'rgba(255,255,255,.9)', letterSpacing: 1 }}>
              {teamMeta.flag} {teamMeta.abbr}
            </span>
            {stat.jersey_number != null && (
              <span style={{ fontFamily: 'Poppins,sans-serif', fontWeight: 800, fontSize: 20, color: '#fff', textShadow: '0 1px 2px rgba(0,0,0,.3)' }}>
                #{stat.jersey_number}
              </span>
            )}
          </div>

          {/* Photo placeholder */}
          <div style={{
            position: 'absolute', top: 46, left: 8, right: 8, bottom: 54,
            borderRadius: 8,
            background: 'repeating-linear-gradient(135deg,rgba(0,0,0,.04) 0 8px,rgba(0,0,0,.08) 8px 16px)',
            display: 'flex', alignItems: 'flex-end', justifyContent: 'center', overflow: 'hidden',
          }}>
            <span style={{ fontSize: 64, opacity: .85, marginBottom: 6 }}>{getAvatar(stat.position)}</span>
            <span style={{ position: 'absolute', top: 8, left: 8, fontFamily: "'Roboto Mono',monospace", fontSize: 8, color: 'rgba(0,0,0,.3)', letterSpacing: .5 }}>PHOTO</span>
          </div>

          {/* Name / position */}
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 54, padding: '0 12px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div style={{ fontFamily: 'Poppins,sans-serif', fontWeight: 700, fontSize: 13, color: '#0e1430', lineHeight: 1.05, letterSpacing: '-.2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {stat.player_name}
            </div>
            <div style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 9, color: '#6b7280', letterSpacing: 1, marginTop: 3, textTransform: 'uppercase' }}>
              {stat.position ?? '—'} · {stat.year}
            </div>
          </div>

          {/* Duplicate star */}
          {isDuplicate && (
            <div style={{ position: 'absolute', top: 52, right: 8, width: 26, height: 26, borderRadius: '50%', background: '#f5c542', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, boxShadow: '0 2px 6px rgba(0,0,0,.3)', zIndex: 3 }}>⭐</div>
          )}

          {/* Locked overlay */}
          {!collected && (
            <div style={{ position: 'absolute', inset: 0, borderRadius: 13, background: 'rgba(14,20,48,.76)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8, zIndex: 4 }}>
              <span style={{ fontSize: 30 }}>🔒</span>
              <span style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 9, color: 'rgba(255,255,255,.7)', letterSpacing: 1.5 }}>CLICK TO COLLECT</span>
            </div>
          )}
        </div>

        {/* BACK */}
        <div style={{ ...faceStyle, transform: 'rotateY(180deg)' }}>
          <div style={{ position: 'absolute', inset: 0, borderRadius: 13, background: 'linear-gradient(160deg,#141c44,#0b1029)' }} />

          {/* Back header */}
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 40, background: teamMeta.color, borderRadius: '13px 13px 0 0', display: 'flex', alignItems: 'center', padding: '0 12px' }}>
            <span style={{ fontFamily: 'Poppins,sans-serif', fontWeight: 700, fontSize: 11, color: '#fff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{stat.player_name}</span>
          </div>

          {/* Stats */}
          <div style={{ position: 'absolute', top: 48, left: 10, right: 10, display: 'flex', flexDirection: 'column', gap: 5 }}>
            {[
              { label: 'Goals', value: stat.goals, color: '#f5c542' },
              { label: 'Assists', value: stat.assists, color: '#3ad29f' },
              { label: 'Apps', value: stat.appearances, color: '#fff' },
              { label: 'Minutes', value: stat.minutes_played, color: '#fff' },
              { label: 'Yellow', value: stat.yellow_cards, color: '#e0a82e' },
            ].map(s => (
              <div key={s.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '5px 9px', borderRadius: 7, background: 'rgba(255,255,255,.06)' }}>
                <span style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 9, color: 'rgba(255,255,255,.55)', letterSpacing: 1, textTransform: 'uppercase' }}>{s.label}</span>
                <span style={{ fontFamily: 'Poppins,sans-serif', fontWeight: 700, fontSize: 14, color: s.color }}>{s.value ?? '—'}</span>
              </div>
            ))}
          </div>

          {/* Back buttons */}
          <div style={{ position: 'absolute', bottom: 10, left: 10, right: 10, display: 'flex', gap: 7 }}>
            <button
              onClick={onToggleDup}
              style={{ flex: 1, padding: '7px 0', borderRadius: 7, border: 'none', fontFamily: 'Poppins,sans-serif', fontWeight: 700, fontSize: 10, cursor: 'pointer', background: isDuplicate ? '#f5c542' : 'rgba(255,255,255,.12)', color: isDuplicate ? '#0e1430' : '#fff' }}
            >
              {isDuplicate ? '★ DUPLICATE' : 'MARK DUPE'}
            </button>
            <button
              onClick={onZoom}
              style={{ padding: '7px 11px', borderRadius: 7, border: 'none', background: 'rgba(255,255,255,.12)', color: '#fff', fontFamily: 'Poppins,sans-serif', fontWeight: 700, fontSize: 10, cursor: 'pointer' }}
            >⤢</button>
          </div>
        </div>

      </div>
    </div>
  )
}

// ─── AlbumPage ────────────────────────────────────────────────────────────────

interface Props {
  initialYear: number
  tournaments: TournamentOut[]
}

export function AlbumPage({ initialYear, tournaments }: Props) {
  const [year, setYear] = useState(initialYear)
  const [stats, setStats] = useState<PlayerStatOut[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [collected, setCollected] = useState<Record<string, boolean>>({})
  const [duplicates, setDuplicates] = useState<Record<string, boolean>>({})
  const [flipped, setFlipped] = useState<Record<string, boolean>>({})
  const [zoomId, setZoomId] = useState<number | null>(null)
  const [shareToast, setShareToast] = useState(false)
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Load persistence from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('wc_album_v1')
      if (saved) {
        const { c, d } = JSON.parse(saved)
        setCollected(c || {})
        setDuplicates(d || {})
      }
    } catch { /* ignore */ }
  }, [])

  // Persist collected / duplicates
  useEffect(() => {
    try {
      localStorage.setItem('wc_album_v1', JSON.stringify({ c: collected, d: duplicates }))
    } catch { /* ignore */ }
  }, [collected, duplicates])

  // Fetch all stats for the year (paginated, API max 200/page)
  useEffect(() => {
    setLoading(true)
    setFlipped({})
    const PAGE = 200
    api.getStats({ year, sort: '-goals' }, 0, PAGE).then(async first => {
      const pages = Math.ceil(first.total / PAGE)
      if (pages <= 1) { setStats(first.items); setLoading(false); return }
      const rest = await Promise.all(
        Array.from({ length: pages - 1 }, (_, i) =>
          api.getStats({ year, sort: '-goals' }, i + 1, PAGE).then(p => p.items)
        )
      )
      setStats([...first.items, ...rest.flat()])
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [year])

  const key = (s: PlayerStatOut) => `${s.player_id}_${s.year}`

  const isCollected = useCallback((s: PlayerStatOut) => !!collected[key(s)], [collected])
  const isDuplicate = useCallback((s: PlayerStatOut) => !!duplicates[key(s)], [duplicates])
  const isFlipped  = useCallback((s: PlayerStatOut) => !!flipped[key(s)], [flipped])

  function toggleCollect(s: PlayerStatOut) {
    const k = key(s)
    const wasCollected = !!collected[k]
    setCollected(c => ({ ...c, [k]: !wasCollected }))
    if (wasCollected) setFlipped(f => { const n = { ...f }; delete n[k]; return n })
  }

  function toggleFlip(s: PlayerStatOut) {
    const k = key(s)
    setFlipped(f => ({ ...f, [k]: !f[k] }))
  }

  function toggleDup(s: PlayerStatOut) {
    const k = key(s)
    setDuplicates(d => ({ ...d, [k]: !d[k] }))
  }

  function collectAll() {
    const updates: Record<string, boolean> = {}
    for (const s of stats) updates[key(s)] = true
    setCollected(c => ({ ...c, ...updates }))
  }

  function share() {
    navigator.clipboard.writeText(window.location.href).catch(() => {})
    setShareToast(true)
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
    toastTimerRef.current = setTimeout(() => setShareToast(false), 2200)
  }

  // Filter + group by team
  const q = query.toLowerCase()
  const visible = stats.filter(s =>
    !q || s.player_name.toLowerCase().includes(q) || (s.team_name ?? '').toLowerCase().includes(q)
  )

  const teamMap = new Map<string, PlayerStatOut[]>()
  for (const s of visible) {
    const t = s.team_name ?? 'Unknown'
    if (!teamMap.has(t)) teamMap.set(t, [])
    teamMap.get(t)!.push(s)
  }
  const teams = [...teamMap.entries()].sort((a, b) => a[0].localeCompare(b[0]))

  const total = stats.length
  const collectedCount = stats.filter(s => isCollected(s)).length
  const pct = total ? Math.round((collectedCount / total) * 100) : 0

  const zoomedStat = zoomId != null ? stats.find(s => s.player_id === zoomId) ?? null : null

  return (
    <div style={{ minHeight: '100vh', background: '#0e1430', fontFamily: 'Roboto,system-ui,sans-serif', color: '#0e1430' }}>

      {/* ── Header ── */}
      <header style={{ position: 'sticky', top: 0, zIndex: 30, background: 'linear-gradient(180deg,#141c44,#0e1430)', borderBottom: '3px solid #f5c542', padding: '18px 28px', display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', boxShadow: '0 6px 24px rgba(0,0,0,.4)' }}>

        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ width: 46, height: 46, borderRadius: 12, background: '#f5c542', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26, boxShadow: '0 4px 0 #c79a1f' }}>⚽</div>
          <div>
            <div style={{ fontFamily: 'Poppins,sans-serif', fontWeight: 800, fontSize: 21, color: '#fff', letterSpacing: '-.3px', lineHeight: 1 }}>PANINI FAN ALBUM</div>
            <div style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 11, color: '#f5c542', letterSpacing: 2, marginTop: 4 }}>FAN EDITION · 1970–2026</div>
          </div>
        </div>

        {/* Search */}
        <div style={{ position: 'relative', flex: 1, minWidth: 200, maxWidth: 400 }}>
          <span style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', fontSize: 14, opacity: .5, pointerEvents: 'none' }}>🔍</span>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search players or nations…"
            style={{ width: '100%', padding: '11px 14px 11px 40px', borderRadius: 10, border: 'none', background: 'rgba(255,255,255,.1)', color: '#fff', fontSize: 14, fontFamily: 'Roboto,sans-serif', outline: 'none', boxSizing: 'border-box' }}
          />
        </div>

        {/* Year picker */}
        <select
          value={year}
          onChange={e => setYear(Number(e.target.value))}
          style={{ padding: '10px 14px', borderRadius: 10, border: 'none', background: 'rgba(255,255,255,.12)', color: '#fff', fontFamily: 'Poppins,sans-serif', fontWeight: 700, fontSize: 14, cursor: 'pointer', outline: 'none' }}
        >
          {[...tournaments].reverse().map(t => (
            <option key={t.year} value={t.year} style={{ background: '#141c44' }}>
              {t.year}{t.host_country ? ` · ${t.host_country}` : ''}
            </option>
          ))}
        </select>

        {/* Counter + actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginLeft: 'auto' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontFamily: 'Poppins,sans-serif', fontWeight: 800, fontSize: 22, color: '#f5c542', lineHeight: 1 }}>
              {collectedCount}<span style={{ color: 'rgba(255,255,255,.4)', fontSize: 15, fontWeight: 600 }}>/{total}</span>
            </div>
            <div style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 10, color: 'rgba(255,255,255,.55)', letterSpacing: 1.5, marginTop: 3 }}>STICKERS</div>
          </div>
          <button onClick={collectAll} style={{ padding: '10px 16px', borderRadius: 10, border: 'none', background: 'rgba(255,255,255,.12)', color: '#fff', fontFamily: 'Poppins,sans-serif', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}>Collect all</button>
          <button onClick={share} style={{ padding: '10px 18px', borderRadius: 10, border: 'none', background: '#f5c542', color: '#0e1430', fontFamily: 'Poppins,sans-serif', fontWeight: 700, fontSize: 13, cursor: 'pointer', boxShadow: '0 4px 0 #c79a1f' }}>Share album</button>
        </div>
      </header>

      {/* ── Progress bar ── */}
      <div style={{ background: '#0b1029', padding: '14px 28px', display: 'flex', alignItems: 'center', gap: 16, borderBottom: '1px solid rgba(255,255,255,.06)' }}>
        <div style={{ flex: 1, height: 10, borderRadius: 99, background: 'rgba(255,255,255,.08)', overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${pct}%`, background: 'linear-gradient(90deg,#3ad29f,#f5c542)', borderRadius: 99, transition: 'width .5s ease' }} />
        </div>
        <div style={{ fontFamily: 'Poppins,sans-serif', fontWeight: 700, fontSize: 13, color: '#3ad29f', minWidth: 54, textAlign: 'right' }}>{pct}%</div>
      </div>

      {/* ── Album body ── */}
      <main style={{ maxWidth: 1180, margin: '0 auto', padding: '34px 28px 80px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '70px 0', color: 'rgba(255,255,255,.5)' }}>
            <div style={{ fontSize: 46, marginBottom: 14 }}>⏳</div>
            <div style={{ fontFamily: 'Poppins,sans-serif', fontWeight: 700, fontSize: 17, color: '#fff' }}>Loading stickers…</div>
          </div>
        ) : teams.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '70px 0', color: 'rgba(255,255,255,.5)' }}>
            <div style={{ fontSize: 46, marginBottom: 14 }}>🗂️</div>
            <div style={{ fontFamily: 'Poppins,sans-serif', fontWeight: 700, fontSize: 17, color: '#fff' }}>
              {query ? `No stickers match "${query}"` : 'No players found'}
            </div>
            {query && <div style={{ fontSize: 13, marginTop: 6 }}>Try a different player or nation.</div>}
          </div>
        ) : (
          teams.map(([teamName, players]) => {
            const tm = getTeamMeta(teamName)
            const tCollected = players.filter(p => isCollected(p)).length
            return (
              <section key={teamName} style={{ marginBottom: 42 }}>
                {/* Team header */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
                  <div style={{ width: 8, height: 34, borderRadius: 4, background: tm.color }} />
                  <div style={{ width: 44, height: 44, borderRadius: 10, background: tm.color, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, boxShadow: `0 4px 12px ${tm.color}66` }}>
                    {tm.flag}
                  </div>
                  <div>
                    <div style={{ fontFamily: 'Poppins,sans-serif', fontWeight: 800, fontSize: 20, color: '#fff', letterSpacing: '-.3px', lineHeight: 1 }}>{teamName}</div>
                    <div style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 11, color: 'rgba(255,255,255,.5)', letterSpacing: 1.5, marginTop: 4 }}>{players.length} STICKERS</div>
                  </div>
                  <div style={{ marginLeft: 'auto', padding: '7px 14px', borderRadius: 99, background: 'rgba(255,255,255,.05)', border: `1.5px solid ${tm.color}`, fontFamily: 'Poppins,sans-serif', fontWeight: 700, fontSize: 13, color: tm.color }}>
                    {tCollected}/{players.length}
                  </div>
                </div>

                {/* Sticker grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(160px,1fr))', gap: 18 }}>
                  {players.map(stat => (
                    <StickerCard
                      key={stat.player_id}
                      stat={stat}
                      teamMeta={tm}
                      collected={isCollected(stat)}
                      flipped={isFlipped(stat)}
                      isDuplicate={isDuplicate(stat)}
                      onFlip={() => toggleFlip(stat)}
                      onCollect={() => toggleCollect(stat)}
                      onToggleDup={e => { e.stopPropagation(); toggleDup(stat) }}
                      onZoom={e => { e.stopPropagation(); setZoomId(stat.player_id) }}
                    />
                  ))}
                </div>
              </section>
            )
          })
        )}
      </main>

      {/* ── Zoom modal ── */}
      {zoomedStat && (() => {
        const tm = getTeamMeta(zoomedStat.team_name)
        return (
          <div
            onClick={() => setZoomId(null)}
            style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(8,11,28,.86)', backdropFilter: 'blur(6px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}
          >
            <div style={{ animation: 'wc-pop .25s ease', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
              <div style={{ position: 'relative', width: 300, height: 418, borderRadius: 20, overflow: 'hidden', boxShadow: '0 30px 80px rgba(0,0,0,.6)', background: '#fff' }}>
                {/* Coloured top half */}
                <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '40%', overflow: 'hidden' }}>
                  <div style={{ position: 'absolute', inset: 0, background: tm.color }} />
                  <div style={{ position: 'absolute', top: '-40%', left: 0, width: '60%', height: '180%', background: 'linear-gradient(rgba(255,255,255,.35),transparent)', animation: 'wc-shine 2.5s linear infinite' }} />
                </div>
                {/* Flag + number */}
                <div style={{ position: 'absolute', top: 16, left: 16, right: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', zIndex: 2 }}>
                  <span style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 12, color: '#fff', letterSpacing: 1 }}>{tm.flag} {tm.abbr}</span>
                  {zoomedStat.jersey_number != null && (
                    <span style={{ fontFamily: 'Poppins,sans-serif', fontWeight: 800, fontSize: 34, color: '#fff', textShadow: '0 2px 4px rgba(0,0,0,.3)' }}>#{zoomedStat.jersey_number}</span>
                  )}
                </div>
                {/* Large avatar */}
                <div style={{ position: 'absolute', top: '18%', left: 0, right: 0, display: 'flex', justifyContent: 'center', zIndex: 2 }}>
                  <span style={{ fontSize: 120 }}>{getAvatar(zoomedStat.position)}</span>
                </div>
                {/* Info panel */}
                <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '54%', background: '#fff', borderRadius: '20px 20px 0 0', padding: '22px 20px' }}>
                  <div style={{ fontFamily: 'Poppins,sans-serif', fontWeight: 800, fontSize: 22, color: '#0e1430', letterSpacing: '-.4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {zoomedStat.player_name}
                  </div>
                  <div style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 10, color: '#6b7280', letterSpacing: 1.5, margin: '5px 0 14px', textTransform: 'uppercase' }}>
                    {zoomedStat.position ?? '—'} · {zoomedStat.team_name} · {zoomedStat.year}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9 }}>
                    {[
                      { label: 'Goals', value: zoomedStat.goals, color: '#f5c542' },
                      { label: 'Assists', value: zoomedStat.assists, color: '#3ad29f' },
                      { label: 'Apps', value: zoomedStat.appearances, color: '#0e1430' },
                      { label: 'Minutes', value: zoomedStat.minutes_played, color: '#0e1430' },
                      { label: 'Yellow', value: zoomedStat.yellow_cards, color: '#e0a82e' },
                      { label: 'Red', value: zoomedStat.red_cards, color: '#e0556b' },
                    ].map(s => (
                      <div key={s.label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '9px 0', borderRadius: 9, background: '#f3f4f8' }}>
                        <span style={{ fontFamily: 'Poppins,sans-serif', fontWeight: 800, fontSize: 20, color: s.color }}>{s.value ?? '—'}</span>
                        <span style={{ fontFamily: "'Roboto Mono',monospace", fontSize: 8, color: '#9099aa', letterSpacing: 1, marginTop: 2, textTransform: 'uppercase' }}>{s.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <button
                onClick={() => setZoomId(null)}
                style={{ marginTop: 18, padding: '10px 26px', borderRadius: 99, border: 'none', background: 'rgba(255,255,255,.15)', color: '#fff', fontFamily: 'Poppins,sans-serif', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}
              >Close ✕</button>
            </div>
          </div>
        )
      })()}

      {/* ── Share toast ── */}
      {shareToast && (
        <div style={{ position: 'fixed', bottom: 26, left: '50%', transform: 'translateX(-50%)', zIndex: 70, background: '#3ad29f', color: '#06281d', padding: '14px 24px', borderRadius: 12, fontFamily: 'Poppins,sans-serif', fontWeight: 700, fontSize: 14, boxShadow: '0 12px 30px rgba(0,0,0,.4)', animation: 'wc-pop .2s ease' }}>
          🔗 Album link copied to clipboard!
        </div>
      )}

    </div>
  )
}
