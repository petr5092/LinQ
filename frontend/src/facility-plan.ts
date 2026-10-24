import type { Camera, SafetyEvent } from './data'

export type Floor = 'ground' | 'mezzanine' | 'upper'
export type Risk = 'clear' | 'notice' | 'warning' | 'critical'
export type PlanRoom = {
  id: string
  zone: string
  name: string
  building: string
  floor: Floor
  cameras: Camera[]
}
export const floorLabels: Record<Floor, string> = {
  ground: '1 этаж',
  mezzanine: 'Антресоль',
  upper: '2 этаж',
}
export const riskLabels: Record<Risk, string> = {
  clear: 'Без нарушений',
  notice: 'Внимание',
  warning: 'Повышенный риск',
  critical: 'Критический риск',
}
export function activeEvents(events: SafetyEvent[]) {
  return events.filter((event) => event.status === 'new' || event.status === 'working')
}
export function riskOf(events: SafetyEvent[]): Risk {
  const active = activeEvents(events)
  if (active.some((event) => event.severity === 'critical')) return 'critical'
  if (active.filter((event) => event.severity === 'warning').length > 1) return 'warning'
  return active.length ? 'notice' : 'clear'
}
export function roomEvents(room: PlanRoom, events: SafetyEvent[]) {
  const ids = new Set(room.cameras.map((camera) => camera.id))
  return events.filter((event) => ids.has(event.camera)).sort((a, b) => b.time.localeCompare(a.time))
}
// Demonstration geometry and levels. Camera IDs link events to a single area and level.
export function createRooms(cameras: Camera[]): PlanRoom[] {
  const zones = [...new Set(cameras.map((camera) => camera.zone))]
  return zones.flatMap((zone) => {
    const zoneCameras = cameras.filter((camera) => camera.zone === zone)
    const levels = zoneCameras.map((camera, index): { camera: Camera; floor: Floor } => ({
      camera,
      floor:
        zone === 'Высотные работы' || (zone === 'Цех № 1' && index >= 3) || (zone === 'Склад' && index >= 3)
          ? 'mezzanine'
          : zone === 'Окрасочный участок' && index >= 3
            ? 'upper'
            : 'ground',
    }))
    return (['ground', 'mezzanine', 'upper'] as Floor[]).flatMap((floor) => {
      const onFloor = levels.filter((entry) => entry.floor === floor).map((entry) => entry.camera)
      const camerasPerRoom = zone === 'Периметр' ? 1 : 2
      return Array.from({ length: Math.ceil(onFloor.length / camerasPerRoom) }, (_, index) => {
        const group = onFloor.slice(index * camerasPerRoom, index * camerasPerRoom + camerasPerRoom)
        return {
          id: `${zone}-${floor}-${index}`,
          zone,
          name:
            zone === 'Периметр'
              ? (['Северная секция', 'Восточная секция', 'Южная секция', 'Западная секция'][index] ??
                `Секция ${index + 1}`)
              : group[0].name,
          building: group[0].workshop,
          floor,
          cameras: group,
        }
      })
    })
  })
}
