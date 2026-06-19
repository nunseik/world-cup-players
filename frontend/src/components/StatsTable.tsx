import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Page, PlayerStatOut, StatsFilters } from '../types'
import { PlayerRow } from './PlayerRow'

const PAGE_SIZE = 50

interface Props {
  filters: StatsFilters
  selectedPlayerId: number | null
  onSelectPlayer: (id: number, name: string) => void
}

export function StatsTable({ filters, selectedPlayerId, onSelectPlayer }: Props) {
  const [data, setData] = useState<Page<PlayerStatOut> | null>(null)
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const prevFiltersRef = useRef<StatsFilters | null>(null)

  useEffect(() => {
    if (prevFiltersRef.current !== null) {
      setPage(0)
    }
    prevFiltersRef.current = filters
  }, [filters])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .getStats(filters, page, PAGE_SIZE)
      .then((result) => {
        if (!cancelled) setData(result)
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
  }, [filters, page])

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Table container */}
      <div className="flex-1 overflow-auto relative">
        {loading && (
          <div className="absolute inset-0 bg-white/60 flex items-center justify-center z-10">
            <span className="text-sm text-gray-500">Loading…</span>
          </div>
        )}

        {error && (
          <div className="p-8 text-center text-red-600 text-sm">{error}</div>
        )}

        {!error && (
          <table className="w-full text-left border-collapse">
            <thead className="bg-gray-50 border-b border-gray-200 sticky top-0">
              <tr>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Player</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Team</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Year</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-center">Goals</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-center">Assists</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-center">Apps</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-center">Min</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-center">YC</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-center">RC</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((stat) => (
                <PlayerRow
                  key={`${stat.player_id}-${stat.year}`}
                  stat={stat}
                  selected={selectedPlayerId === stat.player_id}
                  onClick={() => onSelectPlayer(stat.player_id, stat.player_name)}
                />
              ))}
              {data?.items.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-gray-400 text-sm">
                    No results
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {data && totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 bg-white shrink-0">
          <span className="text-sm text-gray-500">
            {data.total.toLocaleString()} players · page {page + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
              className="px-3 py-1 text-sm border border-gray-300 rounded disabled:opacity-40 hover:bg-gray-50"
            >
              ← Prev
            </button>
            <button
              disabled={page >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1 text-sm border border-gray-300 rounded disabled:opacity-40 hover:bg-gray-50"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
