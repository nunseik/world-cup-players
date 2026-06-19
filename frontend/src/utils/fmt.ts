export function fmt(value: number | null | undefined): string {
  return value == null ? '–' : String(value)
}

export function fmtMinutes(value: number | null | undefined): string {
  return value == null ? '–' : `${value}'`
}
