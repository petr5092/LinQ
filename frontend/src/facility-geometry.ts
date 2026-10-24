import type { SiteId } from './data'
import type { PlanRoom } from './facility-plan'

export type Point = [number, number]
export type Outline = Point[]
export type Fixture = 'machines' | 'racks' | 'booths' | 'loading' | 'gate' | 'fence' | 'platform'
export type PlanArea = { room: PlanRoom; outline: Outline; fixture: Fixture; elevation: number }
export type BuildingShape = { name: string; outline: Outline; height: number; dimensions: string }
export const floorHeights = { ground: 0, mezzanine: 3.6, upper: 6 }
export const rectangle = (x: number, y: number, width: number, depth: number): Outline => [
  [x, y],
  [x + width, y],
  [x + width, y + depth],
  [x, y + depth],
]
const northernAreas: Record<string, Outline[]> = {
  'Цех № 1-ground': [
    [
      [20, 20],
      [90, 20],
      [90, 49],
      [76, 49],
      [76, 60],
      [20, 60],
    ],
    rectangle(20, 64, 72, 34),
  ],
  'Цех № 1-mezzanine': [rectangle(21, 21, 38, 18)],
  'Окрасочный участок-ground': [rectangle(95, 20, 46, 40), rectangle(96, 65, 15, 33)],
  'Окрасочный участок-upper': [rectangle(97, 22, 42, 18)],
  'Склад-ground': [rectangle(156, 23, 30, 58), rectangle(189, 23, 23, 58)],
  'Склад-mezzanine': [rectangle(157, 24, 54, 18)],
  'Погрузочная зона-ground': [rectangle(156, 86, 56, 32), rectangle(218, 48, 15, 68)],
  'Проходная-ground': [rectangle(93, 132, 15, 12), rectangle(111, 132, 16, 12)],
  'Периметр-ground': [
    rectangle(4, 0, 240, 4),
    rectangle(240, 4, 4, 146),
    rectangle(4, 146, 236, 4),
    rectangle(4, 4, 4, 142),
  ],
  'Высотные работы-mezzanine': [rectangle(117, 70, 11, 14), rectangle(131, 70, 10, 14)],
}
export function outlineBounds(outline: Outline) {
  const xs = outline.map(([x]) => x),
    ys = outline.map(([, y]) => y)
  return {
    x: Math.min(...xs),
    y: Math.min(...ys),
    width: Math.max(...xs) - Math.min(...xs),
    depth: Math.max(...ys) - Math.min(...ys),
  }
}
export function insideOutline([x, y]: Point, outline: Outline) {
  let inside = false
  for (let i = 0, j = outline.length - 1; i < outline.length; j = i++) {
    const [xi, yi] = outline[i],
      [xj, yj] = outline[j]
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}
export function fixtureFor(zone: string): Fixture {
  if (/Склад|комплект/i.test(zone)) return 'racks'
  if (/красоч/i.test(zone)) return 'booths'
  if (/Погруз|разгруз|Парков/i.test(zone)) return 'loading'
  if (/Проход|ворот/i.test(zone)) return 'gate'
  if (/Периметр|Котлован/i.test(zone)) return 'fence'
  if (/Высот|Монтаж/i.test(zone)) return 'platform'
  return 'machines'
}
export function createGeometry(rooms: PlanRoom[], site: SiteId) {
  const groups = [...new Set(rooms.map((room) => room.building))]
  const buildings: BuildingShape[] =
    site === 'north'
      ? [
          {
            name: 'Корпус А',
            outline: [
              [18, 18],
              [143, 18],
              [143, 62],
              [113, 62],
              [113, 100],
              [18, 100],
            ],
            height: 12,
            dimensions: '125 × 82 м',
          },
          {
            name: 'Корпус Б',
            outline: [
              [154, 20],
              [214, 20],
              [214, 45],
              [236, 45],
              [236, 121],
              [154, 121],
            ],
            height: 10,
            dimensions: '82 × 101 м',
          },
          { name: 'Периметр', outline: rectangle(91, 130, 38, 16), height: 4, dimensions: 'КПП · 38 × 16 м' },
        ]
      : groups.map((name, index) => ({
          name,
          outline:
            index === 0
              ? [
                  [18, 18],
                  [140, 18],
                  [140, 61],
                  [105, 61],
                  [105, 107],
                  [18, 107],
                ]
              : rectangle(157, 27, 66, 99),
          height: index === 0 ? 11 : 8,
          dimensions: index === 0 ? '122 × 89 м' : '66 × 99 м',
        }))
  const areas: PlanArea[] = rooms.map((room) => {
    const peers = rooms.filter((peer) => peer.zone === room.zone && peer.floor === room.floor)
    const index = peers.indexOf(room)
    let outline = site === 'north' ? northernAreas[`${room.zone}-${room.floor}`]?.[index] : undefined
    if (!outline) {
      const groupIndex = groups.indexOf(room.building)
      const groupRooms = rooms.filter((peer) => peer.building === room.building && peer.floor === room.floor)
      const roomIndex = groupRooms.indexOf(room)
      const baseX = groupIndex === 0 ? 21 : 160
      const width = groupIndex === 0 ? 79 : 60
      outline = rectangle(baseX + (roomIndex % 2) * (width / 2), 24 + Math.floor(roomIndex / 2) * 39, width / 2 - 3, 35)
    }
    return { room, outline, fixture: fixtureFor(room.zone), elevation: floorHeights[room.floor] }
  })
  return { areas, buildings }
}

// Curved projections need samples along edges, not only the original corners.
export function sampleEdge(from: Point, to: Point, step = 6): Point[] {
  const count = Math.max(1, Math.ceil(Math.hypot(to[0] - from[0], to[1] - from[1]) / step))
  return Array.from({ length: count + 1 }, (_, index) => [
    from[0] + ((to[0] - from[0]) * index) / count,
    from[1] + ((to[1] - from[1]) * index) / count,
  ])
}
export function sampleOutline(outline: Outline): Outline {
  return outline.flatMap((point, index) => sampleEdge(point, outline[(index + 1) % outline.length]).slice(0, -1))
}

export function sceneLayout(
  rooms: PlanRoom[],
  visibleRooms: PlanRoom[],
  site: SiteId,
  projection: 'top' | 'isometric' | 'arc',
  scope: 'site' | 'building' | 'zone',
  compact = false
) {
  const { areas: allAreas, buildings: allBuildings } = createGeometry(rooms, site)
  const ids = new Set(visibleRooms.map((room) => room.id))
  const areas = allAreas.filter((area) => ids.has(area.room.id))
  const names = new Set(visibleRooms.map((room) => room.building))
  const buildings = allBuildings.filter((building) => names.has(building.name))
  const width = 1000,
    height = compact ? 320 : 650
  const includeCampus = scope === 'site' || names.size > 1 || visibleRooms.some((room) => room.zone === 'Периметр')
  const campus = rectangle(4, 0, 240, 150)
  const curved = projection === 'arc'
  const edgePoints = (outline: Outline) => (curved ? sampleOutline(outline) : outline)
  const reference = includeCampus
    ? campus
    : [
        ...areas.flatMap((area) => area.outline),
        ...(scope === 'building' ? buildings.flatMap((building) => building.outline) : []),
      ]
  const lateral = reference.map(([x, y]) => (x - y) * 2.5)
  const left = lateral.length ? Math.min(...lateral) : 0
  const right = lateral.length ? Math.max(...lateral) : 1
  const span = Math.max(1, right - left)
  const middle = (left + right) / 2
  const raw = ([x, y]: Point, z = 0): Point => {
    if (projection === 'top') return [x * 2.5, y * 2.5]
    const sx = (x - y) * 2.5
    // A shallow cylindrical surface lifts its wings. A steeper viewing angle
    // also separates front and rear objects while preserving their positions.
    const bend = curved ? Math.pow((sx - middle) / (span / 2), 2) * span * 0.14 : 0
    return [sx, (x + y) * (curved ? (compact ? 1.15 : 1.7) : compact ? 0.82 : 1.12) - z * 3.4 - bend]
  }
  const extent = areas.flatMap((area) =>
    edgePoints(area.outline).flatMap((point) => [raw(point, area.elevation), raw(point, area.elevation + 8)])
  )
  if (includeCampus) extent.push(...edgePoints(campus).map((point) => raw(point)))
  if (scope === 'building' || curved)
    for (const building of buildings)
      if (scope !== 'zone')
        extent.push(...edgePoints(building.outline).flatMap((point) => [raw(point), raw(point, building.height)]))
  const xs = extent.map(([x]) => x),
    ys = extent.map(([, y]) => y)
  const minX = xs.length ? Math.min(...xs) : 0,
    maxX = xs.length ? Math.max(...xs) : 1,
    minY = ys.length ? Math.min(...ys) : 0,
    maxY = ys.length ? Math.max(...ys) : 1
  const scale = Math.min(
    (width - (compact ? 80 : 130)) / Math.max(1, maxX - minX),
    (height - (compact ? 70 : 125)) / Math.max(1, maxY - minY)
  )
  const dx = (width - (maxX - minX) * scale) / 2 - minX * scale,
    dy = (height - (maxY - minY) * scale) / 2 - minY * scale
  const project = (point: Point, z = 0, _floor?: PlanRoom['floor']): Point => {
    const [x, y] = raw(point, z)
    return [x * scale + dx, y * scale + dy]
  }
  return { areas, buildings, width, height, scale, project, includeCampus, campus }
}
