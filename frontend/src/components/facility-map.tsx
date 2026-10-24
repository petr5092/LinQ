import { useReducer, useRef, useState } from 'react'
import {
  ArrowRight,
  Check,
  ChevronRight,
  Factory,
  Layers3,
  LayoutGrid,
  Map,
  Maximize2,
  Minus,
  Plus,
  RotateCcw,
  Video,
  X,
} from 'lucide-react'
import { cameras as allCameras, type Camera, type SafetyEvent, type Site } from '../data'
import { activeEvents, createRooms, floorLabels, riskLabels, riskOf, roomEvents, type Floor } from '../facility-plan'
import { FacilityScene, type Projection, type SceneDepth } from './facility-scene'
import { FacilityAtlas } from './facility-atlas'
import { FacilityFocus } from './facility-focus'
import { mapNavigation, siteFocus } from '../facility-navigation'
import './facility-map.css'

type Props = {
  site: Site
  events: SafetyEvent[]
  onEvent: (id: string) => void
  onAttention: (cameraIds: string[]) => void
  onCameras: (zone: string) => void
  renderCamera: (camera: Camera, event?: SafetyEvent) => React.ReactNode
}
export function FacilityMap({ site, events, onEvent, onAttention, onCameras, renderCamera }: Props) {
  const detailRef = useRef<HTMLElement>(null)
  const [view, setView] = useState<'scheme' | 'cards'>('scheme')
  const [floor, setFloor] = useState<Floor | 'all'>('all')
  const [focus, dispatch] = useReducer(mapNavigation, siteFocus)
  const [selectedCard, setSelectedCard] = useState<string | null>(null)
  const [projection, setProjection] = useState<Projection | 'focus' | 'arc-focus'>('focus')
  const [sceneReset, setSceneReset] = useState(0)
  const [coverage, setCoverage] = useState(false)
  const [zoom, setZoom] = useState(1)
  const cameras = allCameras.filter((camera) => camera.site === site.id)
  const rooms = createRooms(cameras)
  const building = focus.building ?? 'all'
  const selected = view === 'cards' ? selectedCard : focus.room
  const selectedRoom = rooms.find((room) => room.id === selected)
  const selectedZone = view === 'cards' ? selectedCard?.slice(5) : focus.zone
  const buildingRooms = rooms.filter(
    (room) => (!focus.building || room.building === focus.building) && (floor === 'all' || room.floor === floor)
  )
  const shownRooms = buildingRooms.filter((room) => !focus.zone || room.zone === focus.zone)
  const groups = site.workshops.filter((group) => building === 'all' || group.name === building)
  const detailCameras =
    selectedRoom?.cameras ??
    cameras.filter(
      (camera) =>
        camera.zone === selectedZone &&
        (view === 'cards' || shownRooms.some((room) => room.cameras.some((item) => item.id === camera.id)))
    )
  const detailCameraIds = new Set(detailCameras.map((camera) => camera.id))
  const detailEvents = selectedRoom
    ? roomEvents(selectedRoom, events)
    : events.filter((event) => detailCameraIds.has(event.camera)).sort((a, b) => b.time.localeCompare(a.time))
  const active = activeEvents(events)
  const attentionCameras =
    view === 'scheme'
      ? (selectedRoom?.cameras ?? shownRooms.flatMap((room) => room.cameras))
      : cameras.filter(
          (camera) =>
            groups.some((group) => group.zones.includes(camera.zone)) && (!selectedZone || camera.zone === selectedZone)
        )
  const attentionCameraIds = new Set(attentionCameras.map((camera) => camera.id))
  const affected = new Set(active.filter((event) => attentionCameraIds.has(event.camera)).map((event) => event.zone))
    .size
  const zonePlural = new Intl.PluralRules('ru').select(affected)
  const affectedLabel = `${affected} ${zonePlural === 'one' ? 'зона требует' : zonePlural === 'few' ? 'зоны требуют' : 'зон требуют'} внимания`
  const availableFloors = (['ground', 'mezzanine', 'upper'] as Floor[]).filter((level) =>
    rooms.some((room) => room.floor === level && (!focus.building || room.building === focus.building))
  )
  const resetScene = () => {
    setZoom(1)
    setSceneReset((value) => value + 1)
  }
  const selectBuilding = (value: string) => {
    dispatch(value === 'all' ? { type: 'close-building' } : { type: 'building', building: value })
    setFloor('all')
    setSelectedCard(null)
    resetScene()
  }
  const closeZone = () => {
    dispatch({ type: 'close-zone' })
    setFloor('all')
    resetScene()
  }
  const closeRoom = () => {
    dispatch({ type: 'clear-room' })
    setFloor('all')
    resetScene()
  }
  const selectZone = (buildingName: string, zone: string) => {
    dispatch({ type: 'zone', building: buildingName, zone })
    setFloor('all')
    resetScene()
  }
  const selectRoom = (id: string | null) => {
    if (id?.startsWith('zone:')) {
      setSelectedCard(id)
      return
    }
    const room = rooms.find((room) => room.id === id)
    if (!room) {
      closeZone()
      return
    }
    dispatch({ type: 'room', room })
    setFloor(room.floor)
    resetScene()
  }
  const jumpToIncident = (event: SafetyEvent) => {
    const room = rooms.find((room) => room.cameras.some((camera) => camera.id === event.camera))
    if (room) selectRoom(room.id)
  }
  const depth: SceneDepth = focus.zone ? 'zone' : focus.building ? 'building' : 'site'
  const renderScene = (sceneDepth: SceneDepth, visibleRooms: typeof rooms) => (
    <FacilityScene
      site={site.id}
      rooms={rooms}
      visibleRooms={visibleRooms}
      events={events}
      selected={focus.room}
      selectedBuilding={focus.building}
      selectedZone={focus.zone}
      projection={projection === 'top' ? 'top' : 'isometric'}
      depth={sceneDepth}
      coverage={coverage}
      zoom={sceneDepth === depth ? zoom : 1}
      reset={sceneReset}
      onSelect={selectRoom}
      onBuilding={selectBuilding}
      onZone={selectZone}
      onIncident={jumpToIncident}
    />
  )
  return (
    <section className="object-map" aria-label="Карта объекта">
      <div className="object-map-heading">
        <div>
          <h2>
            Карта объекта{' '}
            <span className="count-badge">{site.workshops.flatMap((group) => group.zones).length} зон</span>
          </h2>
        </div>
        <div className="map-view-toggle" aria-label="Вид карты объекта">
          <button
            className={view === 'cards' ? 'active' : ''}
            aria-pressed={view === 'cards'}
            onClick={() => setView('cards')}
          >
            <LayoutGrid size={14} />
            Карточки
          </button>
          <button
            className={view === 'scheme' ? 'active' : ''}
            aria-pressed={view === 'scheme'}
            onClick={() => {
              setView('scheme')
              if (selectedCard) {
                const room = rooms.find((room) => room.zone === selectedCard.slice(5))
                if (room) selectZone(room.building, room.zone)
              }
            }}
          >
            <Map size={14} />
            Схема
          </button>
        </div>
      </div>
      <div className="plan-toolbar">
        <label>
          <Factory size={14} />
          <select
            aria-label="Корпус на схеме"
            value={building}
            onChange={(event) => selectBuilding(event.target.value)}
          >
            <option value="all">Все корпуса</option>
            {site.workshops.map((group) => (
              <option key={group.name}>{group.name}</option>
            ))}
          </select>
        </label>
        {view === 'scheme' && focus.building ? (
          <label>
            <Layers3 size={14} />
            <select
              aria-label="Этаж на схеме"
              value={floor}
              onChange={(event) => {
                setFloor(event.target.value as Floor | 'all')
                setZoom(1)
                setSceneReset((value) => value + 1)
                dispatch({ type: 'clear-room' })
              }}
            >
              <option value="all">Все этажи</option>
              {availableFloors.map((level) => (
                <option key={level} value={level}>
                  {floorLabels[level]}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <button
          className="plan-live"
          onClick={() => onAttention([...attentionCameraIds])}
          aria-label={`Показать проблемы: ${affectedLabel}`}
        >
          <i />
          {affectedLabel}
          <ChevronRight size={12} />
        </button>
      </div>
      {view === 'cards' ? (
        <div className="plan-cards">
          {groups.flatMap((group) =>
            group.zones.map((zone) => {
              const zoneEvents = events.filter((event) => event.zone === zone)
              const risk = riskOf(zoneEvents)
              const zoneCameras = cameras.filter((camera) => camera.zone === zone)
              return (
                <button
                  key={zone}
                  className={`plan-card risk-${risk} ${selectedZone === zone ? 'chosen' : ''}`}
                  aria-pressed={selectedZone === zone}
                  onClick={() => selectRoom(`zone:${zone}`)}
                >
                  <div>
                    <Factory size={15} />
                    <span className="risk-dot" />
                  </div>
                  <small>{group.name}</small>
                  <strong>{zone}</strong>
                  <span>
                    Камер: {zoneCameras.length} ·{' '}
                    {new Set(rooms.filter((room) => room.zone === zone).map((room) => room.floor)).size} ур.
                  </span>
                  <footer>
                    {risk === 'clear' ? <Check size={12} /> : <span className="risk-dot" />}
                    {riskLabels[risk]}
                    <ChevronRight size={13} />
                  </footer>
                </button>
              )
            })
          )}
        </div>
      ) : (
        <div className="plan-canvas">
          <div className="plan-display-options">
            <div className="scene-view-switch" aria-label="Проекция схемы">
              {(
                [
                  ['top', 'Сверху'],
                  ['isometric', 'Объём 1'],
                  ['focus', 'Объём 2'],
                  ['arc', 'Дуга 1'],
                  ['arc-focus', 'Дуга 2'],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  aria-pressed={projection === value}
                  onClick={() => {
                    setProjection(value)
                    setZoom(1)
                    setSceneReset((value) => value + 1)
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <button aria-pressed={coverage} onClick={() => setCoverage(!coverage)}>
              <Video size={12} />
              Покрытие камер
            </button>
          </div>
          <nav className="plan-breadcrumbs" aria-label="Путь на карте">
            <button onClick={() => selectBuilding('all')}>Объект</button>
            {focus.building ? (
              <>
                <ChevronRight size={12} />
                <button onClick={closeZone}>{focus.building}</button>
              </>
            ) : null}
            {focus.zone ? (
              <>
                <ChevronRight size={12} />
                <button
                  onClick={() => {
                    if (focus.building && focus.zone) selectZone(focus.building, focus.zone)
                  }}
                >
                  {focus.zone}
                </button>
              </>
            ) : null}
            {focus.room ? (
              <>
                <ChevronRight size={12} />
                <span aria-current="location">{selectedRoom?.name}</span>
              </>
            ) : null}
            {focus.building ? (
              <button
                className="plan-back"
                onClick={() => (focus.room ? closeRoom() : focus.zone ? closeZone() : selectBuilding('all'))}
              >
                На уровень выше
              </button>
            ) : null}
          </nav>
          {projection === 'focus' || projection === 'arc-focus' ? (
            <FacilityFocus
              curved={projection === 'arc-focus'}
              site={site.id}
              rooms={rooms}
              buildingRooms={buildingRooms}
              zoneRooms={shownRooms}
              events={events}
              focus={focus}
              floor={floor}
              coverage={coverage}
              zoom={zoom}
              reset={sceneReset}
              onBuilding={selectBuilding}
              onZone={selectZone}
              onSelect={selectRoom}
              onIncident={jumpToIncident}
              onCloseZone={closeZone}
              onCloseRoom={closeRoom}
            />
          ) : projection === 'isometric' || projection === 'arc' ? (
            <FacilityAtlas
              curved={projection === 'arc'}
              site={site.id}
              rooms={rooms}
              buildingRooms={buildingRooms}
              zoneRooms={shownRooms}
              events={events}
              focus={focus}
              coverage={coverage}
              zoom={zoom}
              reset={sceneReset}
              onBuilding={selectBuilding}
              onZone={selectZone}
              onSelect={selectRoom}
              onIncident={jumpToIncident}
              onCloseZone={closeZone}
              onCloseRoom={closeRoom}
            />
          ) : (
            <div className="plan-viewport">{renderScene(depth, depth === 'site' ? rooms : shownRooms)}</div>
          )}
          <div className="plan-canvas-bottom">
            <label className="plan-room-picker">
              <Map size={13} />
              <select
                aria-label="Участок на схеме"
                value={selectedRoom?.id ?? ''}
                onChange={(event) => selectRoom(event.target.value || null)}
              >
                <option value="">Выбрать участок или камеру…</option>
                {(projection !== 'top' && focus.zone
                  ? rooms.filter((room) => room.zone === focus.zone && room.building === focus.building)
                  : shownRooms
                ).map((room) => (
                  <option key={room.id} value={room.id}>
                    {room.building} · {room.zone} · {floorLabels[room.floor]} ·{' '}
                    {room.cameras.map((camera) => camera.id).join(', ')} ·{' '}
                    {riskLabels[riskOf(roomEvents(room, events))]}
                  </option>
                ))}
              </select>
            </label>
            <div>
              <button
                aria-label="Уменьшить схему"
                disabled={zoom <= 1}
                onClick={() => setZoom((value) => Math.max(1, value - 0.25))}
              >
                <Minus size={13} />
              </button>
              <span>{Math.round(zoom * 100)}%</span>
              <button
                aria-label="Увеличить схему"
                disabled={zoom >= 2}
                onClick={() => setZoom((value) => Math.min(2, value + 0.25))}
              >
                <Plus size={13} />
              </button>
              <button
                aria-label="Сбросить ракурс и масштаб"
                onClick={() => {
                  setZoom(1)
                  setSceneReset((value) => value + 1)
                }}
              >
                <RotateCcw size={13} />
              </button>
            </div>
          </div>
        </div>
      )}
      {cameras.some((camera) => !camera.online) ? (
        <p className="plan-signal-note">
          <Video size={11} />
          {cameras.filter((camera) => !camera.online).length} камера без сигнала · подсветка учитывает последнее
          активное событие
        </p>
      ) : null}
      <div className="plan-legend">
        {(['clear', 'notice', 'warning', 'critical'] as const).map((risk) => (
          <span key={risk} className={`risk-${risk}`}>
            <i />
            {riskLabels[risk]}
          </span>
        ))}
      </div>
      {selectedZone ? (
        <section ref={detailRef} className="plan-detail" aria-label="Выбранная зона">
          <div className="plan-detail-heading">
            <div>
              <small>
                {selectedRoom ? `${selectedRoom.building} / ${floorLabels[selectedRoom.floor]}` : 'Все уровни зоны'}
              </small>
              <h3>
                {selectedZone}
                {selectedRoom ? ` · ${selectedRoom.name}` : ''}
              </h3>
            </div>
            <button
              className="icon-button"
              aria-label="Закрыть выбранную зону"
              onClick={() => (view === 'cards' ? setSelectedCard(null) : closeZone())}
            >
              <X size={16} />
            </button>
          </div>
          <div className="plan-detail-summary">
            <span className={`plan-risk-label risk-${riskOf(detailEvents)}`}>
              <i className="risk-dot" />
              {riskLabels[riskOf(detailEvents)]}
            </span>
            <span>
              {detailCameras.filter((camera) => camera.online).length}/{detailCameras.length} камер онлайн
            </span>
            <button onClick={() => onCameras(selectedZone)}>
              Все камеры зоны <ArrowRight size={13} />
            </button>
          </div>
          <div className="plan-camera-previews">
            {detailCameras.map((camera) => {
              const event = detailEvents.find((item) => item.camera === camera.id)
              return (
                <div key={camera.id}>
                  {renderCamera(camera, event)}
                  <div>
                    <strong>{camera.id}</strong>
                    <span title={camera.name}>{camera.name}</span>
                    {event ? (
                      <button aria-label={`Открыть событие ${event.id}`} onClick={() => onEvent(event.id)}>
                        <Maximize2 size={12} />
                      </button>
                    ) : null}
                  </div>
                </div>
              )
            })}
          </div>
          <div className="plan-zone-events">
            <strong>
              Последние события зоны <span>{detailEvents.length}</span>
            </strong>
            {detailEvents.length ? (
              detailEvents.slice(0, 4).map((event) => (
                <button key={event.id} onClick={() => onEvent(event.id)}>
                  <i className={`event-risk-dot risk-${riskOf([event])}`} />
                  <span>
                    {event.title}
                    <small>
                      {event.camera} ·{' '}
                      {event.status === 'resolved'
                        ? 'Устранено'
                        : event.status === 'dismissed'
                          ? 'Ложное срабатывание'
                          : event.status === 'working'
                            ? 'В работе'
                            : 'Новое'}
                    </small>
                  </span>
                  <time>{event.time.slice(0, 5)}</time>
                  <ChevronRight size={13} />
                </button>
              ))
            ) : (
              <p>В этой зоне событий нет. Камеры ведут наблюдение.</p>
            )}
          </div>
        </section>
      ) : null}
    </section>
  )
}
