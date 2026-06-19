import type { PlayerStatOut } from '../types'
import { fmt, fmtMinutes } from '../utils/fmt'

interface Props {
  stat: PlayerStatOut
  onClick: () => void
  selected: boolean
}

export function PlayerRow({ stat, onClick, selected }: Props) {
  return (
    <tr
      className={`border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors ${
        selected ? 'bg-blue-50' : ''
      }`}
      onClick={onClick}
    >
      <td className="px-4 py-2.5">
        <div className="font-medium text-gray-900 text-sm">{stat.player_name}</div>
      </td>
      <td className="px-4 py-2.5 text-sm text-gray-600">{stat.team_name ?? '–'}</td>
      <td className="px-4 py-2.5 text-sm text-gray-600">{stat.year}</td>
      <td className="px-4 py-2.5 text-sm text-center">
        <span className={`font-semibold ${stat.goals ? 'text-green-700' : 'text-gray-400'}`}>
          {fmt(stat.goals)}
        </span>
      </td>
      <td className="px-4 py-2.5 text-sm text-center text-gray-600">{fmt(stat.assists)}</td>
      <td className="px-4 py-2.5 text-sm text-center text-gray-600">{fmt(stat.appearances)}</td>
      <td className="px-4 py-2.5 text-sm text-center text-gray-500">{fmtMinutes(stat.minutes_played)}</td>
      <td className="px-4 py-2.5 text-sm text-center">
        {stat.yellow_cards ? (
          <span className="inline-block w-3 h-4 bg-yellow-400 rounded-sm align-middle mr-0.5" title="Yellow cards" />
        ) : null}
        <span className="text-gray-600">{fmt(stat.yellow_cards)}</span>
      </td>
      <td className="px-4 py-2.5 text-sm text-center">
        {stat.red_cards ? (
          <span className="inline-block w-3 h-4 bg-red-500 rounded-sm align-middle mr-0.5" title="Red cards" />
        ) : null}
        <span className="text-gray-600">{fmt(stat.red_cards)}</span>
      </td>
    </tr>
  )
}
