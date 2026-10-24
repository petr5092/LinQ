import { useRef, useState } from 'react'
import { X } from 'lucide-react'
import type { SafetyEvent, SiteId } from '../data'
import type { PlanRoom } from '../facility-plan'
import type { MapFocus } from '../facility-navigation'
import { sceneLayout, sampleOutline, type Point } from '../facility-geometry'
import { FacilityScene, type SceneDepth } from './facility-scene'

type Frame = { x: number; y: number; width: number }
export type FacilityAtlasProps = {
  site: SiteId
  rooms: PlanRoom[]
  buildingRooms: PlanRoom[]
  zoneRooms: PlanRoom[]
  events: SafetyEvent[]
  focus: MapFocus
  coverage: boolean
  zoom: number
  reset: number
  onBuilding: (name: string) => void
  onZone: (building: string, zone: string) => void
  onSelect: (id: string) => void
  onIncident: (event: SafetyEvent) => void
  onCloseZone: () => void
  onCloseRoom: () => void
  curved?: boolean
}
const placements = (count: number): Frame[] =>
  count === 1
    ? [{ x: 35, y: 145, width: 930 }]
    : count === 2
      ? [
          { x: 20, y: 10, width: 520 },
          { x: 10, y: 260, width: 980 },
        ]
      : count === 3
        ? [
            { x: 10, y: 5, width: 440 },
            { x: 390, y: 130, width: 590 },
            { x: 0, y: 320, width: 1000 },
          ]
        : [
            { x: 10, y: 5, width: 320 },
            { x: 490, y: 5, width: 490 },
            { x: 10, y: 155, width: 620 },
            { x: 10, y: 340, width: 950 },
          ]
