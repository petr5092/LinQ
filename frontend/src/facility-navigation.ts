import type { PlanRoom } from './facility-plan'

export type MapFocus = { building: string | null; zone: string | null; room: string | null }
export const siteFocus: MapFocus = { building: null, zone: null, room: null }
export type MapAction =
  | { type: 'building'; building: string }
  | { type: 'zone'; building: string; zone: string }
  | { type: 'room'; room: PlanRoom }
  | { type: 'close-zone' | 'close-building' | 'clear-room' }
export function mapNavigation(focus: MapFocus, action: MapAction): MapFocus {
  switch (action.type) {
    case 'building':
      return { building: action.building, zone: null, room: null }
    case 'zone':
      return { building: action.building, zone: action.zone, room: null }
    case 'room':
      return { building: action.room.building, zone: action.room.zone, room: action.room.id }
    case 'close-zone':
      return { ...focus, zone: null, room: null }
    case 'close-building':
      return siteFocus
    case 'clear-room':
      return { ...focus, room: null }
  }
}
