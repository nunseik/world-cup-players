import { useEffect, useState } from 'react'
import { api } from '../api'
import type { CareerAggregateOut, PlayerStatOut } from '../types'
import { fmt, fmtMinutes } from '../utils/fmt'

interface Props {
  playerId: number | null
  playerName: string | null
  onClose: () => void
}

function Skeleton() {
  return (
    <div className="space-y-2 animate-pulse">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="h-4 bg-gray-200 rounded w-full" />
      ))}
    </div>
  )
}

export function CareerPanel({ playerId, playerName, onClose }: Props) {
  const [career, setCareer] = useState<CareerAggregateOut | null>(null)
  const [statRows, setStatRows] = useState<PlayerStatOut[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (playerId == null) {
      setCareer(null)
      setStatRows([])
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([api.getCareer(playerId), api.getPlayerStats(playerId)])
      .then(([c, s]) => {
        if (cancelled) return
        setCareer(c)
        setStatRows(s.items)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [playerId])

  if (playerId == null) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/20 z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed inset-y-0 right-0 z-50 w-80 bg-white shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 shrink-0">
          <div>
            <h2 className="font-semibold text-gray-900 text-base leading-tight">
              {playerName ?? 'Player'}
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">Career overview</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl font-light leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {error && <p className="text-red-600 text-sm">{error}</p>}

          {loading ? (
            <Skeleton />
          ) : (
            <>
              {/* Career totals */}
              {career && (
                <section>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                    Career totals
                  </h3>
                  <div className="grid grid-cols-2 gap-3">
                    <Stat label="World Cups" value={String(career.tournaments_played)} />
                    <Stat label="Goals" value={String(career.total_goals)} accent />
                    <Stat label="Assists" value={String(career.total_assists)} />
                    <Stat label="Minutes" value={fmtMinutes(career.total_minutes)} />
                    <Stat label="Yellow cards" value={String(career.total_yellow_cards)} />
                    <Stat label="Red cards" value={String(career.total_red_cards)} />
                  </div>
                </section>
              )}

              {/* Per-tournament breakdown */}
              {statRows.length > 0 && (
                <section>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                    By tournament
                  </h3>
                  <div className="space-y-2">
                    {statRows.map((s) => (
                      <div
                        key={s.year}
                        className="bg-gray-50 rounded p-3 text-sm"
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="font-semibold text-gray-800">{s.year}</span>
                          <span className="text-xs text-gray-500">{s.team_name}</span>
                        </div>
                        <div className="flex gap-4 text-gray-600 flex-wrap">
                          <span>⚽ {fmt(s.goals)}</span>
                          <span>🎯 {fmt(s.assists)}</span>
                          <span>▶ {fmt(s.appearances)}</span>
                          {s.minutes_played != null && (
                            <span>{fmtMinutes(s.minutes_played)}</span>
                          )}
                          {(s.yellow_cards != null && s.yellow_cards > 0) && (
                            <span className="text-yellow-600">🟨 {s.yellow_cards}</span>
                          )}
                          {(s.red_cards != null && s.red_cards > 0) && (
                            <span className="text-red-600">🟥 {s.red_cards}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </>
  )
}

function Stat({
  label,
  value,
  accent = false,
}: {
  label: string
  value: string
  accent?: boolean
}) {
  return (
    <div className="bg-gray-50 rounded p-2.5">
      <div className="text-xs text-gray-500 mb-0.5">{label}</div>
      <div className={`text-lg font-semibold ${accent ? 'text-green-700' : 'text-gray-900'}`}>
        {value}
      </div>
    </div>
  )
}
