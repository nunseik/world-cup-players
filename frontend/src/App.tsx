import { useEffect, useState } from 'react'
import { api } from './api'
import { CareerPanel } from './components/CareerPanel'
import { FilterBar } from './components/FilterBar'
import { PlayerSearch } from './components/PlayerSearch'
import { StatsTable } from './components/StatsTable'
import type { PlayerOut, StatsFilters, TournamentOut } from './types'

export default function App() {
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
    // Filter the table to show only this player's career
    setFilters((f) => ({ sort: f.sort, player_id: player.id }))
  }

  function handleClosePanel() {
    setSelectedPlayerId(null)
    setSelectedPlayerName(null)
    // Remove player_id filter when closing
    setFilters((f) => {
      const { player_id: _, ...rest } = f
      return { ...rest, year: rest.year ?? 2026 }
    })
  }

  function handleFilterChange(f: StatsFilters) {
    // Clear player focus when user changes filters manually
    setSelectedPlayerId(null)
    setSelectedPlayerName(null)
    setFilters({ ...f, player_id: undefined })
  }

  const currentTournament = tournaments.find((t) => t.year === filters.year)

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
          <PlayerSearch onSelectPlayer={handleSearchSelect} />
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
