import { useId, useRef, useState, type ReactNode } from 'react'
import { Tooltip, TooltipTrigger, TooltipContent } from './ui/tooltip'
import type { SafetyEvent, SiteId } from '../data'
import { floorLabels, riskLabels, riskOf, roomEvents, activeEvents, type PlanRoom, type Floor } from '../facility-plan'
import {
  sceneLayout,
  sampleEdge,
  sampleOutline,
  outlineBounds,
  insideOutline,
  rectangle,
  type Outline,
  type Point,
  type PlanArea,
} from '../facility-geometry'

export type Projection = 'isometric' | 'top' | 'arc'
export type SceneDepth = 'site' | 'building' | 'zone'
type Props = {
  site: SiteId
  rooms: PlanRoom[]
  visibleRooms: PlanRoom[]
  events: SafetyEvent[]
  selected: string | null
  projection: Projection
  embedded?: boolean
  selectedBuilding?: string | null
  selectedZone?: string | null
  depth: SceneDepth
  onBuilding: (name: string) => void
  onZone: (building: string, zone: string) => void
  onIncident: (event: SafetyEvent) => void
  coverage: boolean
  zoom: number
  reset: number
  onSelect: (id: string) => void
}
function SceneTarget({
  label,
  name,
  detail,
  className,
  selected = false,
  onActivate,
  children,
}: {
  label: string
  name: string
  detail: string
  className: string
  selected?: boolean
  onActivate: () => void
  children: ReactNode
}) {
  return (
    <Tooltip delayDuration={100}>
      <TooltipTrigger asChild>
        <g
          role="button"
          tabIndex={0}
          aria-label={label}
          aria-pressed={selected}
          className={className}
          onClick={(event) => {
            event.stopPropagation()
            onActivate()
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault()
              event.stopPropagation()
              onActivate()
            }
          }}
        >
          {children}
        </g>
      </TooltipTrigger>
      <TooltipContent side="top" sideOffset={8} className="scene-tooltip">
        <strong>{name}</strong>
        <span>{detail}</span>
      </TooltipContent>
    </Tooltip>
  )
}
function center(outline: Outline): Point {
  const b = outlineBounds(outline)
  return [b.x + b.width / 2, b.y + b.depth / 2]
}
export function FacilityScene({
  site,
  rooms,
  visibleRooms,
  events,
  selected,
  projection,
  depth,
  onBuilding,
  onZone,
  onIncident,
  coverage,
  zoom,
  onSelect,
  reset,
  embedded = false,
  selectedBuilding,
  selectedZone,
}: Props) {
  const clipId = useId().replaceAll(':', '')
  const [pan, setPan] = useState({ x: 0, y: 0, reset })
  const suppressClick = useRef(false)
  const drag = useRef<{ x: number; y: number; startX: number; startY: number; moved: boolean } | null>(null)
  const {
    areas,
    buildings,
    project,
    scale,
    includeCampus,
    campus,
    width: WIDTH,
    height: HEIGHT,
  } = sceneLayout(rooms, visibleRooms, site, projection, depth, embedded)
  const points = (outline: Outline, z = 0, level: Floor = 'ground') =>
    (projection === 'arc' ? sampleOutline(outline) : outline)
      .map((point) => project(point, z, level).join(','))
      .join(' ')
  const line = (from: Point, to: Point, z: number, level: Floor) => {
    const edge = projection === 'arc' ? sampleEdge(from, to) : [from, to]
    return edge.map((point, index) => `${index ? 'L' : 'M'}${project(point, z, level).join(' ')}`).join('')
  }
  const prism = (outline: Outline, z: number, height: number, level: Floor, className: string) => (
    <g className={className}>
      {projection !== 'top'
        ? outline.map((point, index) => {
            const next = outline[(index + 1) % outline.length]
            const edge = projection === 'arc' ? sampleEdge(point, next) : [point, next]
            return (
              <polygon
                key={index}
                className="scene-prism-side"
                points={[
                  ...edge.map((point) => project(point, z, level)),
                  ...[...edge].reverse().map((point) => project(point, z + height, level)),
                ]
                  .map((p) => p.join(','))
                  .join(' ')}
              />
            )
          })
        : null}
      <polygon className="scene-prism-top" points={points(outline, z + height, level)} />
    </g>
  )
  const equipment = (area: PlanArea) => {
    const { x, y, width, depth } = outlineBounds(area.outline)
    if (area.fixture === 'fence')
      return (
        <path
          className="scene-fence"
          d={
            width > depth
              ? line([x + 2, y + depth / 2], [x + width - 2, y + depth / 2], area.elevation + 1, area.room.floor)
              : line([x + width / 2, y + 2], [x + width / 2, y + depth - 2], area.elevation + 1, area.room.floor)
          }
        />
      )
    const rack = area.fixture === 'racks',
      booth = area.fixture === 'booths',
      loading = area.fixture === 'loading'
    const stepX = rack ? 9 : booth ? 11 : loading ? 17 : 12
    const stepY = rack ? 12 : booth ? 12 : loading ? 15 : 11
    const items = []
    for (let i = 0, xx = x + 5; xx < x + width - 4; xx += stepX)
      for (let yy = y + 5; yy < y + depth - 4; yy += stepY) {
        const w = rack ? 3 : booth ? 6 : loading ? 5 : 3.5
        const d = rack ? 8 : booth ? 7 : loading ? 9 : 4.5
        if (
          xx + w > x + width - 2 ||
          yy + d > y + depth - 2 ||
          ![
            [xx, yy],
            [xx + w, yy],
            [xx + w, yy + d],
            [xx, yy + d],
          ].every((point) => insideOutline(point as Point, area.outline))
        )
          continue
        const outline = rectangle(xx, yy, w, d)
        items.push(
          <g key={i++}>
            {prism(
              outline,
              area.elevation + 0.25,
              rack ? 4.5 : booth ? 3 : loading ? 1.6 : 1.8,
              area.room.floor,
              `scene-fixture ${rack ? 'rack' : ''}`
            )}
            {rack
              ? [1.5, 3].map((z) => (
                  <polyline
                    key={z}
                    points={points(outline, area.elevation + z, area.room.floor)}
                    className="scene-rack-shelf"
                  />
                ))
              : null}
          </g>
        )
      }
    return items
  }
  const currentPan = pan.reset === reset && zoom > 1 ? pan : { x: 0, y: 0 }
  const viewWidth = WIDTH / zoom,
    viewHeight = HEIGHT / zoom
  const eventsForRooms = (group: PlanRoom[]) => {
    const ids = new Set(group.flatMap((room) => room.cameras.map((camera) => camera.id)))
    return events.filter((event) => ids.has(event.camera))
  }
  const markers = (history: SafetyEvent[], at: Point) => {
    const open = activeEvents(history).sort(
      (a, b) =>
        (a.severity === 'critical' ? -1 : 1) - (b.severity === 'critical' ? -1 : 1) || b.time.localeCompare(a.time)
    )
    return (
      <g className="scene-markers">
        {open.map((event, index) => {
          const x = at[0] + ((index % 5) - Math.min(4, open.length - 1) / 2) * (embedded ? 36 : 27),
            y = at[1] + Math.floor(index / 5) * (embedded ? 36 : 27)
          return (
            <SceneTarget
              key={event.id}
              className={`scene-incident risk-${riskOf([event])}`}
              label={`Перейти к нарушению ${event.id}: ${event.title}`}
              name={event.title}
              detail={`${event.zone} · ${event.camera} · ${event.time.slice(0, 5)} · Перейти к месту нарушения`}
              onActivate={() => onIncident(event)}
            >
              <circle cx={x} cy={y} r={embedded ? 15 : 11} />
              <text x={x} y={y + 4} textAnchor="middle">
                !
              </text>
            </SceneTarget>
          )
        })}
      </g>
    )
  }
  const renderArea = (area: PlanArea) => {
    const history = roomEvents(area.room, events),
      risk = riskOf(history),
      selectedArea = selected === area.room.id
    const at = project(center(area.outline), area.elevation + 0.4, area.room.floor),
      b = outlineBounds(area.outline)
    return (
      <g
        key={area.room.id}
        data-room-id={area.room.id}
        className={`scene-entity ${
          (depth === 'site' && selectedBuilding && area.room.building !== selectedBuilding) ||
          (depth === 'building' && selectedZone && area.room.zone !== selectedZone) ||
          (depth === 'zone' && selected && !selectedArea)
            ? 'is-muted'
            : ''
        }`}
      >
        <SceneTarget
          className={`scene-area risk-${risk} ${selectedArea ? 'chosen' : ''}`}
          selected={selectedArea}
          label={`${area.room.zone}, ${area.room.name}, ${riskLabels[risk]}`}
          name={area.room.name}
          detail={`${area.room.zone} · ${floorLabels[area.room.floor]} · ${area.room.cameras.map((camera) => camera.id).join(', ')} · ${riskLabels[risk]}`}
          onActivate={() => onSelect(area.room.id)}
        >
          {prism(area.outline, area.elevation, 0.3, area.room.floor, 'scene-area-floor')}
          <g className="scene-equipment" aria-hidden="true">
            {equipment(area)}
          </g>
          {area.elevation > 0 && projection !== 'top' ? (
            <g className="scene-railings" aria-hidden="true">
              <polyline points={points([...area.outline, area.outline[0]], area.elevation + 1.2, area.room.floor)} />
              {area.outline.map((point, index) => (
                <path
                  key={index}
                  d={`M${project(point, area.elevation, area.room.floor).join(' ')}L${project(point, area.elevation + 1.2, area.room.floor).join(' ')}`}
                />
              ))}
            </g>
          ) : null}
          {coverage ? (
            <polygon
              className="scene-camera-cone"
              points={points(
                [
                  [b.x + 1, b.y + 1],
                  [b.x + Math.min(b.width - 1, 28), b.y + 1],
                  [b.x + 1, b.y + Math.min(b.depth - 1, 22)],
                ],
                area.elevation + 0.4,
                area.room.floor
              )}
            />
          ) : null}
          {!area.room.cameras.some((camera) => camera.online) ? (
            <polygon
              className="scene-offline"
              points={points(area.outline, area.elevation + 0.35, area.room.floor)}
              fill={`url(#${clipId}-hatch)`}
            />
          ) : null}
        </SceneTarget>
        {markers(history, [at[0], at[1] + 12])}
      </g>
    )
  }
  return (
    <svg
      role="group"
      className={`facility-scene ${embedded ? 'scene-embedded' : ''}`}
      width={WIDTH}
      height={HEIGHT}
      data-depth={depth}
      data-projection={projection}
      viewBox={`${(WIDTH - viewWidth) / 2 + currentPan.x} ${(HEIGHT - viewHeight) / 2 + currentPan.y} ${viewWidth} ${viewHeight}`}
      aria-label={
        depth === 'site' ? 'Схема завода' : depth === 'building' ? 'Общий план корпуса' : 'Подзоны и оборудование'
      }
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
        const box = event.currentTarget.getBoundingClientRect()
        const factor = Math.max(viewWidth / box.width, viewHeight / box.height)
        setPan({
          x: Math.max(-(WIDTH - viewWidth) / 2, Math.min((WIDTH - viewWidth) / 2, drag.current.startX - dx * factor)),
          y: Math.max(
            -(HEIGHT - viewHeight) / 2,
            Math.min((HEIGHT - viewHeight) / 2, drag.current.startY - dy * factor)
          ),
          reset,
        })
      }}
      onClickCapture={(event) => {
        if (suppressClick.current) {
          event.stopPropagation()
          suppressClick.current = false
        }
      }}
      onPointerCancel={() => {
        drag.current = null
      }}
      onPointerUp={() => {
        if (drag.current) {
          suppressClick.current = drag.current.moved
          drag.current = null
        }
      }}
    >
      <defs>
        <pattern id={`${clipId}-hatch`} width="8" height="8" patternUnits="userSpaceOnUse">
          <path d="M0 8L8 0" stroke="#a6afb7" strokeWidth=".5" />
        </pattern>
      </defs>
      {includeCampus ? (
        <>
          <polygon points={points(campus)} className="scene-campus" />
          <g className="scene-roads" aria-hidden="true">
            <path d={line([8, 125], [240, 125], 0, 'ground')} />
            <path d={line([148, 12], [148, 146], 0, 'ground')} />
            <path d={line([8, 13], [240, 13], 0, 'ground')} />
          </g>
        </>
      ) : null}
      {depth === 'site' ? (
        <g className="scene-site-buildings">
          {buildings.map((building) => {
            const buildingRooms = visibleRooms.filter(
                (room) => room.building === building.name && room.zone !== 'Периметр'
              ),
              history = eventsForRooms(buildingRooms),
              risk = riskOf(history)
            if (!buildingRooms.length) return null
            const title = building.name === 'Периметр' ? 'Проходная и площадки' : building.name
            return (
              <g
                key={building.name}
                data-building={building.name}
                className={`scene-entity ${selectedBuilding && selectedBuilding !== building.name ? 'is-muted' : ''}`}
              >
                <SceneTarget
                  className={`scene-building risk-${risk} ${selectedBuilding === building.name ? 'chosen' : ''}`}
                  selected={selectedBuilding === building.name}
                  label={`Открыть ${building.name}`}
                  name={title}
                  detail={`${riskLabels[risk]} · Открыть общий план`}
                  onActivate={() => onBuilding(building.name)}
                >
                  {prism(building.outline, 0, building.height, 'ground', 'scene-building-volume')}
                </SceneTarget>
              </g>
            )
          })}
          {areas.filter((area) => area.fixture === 'fence' && area.room.zone === 'Периметр').map(renderArea)}
          <g className="scene-site-markers">
            {buildings.map((building) => {
              const buildingRooms = visibleRooms.filter(
                (room) => room.building === building.name && room.zone !== 'Периметр'
              )
              const at = project(center(building.outline), projection === 'top' ? 0 : building.height)
              return (
                <g
                  key={building.name}
                  data-marker-building={building.name}
                  className={`scene-entity ${selectedBuilding && selectedBuilding !== building.name ? 'is-muted' : ''}`}
                >
                  {markers(eventsForRooms(buildingRooms), [at[0], at[1] + 12])}
                </g>
              )
            })}
          </g>
        </g>
      ) : null}
      {depth === 'building' ? (
        <g className="scene-building-zones">
          {[...new Set(areas.map((area) => area.room.zone))].map((zone) => {
            const zoneAreas = areas.filter((area) => area.room.zone === zone)
            if (zone === 'Периметр') return <g key={zone}>{zoneAreas.map(renderArea)}</g>
            const history = eventsForRooms(zoneAreas.map((area) => area.room)),
              risk = riskOf(history)
            const anchor = zoneAreas[0],
              at = project(center(anchor.outline), anchor.elevation + 0.5, anchor.room.floor)
            return (
              <g
                key={zone}
                data-zone={zone}
                className={`scene-entity ${selectedZone && selectedZone !== zone ? 'is-muted' : ''}`}
              >
                <SceneTarget
                  className={`scene-zone risk-${risk} ${selectedZone === zone ? 'chosen' : ''}`}
                  selected={selectedZone === zone}
                  label={`Открыть зону ${zone}`}
                  name={zone}
                  detail={`${riskLabels[risk]} · ${zoneAreas.length} подзоны · Открыть участки и оборудование`}
                  onActivate={() => onZone(anchor.room.building, zone)}
                >
                  {zoneAreas.map((area) => (
                    <g key={area.room.id}>
                      {prism(area.outline, area.elevation, 0.4, area.room.floor, 'scene-area-floor')}
                    </g>
                  ))}
                </SceneTarget>
                {markers(history, [at[0], at[1] + 12])}
              </g>
            )
          })}
        </g>
      ) : null}
      {depth === 'zone' ? (
        <g className="scene-zone-areas">
          {[...areas]
            .sort(
              (a, b) =>
                a.elevation - b.elevation ||
                center(a.outline)[0] + center(a.outline)[1] - center(b.outline)[0] - center(b.outline)[1]
            )
            .map(renderArea)}
        </g>
      ) : null}
      {depth === 'building' ? (
        <g className="scene-building-shell" aria-hidden="true">
          {buildings.map((building) => (
            <polyline key={building.name} points={points([...building.outline, building.outline[0]])} />
          ))}
        </g>
      ) : null}
      {!embedded ? (
        <g className="scene-scale" aria-hidden="true">
          <path d={`M810 604v6h${20 * 2.5 * scale}v-6`} />
          <text x="810" y="630">
            20 м
          </text>
          <text x="50" y="620">
            ↑ С
          </text>
        </g>
      ) : null}
    </svg>
  )
}
