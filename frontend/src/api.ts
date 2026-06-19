import type {
  CareerAggregateOut,
  Page,
  PlayerOut,
  PlayerStatOut,
  StatsFilters,
  TournamentOut,
} from './types'

const KEY = import.meta.env.VITE_API_KEY as string

function headers(): HeadersInit {
  return { 'X-API-Key': KEY }
}

async function get<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
): Promise<T> {
  const url = new URL(path, location.origin)
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== '') url.searchParams.set(k, String(v))
    }
  }
  const res = await fetch(url.toString(), { headers: headers() })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json()
}

export const api = {
  getTournaments: () =>
    get<Page<TournamentOut>>('/v1/tournaments', { limit: 20 }),

  searchPlayers: (q: string) =>
    get<Page<PlayerOut>>('/v1/players', { q, limit: 8 }),

  getStats: (filters: StatsFilters, page = 0, limit = 50) =>
    get<Page<PlayerStatOut>>('/v1/stats', {
      ...filters,
      limit,
      offset: page * limit,
    }),

  getCareer: (id: number) =>
    get<CareerAggregateOut>(`/v1/players/${id}/career`),

  getPlayerStats: (id: number) =>
    get<Page<PlayerStatOut>>('/v1/stats', { player_id: id, limit: 20 }),
}
