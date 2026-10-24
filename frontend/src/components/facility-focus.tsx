import { X } from 'lucide-react'
import { floorLabels, riskLabels, riskOf, roomEvents, type Floor, type PlanRoom } from '../facility-plan'
import { FacilityScene, type SceneDepth } from './facility-scene'
import type { FacilityAtlasProps } from './facility-atlas'

type Props = FacilityAtlasProps & { floor: Floor | 'all' }
type Scope = { key: string; name: string; depth: SceneDepth; rooms: PlanRoom[]; open: () => void; close?: () => void }

export function FacilityFocus({ floor, onCloseRoom, ...props }: Props) {
  const { rooms, focus, onBuilding, onZone, onCloseZone, onSelect, onIncident, events } = props
  const { building, zone } = focus
  // Ancestors retain their complete plans, including siblings on other physical floors.
  const buildingRooms = rooms.filter((room) => room.building === focus.building)
  const zoneRooms = buildingRooms.filter((room) => room.zone === focus.zone)
  const room = zoneRooms.find((item) => item.id === focus.room)
  const scopes: Scope[] = [{ key: 'site', name: 'Объект', depth: 'site', rooms, open: () => onBuilding('all') }]
  if (building)
    scopes.push({
      key: 'building',
      name: building,
      depth: 'building',
      rooms: buildingRooms,
      open: () => onBuilding(building),
      close: () => onBuilding('all'),
    })
  if (building && zone)
    scopes.push({
      key: 'zone',
      name: zone,
      depth: 'zone',
      rooms: zoneRooms,
      open: () => onZone(building, zone),
      close: onCloseZone,
    })
  if (room)
    scopes.push({
      key: 'room',
      name: room.name,
      depth: 'zone',
      rooms: [room],
      open: () => onSelect(room.id),
      close: onCloseRoom,
    })
  const current = scopes[scopes.length - 1]
  const ancestors = scopes.slice(0, -1)
  const visibleRooms = current.rooms.filter((item) => floor === 'all' || item.floor === floor)
  const renderScene = (scope: Scope, preview = false) => (
    <FacilityScene
      embedded={preview || ancestors.length > 0}
      site={props.site}
      rooms={rooms}
      visibleRooms={preview ? scope.rooms : visibleRooms}
      events={events}
      selected={focus.room}
      selectedBuilding={focus.building}
      selectedZone={focus.zone}
      depth={scope.depth}
      projection={props.curved ? 'arc' : 'isometric'}
      coverage={!preview && props.coverage}
      zoom={preview ? 1 : props.zoom}
      reset={props.reset}
      onBuilding={onBuilding}
      onZone={onZone}
      onSelect={onSelect}
      onIncident={onIncident}
    />
  )
  return (
    <div
      className="facility-focus"
      data-levels={scopes.length}
      data-projection={props.curved ? 'arc' : 'isometric'}
      aria-label="Объём 2: текущий план и предыдущие уровни"
    >
      {ancestors.length ? (
        <nav className="focus-contexts" aria-label="Предыдущие уровни карты">
          {ancestors.map((scope, index) => (
            <div key={scope.key} className="focus-context-card" data-context={scope.key}>
              <button
                className="focus-context-open"
                onClick={scope.open}
                aria-label={`Перейти на уровень: ${scope.name}`}
              >
                <span className="focus-context-title">
                  <span>0{index + 1}</span>
                  <strong>{scope.name}</strong>
                </span>
                <span className="focus-context-preview" inert aria-hidden="true">
                  {renderScene(scope, true)}
                </span>
              </button>
              {scope.close ? (
                <button
                  className="focus-context-close"
                  onClick={scope.close}
                  aria-label={`Закрыть уровень: ${scope.name}`}
                >
                  <X size={12} />
                </button>
              ) : null}
            </div>
          ))}
        </nav>
      ) : null}
      <div className="focus-main-heading">
        <button
          className="focus-current-title"
          onClick={current.open}
          aria-label={`Перейти на уровень: ${current.name}`}
        >
          <span>0{scopes.length}</span>
          <strong>{current.name}</strong>
        </button>
        {room ? <span className="focus-current-floor">{floorLabels[room.floor]}</span> : null}
        {current.close ? (
          <button className="focus-main-close" onClick={current.close} aria-label={`Закрыть уровень: ${current.name}`}>
            <X size={14} />
          </button>
        ) : null}
      </div>
      {room ? (
        <nav className="focus-siblings" aria-label={`Подзоны: ${focus.zone}`}>
          {zoneRooms.map((item) => {
            const risk = riskOf(roomEvents(item, events))
            return (
              <button
                key={item.id}
                className={`risk-${risk}`}
                aria-pressed={item.id === room.id}
                onClick={() => onSelect(item.id)}
                title={`${item.name} · ${floorLabels[item.floor]} · ${riskLabels[risk]}`}
              >
                <i className="risk-dot" />
                {item.name}
                <small>{floorLabels[item.floor]}</small>
              </button>
            )
          })}
        </nav>
      ) : null}
      <div className="focus-main-plan" key={current.key + current.name} data-focus-depth={current.key}>
        {renderScene(current)}
      </div>
    </div>
  )
}
