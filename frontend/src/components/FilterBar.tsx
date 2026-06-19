import { useEffect, useRef, useState } from 'react'
import type { StatsFilters, TournamentOut } from '../types'

const POSITIONS = ['', 'FW', 'MF', 'DF', 'GK'] as const
const SORT_OPTIONS = [
  { label: 'Goals ↓', value: '-goals' },
  { label: 'Goals ↑', value: 'goals' },
  { label: 'Assists ↓', value: '-assists' },
  { label: 'Minutes ↓', value: '-minutes' },
  { label: 'Appearances ↓', value: '-appearances' },
  { label: 'Yellow cards ↓', value: '-yellow_cards' },
  { label: 'Red cards ↓', value: '-red_cards' },
]

interface Props {
  tournaments: TournamentOut[]
  filters: StatsFilters
  onChange: (f: StatsFilters) => void
}

export function FilterBar({ tournaments, filters, onChange }: Props) {
  const [teamInput, setTeamInput] = useState(filters.team ?? '')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  function set<K extends keyof StatsFilters>(key: K, value: StatsFilters[K]) {
    onChange({ ...filters, [key]: value })
  }

  function onTeamChange(value: string) {
    setTeamInput(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      set('team', value || undefined)
    }, 300)
  }

  useEffect(() => {
    setTeamInput(filters.team ?? '')
  }, [filters.team])

  return (
    <div className="flex flex-wrap gap-3 p-4 bg-white border-b border-gray-200">
      {/* Year */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
          Tournament
        </label>
        <select
          className="border border-gray-300 rounded px-3 py-1.5 text-sm bg-white"
          value={filters.year ?? ''}
          onChange={(e) =>
            set('year', e.target.value ? Number(e.target.value) : undefined)
          }
        >
          <option value="">All years</option>
          {[...tournaments].reverse().map((t) => (
            <option key={t.year} value={t.year}>
              {t.year} {t.host_country ? `· ${t.host_country}` : ''}
            </option>
          ))}
        </select>
      </div>

      {/* Position */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
          Position
        </label>
        <select
          className="border border-gray-300 rounded px-3 py-1.5 text-sm bg-white"
          value={filters.position ?? ''}
          onChange={(e) => set('position', e.target.value || undefined)}
        >
          {POSITIONS.map((p) => (
            <option key={p} value={p}>
              {p || 'All positions'}
            </option>
          ))}
        </select>
      </div>

      {/* Team */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
          Team
        </label>
        <input
          className="border border-gray-300 rounded px-3 py-1.5 text-sm w-40"
          placeholder="e.g. Brazil"
          value={teamInput}
          onChange={(e) => onTeamChange(e.target.value)}
        />
      </div>

      {/* Sort */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
          Sort by
        </label>
        <select
          className="border border-gray-300 rounded px-3 py-1.5 text-sm bg-white"
          value={filters.sort ?? '-goals'}
          onChange={(e) => set('sort', e.target.value)}
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {/* Min goals */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
          Min goals
        </label>
        <input
          type="number"
          min={0}
          className="border border-gray-300 rounded px-3 py-1.5 text-sm w-24"
          placeholder="0"
          value={filters.min_goals ?? ''}
          onChange={(e) =>
            set('min_goals', e.target.value ? Number(e.target.value) : undefined)
          }
        />
      </div>

      {/* Clear */}
      {(filters.team || filters.position || filters.min_goals || !filters.year) && (
        <div className="flex flex-col gap-1 justify-end">
          <button
            className="text-sm text-blue-600 hover:underline px-2 py-1.5"
            onClick={() =>
              onChange({ year: 2026, sort: filters.sort ?? '-goals' })
            }
          >
            Reset
          </button>
        </div>
      )}
    </div>
  )
}
