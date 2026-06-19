import { useEffect, useState } from 'react'
import { api } from './api'
import { AlbumPage } from './components/AlbumPage'
import { CareerPanel } from './components/CareerPanel'
import { FilterBar } from './components/FilterBar'
import { PlayerSearch } from './components/PlayerSearch'
import { StatsTable } from './components/StatsTable'
import type { PlayerOut, StatsFilters, TournamentOut } from './types'

type View = 'table' | 'album'

export default function App() {
  const [view, setView] = useState<View>('table')
  const [tournaments, setTournaments] = useState<TournamentOut[]>([])
  const [filters, setFilters] = useState<StatsFilters>({
    year: 2026,
    sort: '-goals',
  })
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null)
  const [selectedPlayerName, setSelectedPlayerName] = useState<string | null>(null)

  useEffect(() => {
    api.getTournaments().then((page) => setTournaments(page.items)).catch(() => {})
  }, [])

  function handleSelectPlayer(id: number, name: string) {
    setSelectedPlayerId(id)
    setSelectedPlayerName(name)
  }

  function handleSearchSelect(player: PlayerOut) {
    setSelectedPlayerId(player.id)
    setSelectedPlayerName(player.full_name)
    setFilters((f) => ({ sort: f.sort, player_id: player.id }))
  }

  function handleClosePanel() {
    setSelectedPlayerId(null)
    setSelectedPlayerName(null)
    setFilters((f) => {
      const { player_id: _, ...rest } = f
      return { ...rest, year: rest.year ?? 2026 }
    })
  }

  function handleFilterChange(f: StatsFilters) {
    setSelectedPlayerId(null)
    setSelectedPlayerName(null)
    setFilters({ ...f, player_id: undefined })
  }

  const currentTournament = tournaments.find((t) => t.year === filters.year)

  if (view === 'album') {
    return (
      <div>
        {/* Album view toggle */}
        <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 50 }}>
          <button
            onClick={() => setView('table')}
            style={{ padding: '12px 20px', borderRadius: 99, border: 'none', background: '#f5c542', color: '#0e1430', fontFamily: 'Poppins,sans-serif', fontWeight: 700, fontSize: 13, cursor: 'pointer', boxShadow: '0 4px 16px rgba(0,0,0,.35)' }}
          >
            📊 Stats table
          </button>
        </div>
        <AlbumPage initialYear={filters.year ?? 2026} tournaments={tournaments} />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 shrink-0">
        <div className="max-w-screen-xl mx-auto flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-xl font-bold text-gray-900">
              ⚽ World Cup Players
            </h1>
            <p className="text-sm text-gray-500">
              {filters.player_id && selectedPlayerName
                ? `Showing all tournaments for ${selectedPlayerName}`
                : currentTournament
                ? `${currentTournament.year} · ${currentTournament.host_country ?? ''} · ${currentTournament.num_teams ?? '?'} teams`
                : 'All tournaments · 1970–2026'}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setView('album')}
              className="px-4 py-2 rounded-lg bg-[#0e1430] text-white text-sm font-bold hover:bg-[#141c44] transition-colors"
            >
              🎴 Sticker Album
            </button>
            <PlayerSearch onSelectPlayer={handleSearchSelect} />
          </div>
        </div>
      </header>

      {/* Filter bar */}
      <div className="max-w-screen-xl w-full mx-auto">
        <FilterBar
          tournaments={tournaments}
          filters={filters}
          onChange={handleFilterChange}
        />
      </div>

      {/* Main table */}
      <main className="flex-1 max-w-screen-xl w-full mx-auto bg-white shadow-sm overflow-hidden flex flex-col">
        <StatsTable
          filters={filters}
          selectedPlayerId={selectedPlayerId}
          onSelectPlayer={handleSelectPlayer}
        />
      </main>

      {/* Career panel */}
      <CareerPanel
        playerId={selectedPlayerId}
        playerName={selectedPlayerName}
        onClose={handleClosePanel}
      />
    </div>
  )
}
