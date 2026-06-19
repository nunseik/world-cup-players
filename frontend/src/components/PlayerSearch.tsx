import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { PlayerOut } from '../types'

interface Props {
  onSelectPlayer: (player: PlayerOut) => void
}

export function PlayerSearch({ onSelectPlayer }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<PlayerOut[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (query.length < 2) {
      setResults([])
      setOpen(false)
      return
    }
    debounceRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        const page = await api.searchPlayers(query)
        setResults(page.items)
        setOpen(true)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 400)
  }, [query])

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  function select(player: PlayerOut) {
    onSelectPlayer(player)
    setQuery('')
    setOpen(false)
    setResults([])
  }

  return (
    <div ref={containerRef} className="relative flex flex-col gap-1">
      <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
        Player search
      </label>
      <div className="relative">
        <input
          className="border border-gray-300 rounded px-3 py-1.5 text-sm w-56 pr-8"
          placeholder="Search by name…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results.length > 0 && setOpen(true)}
        />
        {loading && (
          <span className="absolute right-2 top-2 text-gray-400 text-xs">…</span>
        )}
      </div>

      {open && results.length > 0 && (
        <ul className="absolute top-full mt-1 left-0 z-50 w-72 bg-white border border-gray-200 rounded shadow-lg max-h-64 overflow-y-auto">
          {results.map((p) => (
            <li key={p.id}>
              <button
                className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center justify-between gap-2"
                onClick={() => select(p)}
              >
                <span className="font-medium text-gray-800">{p.full_name}</span>
                {p.position && (
                  <span className="text-xs text-gray-500 shrink-0">{p.position}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      {open && query.length >= 2 && results.length === 0 && !loading && (
        <div className="absolute top-full mt-1 left-0 z-50 w-56 bg-white border border-gray-200 rounded shadow-lg px-3 py-2 text-sm text-gray-500">
          No players found
        </div>
      )}
    </div>
  )
}