const toAtlas = (point: Point, frame: Frame): Point => [
  frame.x + (point[0] * frame.width) / 1000,
  frame.y + (point[1] * frame.width) / 1000,
]
export function FacilityAtlas(props: FacilityAtlasProps) {
  const {
    site,
    rooms,
    buildingRooms,
    zoneRooms,
    events,
    focus,
    coverage,
    zoom,
    reset,
    onBuilding,
    onZone,
    onSelect,
    onIncident,
    onCloseZone,
    onCloseRoom,
    curved = false,
  } = props
  const [pan, setPan] = useState({ x: 0, y: 0, reset })
  const drag = useRef<{ x: number; y: number; startX: number; startY: number; moved: boolean } | null>(null)
  const suppressClick = useRef(false)
  const currentPan = zoom > 1 && pan.reset === reset ? pan : { x: 0, y: 0 }
  const viewWidth = 1000 / zoom,
    viewHeight = 650 / zoom
  const selectedRoom = rooms.find((room) => room.id === focus.room)
  // A physical-floor selection must not crop the workshop above the focused subzone.
  const parentBuildingRooms = selectedRoom ? rooms.filter((room) => room.building === focus.building) : buildingRooms
  const parentZoneRooms = selectedRoom ? parentBuildingRooms.filter((room) => room.zone === focus.zone) : zoneRooms
  const scopes: { key: string; depth: SceneDepth; rooms: PlanRoom[]; name: string }[] = [
    { key: 'site', depth: 'site', rooms, name: 'Объект' },
    ...(focus.building
      ? [{ key: 'building', depth: 'building' as const, rooms: parentBuildingRooms, name: focus.building }]
      : []),
    ...(focus.zone ? [{ key: 'zone', depth: 'zone' as const, rooms: parentZoneRooms, name: focus.zone }] : []),
    ...(selectedRoom ? [{ key: 'room', depth: 'zone' as const, rooms: [selectedRoom], name: selectedRoom.name }] : []),
  ]
  const count = scopes.length
  const compact = !(curved && count === 1)
  const frames = compact ? placements(count) : [{ x: 0, y: 0, width: 1000 }]
  const projection = curved ? 'arc' : 'isometric'
  const edgePoints = (outline: Point[]) => (curved ? sampleOutline(outline) : outline)
  const layouts = scopes.map((scope) => sceneLayout(rooms, scope.rooms, site, projection, scope.depth, compact))
  const cones: { source: Point[]; target: Point[]; id: string }[] = []
  if (focus.building) {
    const building = layouts[0].buildings.find((item) => item.name === focus.building)
    if (building)
      cones.push({
        id: focus.building,
        source: edgePoints(building.outline).map((point) =>
          toAtlas(layouts[0].project(point, building.height), frames[0])
        ),
        target: edgePoints(building.outline).map((point) => toAtlas(layouts[1].project(point, 0), frames[1])),
      })
  }
  if (focus.zone) {
    for (const area of layouts[1].areas.filter((area) => area.room.zone === focus.zone)) {
      cones.push({
        id: `${focus.zone}-${area.room.id}`,
        source: edgePoints(area.outline).map((point) => toAtlas(layouts[1].project(point, area.elevation), frames[1])),
        target: edgePoints(area.outline).map((point) => toAtlas(layouts[2].project(point, area.elevation), frames[2])),
      })
    }
  }
  if (selectedRoom) {
    const area = layouts[2].areas.find((area) => area.room.id === selectedRoom.id)
    if (area)
      cones.push({
        id: selectedRoom.id,
        source: edgePoints(area.outline).map((point) => toAtlas(layouts[2].project(point, area.elevation), frames[2])),
        target: edgePoints(area.outline).map((point) => toAtlas(layouts[3].project(point, area.elevation), frames[3])),
      })
  }
  return (
    <div
      className="facility-atlas"
      data-levels={count}
      data-projection={projection}
      aria-label="Объёмная карта с детализацией"
    >
      <svg
        className="atlas-canvas"
        viewBox={`${(1000 - viewWidth) / 2 + currentPan.x} ${(650 - viewHeight) / 2 + currentPan.y} ${viewWidth} ${viewHeight}`}
        onPointerDown={(event) => {
          if (zoom > 1)
            drag.current = {
              x: event.clientX,
              y: event.clientY,
              startX: currentPan.x,
              startY: currentPan.y,
              moved: false,
            }
        }}
        onPointerMove={(event) => {
          if (!drag.current) return
          const dx = event.clientX - drag.current.x,
            dy = event.clientY - drag.current.y
          if (Math.abs(dx) + Math.abs(dy) > 5) {
            drag.current.moved = true
            event.currentTarget.setPointerCapture(event.pointerId)
          }
          const box = event.currentTarget.getBoundingClientRect(),
            factor = Math.max(viewWidth / box.width, viewHeight / box.height)
          setPan({
            x: Math.max(-(1000 - viewWidth) / 2, Math.min((1000 - viewWidth) / 2, drag.current.startX - dx * factor)),
            y: Math.max(-(650 - viewHeight) / 2, Math.min((650 - viewHeight) / 2, drag.current.startY - dy * factor)),
            reset,
          })
        }}
        onPointerUp={() => {
          if (drag.current) {
            suppressClick.current = drag.current.moved
            drag.current = null
          }
        }}
        onPointerCancel={() => {
          drag.current = null
        }}
        onClickCapture={(event) => {
          if (suppressClick.current) {
            event.stopPropagation()
            suppressClick.current = false
          }
        }}
        role="group"
        aria-label="Объект, корпус, цех и выбранная подзона в одном пространстве"
      >
        <defs>
          <linearGradient id="atlas-focus-cone" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#438ce1" stopOpacity=".01" />
            <stop offset="1" stopColor="#438ce1" stopOpacity=".04" />
          </linearGradient>
        </defs>
        <g className="atlas-connections" aria-hidden="true">
          {cones.map((cone) => {
            const guides = curved
              ? [
                  cone.source.reduce((best, point, index) => (point[0] < cone.source[best][0] ? index : best), 0),
                  cone.source.reduce((best, point, index) => (point[0] > cone.source[best][0] ? index : best), 0),
                ]
              : cone.source.map((_, index) => index)
            return (
              <g key={cone.id} className="atlas-cone" data-connection={cone.id}>
                {cone.source.map((point, index) => {
                  const next = (index + 1) % cone.source.length
                  return (
                    <polygon
                      key={index}
                      points={[point, cone.source[next], cone.target[next], cone.target[index]]
                        .map((p) => p.join(','))
                        .join(' ')}
                    />
                  )
                })}
                {[...new Set(guides)].map((index) => (
                  <path key={index} d={`M${cone.source[index].join(' ')}L${cone.target[index].join(' ')}`} />
                ))}
              </g>
            )
          })}
        </g>
        {scopes.map((scope, index) => {
          const frame = frames[index]
          return (
            <g
              key={scope.key}
              className={`atlas-stage atlas-stage-${scope.key}`}
              data-stage={scope.key}
              style={{ transform: `translate(${frame.x}px,${frame.y}px) scale(${frame.width / 1000})` }}
            >
              <FacilityScene
                embedded={compact}
                site={site}
                rooms={rooms}
                visibleRooms={scope.rooms}
                events={events}
                selected={focus.room}
                selectedBuilding={focus.building}
                selectedZone={focus.zone}
                depth={scope.depth}
                projection={projection}
                coverage={coverage}
                zoom={1}
                reset={reset}
                onBuilding={onBuilding}
                onZone={onZone}
                onSelect={onSelect}
                onIncident={onIncident}
              />
            </g>
          )
        })}
        <g className="atlas-stage-captions">
          {scopes.map((scope, index) => {
            const frame = frames[index]
            return (
              <foreignObject
                key={scope.key}
                x={frame.x + 16}
                y={frame.y}
                width={Math.min(450, scope.name.length * 14 + 110)}
                height="44"
                className="atlas-scope-caption"
              >
                <div className={`atlas-scope-title ${index ? 'is-active' : ''}`}>
                  <button
                    className="atlas-scope-jump"
                    aria-label={`Перейти на уровень: ${scope.name}`}
                    onPointerDown={(event) => event.stopPropagation()}
                    onClick={(event) => {
                      event.stopPropagation()
                      if (scope.depth === 'site') onBuilding('all')
                      else if (scope.depth === 'building') onBuilding(scope.name)
                      else if (scope.key === 'room' && selectedRoom) onSelect(selectedRoom.id)
                      else if (focus.building) onZone(focus.building, scope.name)
                    }}
                  >
                    <span className="atlas-level-number">0{index + 1}</span>
                    <span className="atlas-level-name">{scope.name}</span>
                  </button>
                  {index ? (
                    <button
                      type="button"
                      aria-label={
                        scope.key === 'room'
                          ? 'Закрыть план подзоны'
                          : scope.depth === 'building'
                            ? 'Закрыть план корпуса'
                            : 'Закрыть план зоны'
                      }
                      title={
                        scope.key === 'room'
                          ? 'Вернуться к цеху'
                          : scope.depth === 'building'
                            ? 'Вернуться ко всему объекту'
                            : 'Вернуться к корпусу'
                      }
                      onPointerDown={(event) => event.stopPropagation()}
                      onClick={(event) => {
                        event.stopPropagation()
                        if (scope.key === 'room') onCloseRoom()
                        else if (scope.depth === 'building') onBuilding('all')
                        else onCloseZone()
                      }}
                    >
                      <X size={20} />
                    </button>
                  ) : null}
                </div>
              </foreignObject>
            )
          })}
        </g>
      </svg>
    </div>
  )
}
