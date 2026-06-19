export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface TournamentOut {
  year: number
  host_country: string | null
  start_date: string | null
  end_date: string | null
  num_teams: number | null
}

export interface PlayerOut {
  id: number
  full_name: string
  position: string | null
  birth_date: string | null
}

export interface PlayerStatOut {
  player_id: number
  player_name: string
  position: string | null
  team_name: string | null
  year: number
  jersey_number: number | null
  goals: number | null
  assists: number | null
  minutes_played: number | null
  fouls_committed: number | null
  yellow_cards: number | null
  red_cards: number | null
  appearances: number | null
}

export interface CareerAggregateOut {
  player_id: number
  player_name: string
  tournaments_played: number
  total_goals: number
  total_assists: number
  total_minutes: number
  total_yellow_cards: number
  total_red_cards: number
}

export interface StatsFilters {
  year?: number
  team?: string
  position?: string
  player_id?: number
  min_goals?: number
  sort?: string
}
