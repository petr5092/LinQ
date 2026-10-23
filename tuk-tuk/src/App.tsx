import { useEffect, useState } from 'react'
import {
  Activity,
  ArrowDownLeft,
  ArrowDownToLine,
  ArrowRight,
  Bell,
  BellRing,
  CalendarDays,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  ChevronsUpDown,
  CircleCheck,
  CircleHelp,
  Clock3,
  Copy,
  DoorOpen,
  Factory,
  Fence,
  HardHat,
  LayoutDashboard,
  LayoutGrid,
  List,
  Map,
  MapPin,
  Maximize2,
  Menu,
  Pause,
  Phone,
  Play,
  Plus,
  Radio,
  Search,
  Settings2,
  ShieldCheck,
  ShieldX,
  SlidersHorizontal,
  Sparkles,
  TriangleAlert,
  UserRound,
  Video,
  Volume2,
  VolumeX,
  Warehouse,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import {
  accounts,
  cameras,
  initialEvents,
  sites,
  statusLabels,
  zoneRules,
  zoneWorkshop,
  type EventStatus,
  type SafetyEvent,
  type SiteId,
} from './data'

const navItems = [
  { key: 'overview', label: 'Обзор', icon: LayoutDashboard },
  { key: 'cameras', label: 'Камеры', icon: Video },
  { key: 'events', label: 'Журнал событий', icon: List },
  { key: 'zones', label: 'Зоны и правила', icon: Map },
  { key: 'access', label: 'Контроль доступа', icon: DoorOpen },
  { key: 'analytics', label: 'Аналитика', icon: Activity },
]
const pageTitles: Record<string, string> = {
  overview: 'Обзор безопасности',
  cameras: 'Видеомониторинг',
  events: 'Журнал событий',
  zones: 'Зоны и правила',
  access: 'Контроль доступа',
  analytics: 'Аналитика безопасности',
  settings: 'Настройки сервиса',
}
const pageDescriptions: Record<string, string> = {
  overview: 'Всё, что происходит на объекте, — в одном месте.',
  cameras: 'Камеры и события на производственной площадке.',
  events: 'История обнаружений и работа с нарушениями.',
  zones: 'Сценарии контроля для каждого участка предприятия.',
  access: 'Проверка СИЗ и допусков сотрудников перед проходом.',
  analytics: 'Нарушения, реакция и динамика безопасности.',
  settings: 'Параметры оповещений и демонстрационной системы.',
}
function isOpen(e: SafetyEvent) {
  return e.status === 'new' || e.status === 'working'
}
function SeverityBadge({ severity, short = false }: { severity: SafetyEvent['severity']; short?: boolean }) {
  return (
    <span className={`severity-badge ${severity}`}>
      <i />
      {severity === 'critical' ? (short ? 'Критично' : 'Критическое') : severity === 'warning' ? 'Внимание' : 'Информация'}
    </span>
  )
}
function StatusBadge({ status }: { status: EventStatus }) {
  return (
    <span className={`status-badge status-${status}`}>
      <i />
      {statusLabels[status]}
    </span>
  )
}
function StatSpark({ color = 'blue', inverse = false }: { color?: string; inverse?: boolean }) {
  return (
    <svg className={`stat-spark ${color}`} viewBox="0 0 94 38" aria-hidden="true">
      <path
        className="spark-fill"
        d={
          inverse
            ? 'M0 10L10 14L18 9L27 22L36 19L45 28L54 23L63 28L72 25L82 31L94 26V38H0Z'
            : 'M0 30L9 28L17 32L26 18L34 24L44 16L53 20L64 12L72 15L83 5L94 7V38H0Z'
        }
      />
      <path
        className="spark-line"
        d={
          inverse
            ? 'M0 10L10 14L18 9L27 22L36 19L45 28L54 23L63 28L72 25L82 31L94 26'
            : 'M0 30L9 28L17 32L26 18L34 24L44 16L53 20L64 12L72 15L83 5L94 7'
        }
      />
    </svg>
  )
}
function CameraView({
  event,
  image,
  online = true,
  large = false,
  showBoxes = true,
}: {
  event?: SafetyEvent
  image: string
  online?: boolean
  large?: boolean
  showBoxes?: boolean
}) {
  const active = event && isOpen(event)
  return (
    <div
      className={`camera-view ${large ? 'large' : ''} ${online ? '' : 'offline'}`}
      style={{ backgroundImage: `url(/images/${image}.png)` }}
    >
      <div className="camera-tint" />
      <div className="camera-overlay-top">
        <span className={`live-label ${online ? '' : 'stopped'}`}>
          <i />
          {online ? 'LIVE' : 'НЕТ СИГНАЛА'}
        </span>
        <span className="camera-timestamp">23.10.2026 {event?.time ?? '14:32:10'}</span>
      </div>
      {active && online && showBoxes ? (
        <div
          className={`detect-box ${event.severity}`}
          style={{ left: `${event.box[0]}%`, top: `${event.box[1]}%`, width: `${event.box[2]}%`, height: `${event.box[3]}%` }}
        >
          <span>{event.type === 'environment' ? 'Объект' : event.type === 'access' ? 'Контроль доступа' : event.title} · 98%</span>
          <b className="box-corner tl" />
          <b className="box-corner tr" />
          <b className="box-corner bl" />
          <b className="box-corner br" />
        </div>
      ) : null}
      {!online ? (
        <div className="offline-content">
          <Video size={25} />
          <strong>Соединение потеряно</strong>
          <span>Последний сигнал в 14:21</span>
        </div>
      ) : null}
      <span className="camera-demo">ДЕМОНСТРАЦИЯ</span>
      {online ? (
        <span className="camera-ai">
          <Sparkles size={10} /> LinQ AI
        </span>
      ) : null}
    </div>
  )
}
function EventIcon({ event }: { event: SafetyEvent }) {
  const Icon = event.type === 'environment' ? Warehouse : event.type === 'access' ? ShieldX : HardHat
  return (
    <span className={`event-icon ${event.severity}`}>
      <Icon size={16} />
    </span>
  )
}
function Empty({ text }: { text: string }) {
  return (
    <div className="empty-state">
      <CircleCheck size={30} />
      <strong>{text}</strong>
      <span>Попробуйте изменить параметры фильтра.</span>
    </div>
  )
}
function pluralRu(count: number, one: string, few: string, many: string) {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}
const zoneIcons = [Factory, Warehouse, DoorOpen, Fence, Warehouse, HardHat]
function readEvents() {
  try {
    const saved = JSON.parse(localStorage.getItem('tuk-tuk-events-v1') || 'null')
    if (
      Array.isArray(saved) &&
      saved.every((x) => typeof x.id === 'string' && ['new', 'working', 'resolved', 'dismissed'].includes(x.status))
    )
      return initialEvents.map((e) => ({ ...e, status: saved.find((x) => x.id === e.id)?.status ?? e.status }))
  } catch {
    /* Browser storage may be unavailable. */
  }
  return initialEvents
}
export default function App() {
  const [page, setPage] = useState('overview')
  const [events, setEvents] = useState<SafetyEvent[]>(readEvents)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [zone, setZone] = useState('all')
  const [siteId, setSiteId] = useState<SiteId>('north')
  const [workshop, setWorkshop] = useState('all')
  const [accountId, setAccountId] = useState('dispatcher')
  const [search, setSearch] = useState('')
  const [severity, setSeverity] = useState('all')
  const [status, setStatus] = useState('all')
  const [period, setPeriod] = useState('today')
  const [view, setView] = useState('grid')
  const [mapView, setMapView] = useState(false)
  const [feedTab, setFeedTab] = useState('all')
  const [feedUnread, setFeedUnread] = useState(true)
  const [seen, setSeen] = useState<string[]>([])
  const [sound, setSound] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [modal, setModal] = useState<'help' | 'demo' | null>(null)
  const [toast, setToast] = useState('')
  const [showBoxes, setShowBoxes] = useState(true)
  const [playing, setPlaying] = useState(false)
  const [rulesEnabled, setRulesEnabled] = useState<Record<string, boolean>>({})
  const activeSite = sites.find((site) => site.id === siteId) ?? sites[0]
  const activeAccount = accounts.find((account) => account.id === accountId) ?? accounts[0]
  const siteCameras = cameras.filter((camera) => camera.site === siteId)
  const siteEvents = events.filter((event) => event.site === siteId)
  const siteZones = activeSite.workshops.flatMap((group) => group.zones)
  const workshopZones = activeSite.workshops
    .filter((group) => workshop === 'all' || group.name === workshop)
    .flatMap((group) => group.zones)
  const offlineCount = siteCameras.filter((camera) => !camera.online).length
  const selected = events.find((e) => e.id === selectedId)
  const openEvents = siteEvents.filter(isOpen)
  const criticalCount = openEvents.filter((e) => e.severity === 'critical').length
  const notify = (message: string) => setToast(message)
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(''), 4200)
    return () => clearTimeout(t)
  }, [toast])
  useEffect(() => {
    try {
      localStorage.setItem('tuk-tuk-events-v1', JSON.stringify(events.map(({ id, status }) => ({ id, status }))))
    } catch {
      /* Session state remains usable. */
    }
  }, [events])
  useEffect(() => {
    document.title = `Тук-Тук · ${pageTitles[page]}`
  }, [page])
  const updateStatus = (id: string, value: EventStatus) => {
    setEvents((list) => list.map((e) => (e.id === id ? { ...e, status: value } : e)))
    notify(
      value === 'working'
        ? 'Событие взято в работу. Ответственный назначен.'
        : value === 'resolved'
          ? 'Нарушение отмечено как устранённое.'
          : 'Событие помечено как ложное срабатывание.'
    )
  }
  const navigate = (key: string) => {
    window.scrollTo({ top: 0, behavior: 'instant' })
    setPage(key)
    setZone('all')
    setSearch('')
    setSeverity('all')
    setStatus('all')
    setPeriod('today')
    setWorkshop('all')
  }
  const switchSite = (id: SiteId) => {
    if (id === siteId) return
    setSiteId(id)
    setWorkshop('all')
    setZone('all')
    setSearch('')
    setSeverity('all')
    setStatus('all')
    setPeriod('today')
    const next = sites.find((site) => site.id === id)
    if (next) notify(`Площадка: ${next.name}`)
  }
  const switchAccount = (id: string) => {
    if (id === accountId) return
    setAccountId(id)
    const next = accounts.find((account) => account.id === id)
    if (next) notify(`Аккаунт: ${next.role} · ${next.name}`)
  }
  const dateMatch = (e: SafetyEvent) => (period === 'last-hour' ? e.time >= '14:00:00' : true)
  const filteredEvents = siteEvents.filter(
    (e) =>
      (zone === 'all' || e.zone === zone) &&
      (severity === 'all' || e.severity === severity) &&
      (status === 'all' || (status === 'open' ? isOpen(e) : e.status === status)) &&
      dateMatch(e) &&
      `${e.title} ${e.id} ${e.camera} ${e.employee?.name ?? ''}`.toLowerCase().includes(search.toLowerCase())
  )
  const filteredCameras = siteCameras.filter(
    (c) =>
      (zone === 'all' || c.zone === zone) &&
      (workshop === 'all' || c.workshop === workshop) &&
      `${c.name} ${c.id} ${c.zone} ${c.workshop}`.toLowerCase().includes(search.toLowerCase())
  )
  const visibleCameras = page === 'cameras' ? filteredCameras : filteredCameras.slice(0, 6)
  const feedEvents = siteEvents.filter(
    (e) => (feedTab === 'critical' ? e.severity === 'critical' : true) && (feedUnread ? !seen.includes(e.id) : true)
  )
  const demoOptions = siteEvents
    .filter((event) => initialEvents.some((source) => source.id === event.id))
    .slice(0, 3)
    .map((event) => ({
      label: event.title,
      id: event.id,
      icon: event.type === 'environment' ? Warehouse : event.type === 'access' ? ShieldX : HardHat,
    }))
  const exportCSV = () => {
    const fields = [
      ['ID', 'Время', 'Зона', 'Камера', 'Событие', 'Важность', 'Статус', 'Сотрудник'],
      ...filteredEvents.map((e) => [
        e.id,
        e.time,
        e.zone,
        e.camera,
        e.title,
        e.severity,
        statusLabels[e.status],
        e.employee?.name ?? 'Не определён',
      ]),
    ]
    const blob = new Blob(['\ufeff' + fields.map((row) => row.map((s) => '"' + s.replaceAll('"', '""') + '"').join(';')).join('\n')], {
      type: 'text/csv;charset=utf-8;',
    })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'tuk-tuk-events-2026-10-23.csv'
    a.click()
    URL.revokeObjectURL(a.href)
    notify('Журнал событий выгружен в CSV.')
  }
  const stats = (
    <div className="stats-grid">
      <button
        className="stat-card"
        onClick={() => {
          navigate('events')
          setStatus('open')
        }}
      >
        <span className="stat-label">
          Требуют реакции <TriangleAlert size={15} />
        </span>
        <div className="stat-value">
          {openEvents.length}
          <span className="stat-value-tag red">{criticalCount} критических</span>
        </div>
        <div className="stat-note">За текущую смену</div>
        <StatSpark color="orange" />
      </button>
      <button className="stat-card" onClick={() => navigate('cameras')}>
        <span className="stat-label">
          Камеры онлайн <Video size={15} />
        </span>
        <div className="stat-value">
          {siteCameras.filter((c) => c.online).length}
          <span className="stat-total">/ {siteCameras.length}</span>
          <span className="status-dot green" />
        </div>
        <div className="stat-note">
          {offlineCount} {pluralRu(offlineCount, 'камера', 'камеры', 'камер')} без сигнала
        </div>
        <StatSpark color="green" />
      </button>
      <button
        className="stat-card"
        onClick={() => {
          navigate('events')
          setStatus('resolved')
        }}
      >
        <span className="stat-label">
          Устранено за смену <ShieldCheck size={15} />
        </span>
        <div className="stat-value">
          {siteEvents.filter((e) => e.status === 'resolved').length}
          <span className="stat-value-tag green">
            <ArrowDownLeft size={12} /> 2 за последний час
          </span>
        </div>
        <div className="stat-note">Безопасность в действии</div>
        <StatSpark color="blue" />
      </button>
      <button className="stat-card" onClick={() => navigate('analytics')}>
        <span className="stat-label">
          Время реакции <Clock3 size={15} />
        </span>
        <div className="stat-value">
          1<span className="stat-unit">м</span> 42<span className="stat-unit">с</span>
        </div>
        <div className="stat-note">
          <span className="positive">↓ 18%</span> к прошлой смене
        </div>
        <StatSpark inverse color="blue" />
      </button>
    </div>
  )
  const zoneFilter = (
    <label className="select-wrap">
      <MapPin size={15} />
      <select aria-label="Фильтр по зоне" value={zone} onChange={(e) => setZone(e.target.value)}>
        <option value="all">Все зоны</option>
        {workshopZones.map((z) => (
          <option key={z}>{z}</option>
        ))}
      </select>
      <ChevronDown size={13} />
    </label>
  )
  const workshopFilter = (
    <label className="select-wrap">
      <Factory size={14} />
      <select
        aria-label="Фильтр по цеху"
        value={workshop}
        onChange={(e) => {
          const next = e.target.value
          setWorkshop(next)
          if (
            zone !== 'all' &&
            next !== 'all' &&
            !activeSite.workshops.some((group) => group.name === next && group.zones.includes(zone))
          ) {
            setZone('all')
          }
        }}
      >
        <option value="all">Все цеха</option>
        {activeSite.workshops.map((group) => (
          <option key={group.name} value={group.name}>
            {group.name}
          </option>
        ))}
      </select>
      <ChevronDown size={12} />
    </label>
  )
  const searchInput = (
    <label className="search-input">
      <Search size={15} />
      <input
        aria-label="Поиск"
        placeholder={page === 'events' ? 'Событие, сотрудник или ID' : 'Найти камеру'}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      {search ? (
        <button aria-label="Очистить поиск" onClick={() => setSearch('')}>
          <X size={13} />
        </button>
      ) : null}
    </label>
  )
  const cameraGrid = (
    <>
      <div className="section-heading">
        <div>
          <h2>
            {page === 'overview' ? 'Видеомониторинг' : 'Камеры объекта'} <span className="count-badge">{filteredCameras.length}</span>
          </h2>
          <p>Контроль в реальном времени</p>
        </div>
        <div className="section-heading-actions">
          <span className="live-text">
            <i /> Прямой эфир
          </span>
          <button
            className={`icon-button ${showBoxes ? 'selected' : ''}`}
            title="Показать или скрыть детекции"
            aria-label="Показать или скрыть детекции"
            aria-pressed={showBoxes}
            onClick={() => setShowBoxes((v) => !v)}
          >
            <Sparkles size={16} />
          </button>
        </div>
      </div>
      <div className="camera-toolbar">
        <div className="filter-controls">
          {workshopFilter}
          {zoneFilter}
          {searchInput}
        </div>
        <div className="view-switch" aria-label="Вид камер">
          <button
            aria-label="Сетка"
            aria-pressed={view === 'grid'}
            className={view === 'grid' ? 'active' : ''}
            onClick={() => setView('grid')}
          >
            <LayoutGrid size={16} />
          </button>
          <button
            aria-label="Список"
            aria-pressed={view === 'list'}
            className={view === 'list' ? 'active' : ''}
            onClick={() => setView('list')}
          >
            <List size={17} />
          </button>
        </div>
      </div>
      <div className={`camera-grid ${view === 'list' ? 'camera-list' : ''}`}>
        {visibleCameras.map((camera) => {
          const event = events.find((e) => e.id === camera.event)
          return (
            <article className="camera-card" key={camera.id}>
              <button
                className="camera-click"
                aria-label={`Открыть камеру ${camera.id}: ${camera.name}`}
                onClick={() => setSelectedId(camera.event ?? null)}
              >
                <CameraView event={event} image={camera.image} online={camera.online} showBoxes={showBoxes} />
                <span className="expand-camera">
                  <Maximize2 size={16} />
                </span>
              </button>
              <div className="camera-card-body">
                <div className="camera-card-title">
                  <span className={`small-dot ${camera.online ? 'green' : 'gray'}`} />
                  <strong>{camera.name}</strong>
                  <span className="camera-id">{camera.id}</span>
                </div>
                <div className="camera-card-bottom">
                  <span>{camera.zone}</span>
                  {event && isOpen(event) ? (
                    <button className={`camera-event ${event.severity}`} onClick={() => setSelectedId(event.id)}>
                      <TriangleAlert size={12} />
                      {event.type === 'environment' ? 'Препятствие в проходе' : event.type === 'access' ? 'Нарушение доступа' : event.title}
                      <ChevronRight size={12} />
                    </button>
                  ) : (
                    <span className="clear-label">
                      <Check size={12} /> Без нарушений
                    </span>
                  )}
                </div>
              </div>
            </article>
          )
        })}
      </div>
      {filteredCameras.length === 0 ? <Empty text="Камеры не найдены" /> : null}
      <div className="camera-footer">
        <span>
          <span className="small-dot green" /> Обновлено в 14:32:10
        </span>
        {page === 'overview' && filteredCameras.length > visibleCameras.length ? (
          <button className="camera-more" onClick={() => navigate('cameras')}>
            Показаны {visibleCameras.length} из {filteredCameras.length} · Все камеры <ArrowRight size={11} />
          </button>
        ) : (
          <span>Изображения и события — демоданные</span>
        )}
      </div>
    </>
  )
  const eventTable = (list: SafetyEvent[], compact = false) => (
    <div className="event-table-wrap">
      <table className="event-table">
        <thead>
          <tr>
            <th>Событие</th>
            <th>Зона / камера</th>
            <th>
              Время <ChevronDown size={11} />
            </th>
            <th>Статус</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {list.map((e) => (
            <tr key={e.id} onClick={() => setSelectedId(e.id)}>
              <td>
                <button className="event-table-name" onClick={() => setSelectedId(e.id)}>
                  <EventIcon event={e} />
                  <span>
                    <strong>{e.title}</strong>
                    <span>
                      {e.employee?.name ?? (e.type === 'environment' ? 'Объект среды' : 'Личность не определена')}
                      <small> · {e.id}</small>
                    </span>
                  </span>
                </button>
              </td>
              <td>
                <span>{e.zone}</span>
                <small>{e.camera}</small>
              </td>
              <td>
                <span>{e.time}</span>
                <small>23 октября</small>
              </td>
              <td>
                <StatusBadge status={e.status} />
              </td>
              <td>
                <ChevronRight size={15} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {list.length === 0 ? <Empty text="Событий по этим параметрам нет" /> : null}
      {!compact ? (
        <div className="table-footer">
          Показано {list.length} из {siteEvents.length} событий <span>23 октября 2026 · текущая смена</span>
        </div>
      ) : null}
    </div>
  )
  const map = (
    <div className="facility-map">
      <div className="map-top">
        <span>
          <Map size={15} /> {activeSite.name}
        </span>
        <span>Схема зон · демо</span>
      </div>
      <div className="map-roads" />
      {siteZones.map((z, i) => {
        const count = openEvents.filter((e) => e.zone === z).length
        const Icon = zoneIcons[i % zoneIcons.length]
        return (
          <button
            className={`map-zone map-zone-${i} ${count ? 'alert' : ''}`}
            key={z}
            onClick={() => {
              setWorkshop('all')
              setZone(z)
              setMapView(false)
            }}
          >
            <Icon size={27} />
            <strong>{z}</strong>
            <span>
              {count} {count === 1 ? 'событие' : 'событий'}
            </span>
            <b>{i + 1}</b>
          </button>
        )
      })}
      <div className="map-legend">
        <span className="small-dot orange" /> Требует внимания <span className="small-dot blue" /> Зона под контролем
      </div>
    </div>
  )
  return (
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <aside className="sidebar">
        <div className="brand-row">
          <a
            className="brand"
            href="#overview"
            onClick={(e) => {
              e.preventDefault()
              navigate('overview')
            }}
          >
            <span>
              Тук-Тук<span className="brand-dot">.</span>
            </span>
          </a>
          <button
            className="sidebar-toggle"
            aria-label={collapsed ? 'Развернуть меню' : 'Свернуть меню'}
            onClick={() => setCollapsed((v) => !v)}
          >
            <Menu size={16} />
          </button>
        </div>
        <label className="facility-select">
          <span className="facility-symbol">
            <Factory size={17} />
          </span>
          <div>
            <strong>{activeSite.name}</strong>
            <span>{activeSite.subtitle}</span>
          </div>
          <ChevronsUpDown size={13} />
          <select aria-label="Выбор площадки" value={siteId} onChange={(e) => switchSite(e.target.value as SiteId)}>
            {sites.map((site) => (
              <option key={site.id} value={site.id}>
                {site.name} · {site.subtitle}
              </option>
            ))}
          </select>
        </label>
        <div className="nav-caption">РАБОЧЕЕ ПРОСТРАНСТВО</div>
        <nav aria-label="Основная навигация">
          {navItems.map(({ key, label, icon: Icon }) => (
            <button key={key} onClick={() => navigate(key)} className={`nav-item ${page === key ? 'active' : ''}`} title={label}>
              <Icon size={18} />
              <span>{label}</span>
              {key === 'events' ? <b>{openEvents.length}</b> : null}
              {key === 'cameras' ? <small>{siteCameras.length}</small> : null}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button className={`nav-item ${page === 'settings' ? 'active' : ''}`} onClick={() => navigate('settings')}>
            <Settings2 size={18} />
            <span>Настройки</span>
          </button>
          <button className="nav-item" onClick={() => setModal('help')}>
            <CircleHelp size={18} />
            <span>Помощь и поддержка</span>
            <ArrowRight size={14} />
          </button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="profile" aria-label="Переключить аккаунт">
                <div className="avatar">{activeAccount.initials}</div>
                <div>
                  <strong>{activeAccount.name}</strong>
                  <span>{activeAccount.role}</span>
                </div>
                <ChevronsUpDown size={13} />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="top" align="start" sideOffset={8} className="account-menu">
              {accounts.map((account) => (
                <DropdownMenuItem key={account.id} className="account-item" onSelect={() => switchAccount(account.id)}>
                  <span className="avatar">{account.initials}</span>
                  <span className="account-text">
                    <strong>{account.role}</strong>
                    <small>
                      {account.name} · {account.note}
                    </small>
                  </span>
                  {account.id === accountId ? <Check size={14} /> : null}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>
      <main className="workspace">
        <div className="breadcrumbs">
          <Factory size={13} />
          <span>{activeSite.subtitle}</span>
          <ChevronRight size={12} />
          <span className="current">{pageTitles[page]}</span>
        </div>
        <div className="page-heading">
          <div>
            <h1>{pageTitles[page]}</h1>
            <p>{pageDescriptions[page]}</p>
          </div>
          <div className="page-actions">
            <label className="date-select">
              <CalendarDays size={15} />
              <select aria-label="Период" value={period} onChange={(e) => setPeriod(e.target.value)}>
                <option value="today">23 октября, сегодня</option>
                <option value="last-hour">Последний час</option>
              </select>
              <ChevronDown size={12} />
            </label>
            <Button size="sm" variant="outline" onClick={exportCSV}>
              <ArrowDownToLine size={14} />
              <span>Экспорт</span>
            </Button>
          </div>
        </div>
        <div className="page-body">
          {page === 'overview' ? (
            <>
              {stats}
              <div className="overview-tabs">
                <button className={!mapView ? 'active' : ''} onClick={() => setMapView(false)}>
                  <Video size={16} /> Камеры
                </button>
                <button className={mapView ? 'active' : ''} onClick={() => setMapView(true)}>
                  <Map size={16} /> Карта объекта
                </button>
                <span>
                  <ShieldCheck size={13} /> Система работает штатно
                </span>
              </div>
              {mapView ? map : cameraGrid}
              <section className="recent-events">
                <div className="section-heading">
                  <div>
                    <h2>Последние события</h2>
                    <p>Обнаружения за текущую смену</p>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => navigate('events')}>
                    Весь журнал <ArrowRight size={14} />
                  </Button>
                </div>
                {eventTable(siteEvents.filter(dateMatch).slice(0, 4), true)}
              </section>
            </>
          ) : null}
          {page === 'cameras' ? <>{cameraGrid}</> : null}
          {page === 'events' ? (
            <>
              <div className="journal-summary">
                <span className="live-text">
                  <i /> {openEvents.length} событий требуют реакции
                </span>
                <span>
                  {criticalCount} критических · {siteEvents.filter((e) => e.status === 'working').length} в работе
                </span>
              </div>
              <div className="journal-filters">
                {searchInput}
                {zoneFilter}
                <label className="select-wrap">
                  <SlidersHorizontal size={14} />
                  <select aria-label="Важность" value={severity} onChange={(e) => setSeverity(e.target.value)}>
                    <option value="all">Любая важность</option>
                    <option value="critical">Критические</option>
                    <option value="warning">Внимание</option>
                  </select>
                  <ChevronDown size={12} />
                </label>
                <label className="select-wrap">
                  <select aria-label="Статус события" value={status} onChange={(e) => setStatus(e.target.value)}>
                    <option value="all">Все статусы</option>
                    <option value="open">Требуют реакции</option>
                    {Object.entries(statusLabels).map(([v, l]) => (
                      <option value={v} key={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={12} />
                </label>
              </div>
              {eventTable(filteredEvents)}
            </>
          ) : null}
          {page === 'zones' ? (
            <>
              <div className="info-banner">
                <ShieldCheck size={19} />
                <div>
                  <strong>У каждой зоны — свои правила безопасности</strong>
                  <p>Включайте сценарии для участка. Изменения в прототипе применяются только к настройкам интерфейса.</p>
                </div>
              </div>
              <div className="zones-grid">
                {siteZones.map((z, i) => {
                  const Icon = zoneIcons[i % zoneIcons.length]
                  const cameraCount = siteCameras.filter((c) => c.zone === z).length
                  const zoneEventCount = openEvents.filter((e) => e.zone === z).length
                  return (
                    <section className="zone-card" key={z}>
                      <div className="zone-header">
                        <span className="zone-symbol">
                          <Icon size={21} />
                        </span>
                        <div>
                          <h2>{z}</h2>
                          <p>
                            {zoneWorkshop[z]} · {cameraCount} {pluralRu(cameraCount, 'камера', 'камеры', 'камер')} · {zoneEventCount}{' '}
                            {pluralRu(zoneEventCount, 'активное событие', 'активных события', 'активных событий')}
                          </p>
                        </div>
                        <button
                          className="icon-button"
                          aria-label={`Камеры зоны ${z}`}
                          onClick={() => {
                            navigate('cameras')
                            setZone(z)
                          }}
                        >
                          <ArrowRight size={16} />
                        </button>
                      </div>
                      {zoneRules[z].map((rule) => (
                        <div className="rule-row" key={rule}>
                          <span>{rule}</span>
                          <Switch
                            aria-label={`${z}: ${rule}`}
                            checked={rulesEnabled[z + rule] ?? true}
                            onCheckedChange={(v) => setRulesEnabled((p) => ({ ...p, [z + rule]: v }))}
                          />
                        </div>
                      ))}
                    </section>
                  )
                })}
              </div>
            </>
          ) : null}
          {page === 'access' ? (
            <>
              <div className="access-intro">
                <div className="access-shield">
                  <ShieldCheck size={28} />
                </div>
                <div>
                  <h2>Проход начинается с безопасности</h2>
                  <p>СКУД проверяет право доступа, ИИ — соответствие требованиям зоны.</p>
                </div>
                <span className="connected">
                  <i /> СКУД подключена
                </span>
              </div>
              <div className="access-stats">
                <div>
                  <span>Проверено за смену</span>
                  <strong>186</strong>
                </div>
                <div>
                  <span>Отказы в проходе</span>
                  <strong>2</strong>
                </div>
                <div>
                  <span>Причина: нет допуска</span>
                  <strong>1</strong>
                </div>
                <div>
                  <span>Причина: нет СИЗ</span>
                  <strong>1</strong>
                </div>
              </div>
              <div className="section-heading">
                <div>
                  <h2>Контроль на проходной</h2>
                  <p>Отказы и попытки прохода · 23 октября</p>
                </div>
                <span className="tag-neutral">Демонстрационные данные</span>
              </div>
              {siteEvents
                .filter((e) => e.type === 'access')
                .map((e) => (
                  <button className="access-event" key={e.id} onClick={() => setSelectedId(e.id)}>
                    <span className="access-thumb" style={{ backgroundImage: `url(/images/${e.image}.png)` }} />
                    <div>
                      <div className="access-event-title">
                        <strong>{e.title}</strong>
                        <SeverityBadge severity={e.severity} />
                      </div>
                      <p>{e.description}</p>
                      <span>
                        <UserRound size={13} />
                        {e.employee?.name} <b>·</b> {e.employee?.number} <b>·</b> {e.time}
                      </span>
                    </div>
                    <ChevronRight size={18} />
                  </button>
                ))}
              <div className="access-explainer">
                <div>
                  <ShieldX size={20} />
                  <h3>Нет допуска</h3>
                  <p>Попытка несанкционированного прохода. Доступ заблокирован, информация передаётся охране.</p>
                </div>
                <div>
                  <HardHat size={20} />
                  <h3>Не соблюдены требования</h3>
                  <p>Проход отклонён до выдачи необходимых СИЗ. После устранения причины проводится повторная проверка.</p>
                </div>
              </div>
            </>
          ) : null}
          {page === 'analytics' ? (
            <>
              {stats}
              <div className="analytics-card">
                <div className="section-heading">
                  <div>
                    <h2>События в течение смены</h2>
                    <p>23 октября · 08:00–20:00</p>
                  </div>
                  <span className="chart-legend">
                    <i /> Нарушения
                  </span>
                </div>
                <div className="bar-chart">
                  {[2, 1, 3, 2, 4, 3, 6, 4, 2, 1, 0, 0].map((n, i) => (
                    <div className="chart-col" key={i}>
                      <span style={{ height: `${n * 27 + 4}px` }}>
                        <b>{n}</b>
                      </span>
                      <small>{String(i + 8).padStart(2, '0')}:00</small>
                    </div>
                  ))}
                </div>
              </div>
              <div className="analytics-bottom">
                <section>
                  <h2>По зонам</h2>
                  {siteZones.map((z) => (
                    <div className="zone-chart-row" key={z}>
                      <span>{z}</span>
                      <div>
                        <i
                          style={{
                            width: `${(siteEvents.filter((e) => e.zone === z).length / Math.max(siteEvents.length, 1)) * 200}%`,
                          }}
                        />
                      </div>
                      <b>{siteEvents.filter((e) => e.zone === z).length}</b>
                    </div>
                  ))}
                </section>
                <section>
                  <h2>Типы событий</h2>
                  {[
                    ['Действия сотрудников', siteEvents.filter((e) => e.type === 'person').length],
                    ['Контроль доступа', siteEvents.filter((e) => e.type === 'access').length],
                    ['Состояние среды', siteEvents.filter((e) => e.type === 'environment').length],
                  ].map(([label, n]) => (
                    <div className="type-stat" key={label}>
                      <span>{label}</span>
                      <strong>{n}</strong>
                    </div>
                  ))}
                  <div className="analytics-note">
                    <ShieldCheck size={18} /> Одно нарушение — одно уведомление. Повторные срабатывания объединяются.
                  </div>
                </section>
              </div>
            </>
          ) : null}
          {page === 'settings' ? (
            <>
              <section className="settings-card">
                <h2>Уведомления</h2>
                <div className="setting-row">
                  <div>
                    <strong>Звуковые оповещения</strong>
                    <p>Сигнал при появлении критического события</p>
                  </div>
                  <Switch aria-label="Звуковые оповещения" checked={sound} onCheckedChange={setSound} />
                </div>
                <div className="setting-row">
                  <div>
                    <strong>Выделение объектов на камерах</strong>
                    <p>Показывать рамки обнаружений на демонстрационных кадрах</p>
                  </div>
                  <Switch aria-label="Выделение объектов на камерах" checked={showBoxes} onCheckedChange={setShowBoxes} />
                </div>
                <div className="setting-row">
                  <div>
                    <strong>Постоянная лента событий</strong>
                    <p>Доступна справа на всех страницах сервиса</p>
                  </div>
                  <span className="connected">
                    <Check size={13} /> Всегда включена
                  </span>
                </div>
              </section>
              <section className="settings-card">
                <h2>Демонстрационная среда</h2>
                <div className="system-detail">
                  <span>Режим работы</span>
                  <b>Прототип · данные смоделированы</b>
                </div>
                <div className="system-detail">
                  <span>Вычислительная платформа</span>
                  <b>LinQ · демонстрация интерфейса</b>
                </div>
                <div className="system-detail">
                  <span>Тема интерфейса</span>
                  <b>Светлая</b>
                </div>
                <div className="system-detail">
                  <span>Часовой пояс объекта</span>
                  <b>Москва · UTC+3</b>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setEvents(initialEvents)
                    setSeen([])
                    setRulesEnabled({})
                    notify('Демонстрационные события восстановлены.')
                  }}
                >
                  Сбросить демоданные
                </Button>
              </section>
            </>
          ) : null}
          <footer className="workspace-footer">
            <span>Тук-Тук · Безопасность начинается с внимания</span>
            <span>
              <ShieldCheck size={12} /> Обработка на LinQ
            </span>
          </footer>
        </div>
      </main>
      <aside className="notification-rail" aria-label="Постоянная лента уведомлений">
        <div className="rail-header">
          <div>
            <span className="rail-title">
              <Bell size={18} />
              <h2>Лента событий</h2>
              <b>{siteEvents.filter((e) => !seen.includes(e.id)).length}</b>
            </span>
          </div>
          <button
            className={`icon-button ${sound ? 'selected' : ''}`}
            aria-label={sound ? 'Выключить звук' : 'Включить звук'}
            aria-pressed={sound}
            onClick={() => {
              setSound((v) => !v)
              notify(sound ? 'Звук уведомлений выключен.' : 'Звук уведомлений включён для демособытий.')
            }}
          >
            {sound ? <Volume2 size={17} /> : <VolumeX size={17} />}
          </button>
        </div>
        <div className="rail-tabs">
          <button className={feedTab === 'all' ? 'active' : ''} onClick={() => setFeedTab('all')}>
            Все события <span>{siteEvents.length}</span>
          </button>
          <button className={feedTab === 'critical' ? 'active' : ''} onClick={() => setFeedTab('critical')}>
            Критические <span>{siteEvents.filter((e) => e.severity === 'critical').length}</span>
          </button>
        </div>
        <div className="rail-filter">
          <label>
            <input type="checkbox" checked={feedUnread} onChange={(e) => setFeedUnread(e.target.checked)} /> Только непрочитанные
          </label>
          <button
            title="Прочитать все"
            aria-label="Прочитать все"
            onClick={() => {
              setSeen(siteEvents.map((e) => e.id))
              notify('Все уведомления отмечены прочитанными.')
            }}
          >
            <CheckCheck size={17} />
          </button>
        </div>
        <div className="feed-list">
          {feedEvents.map((e, i) => (
            <button
              key={e.id}
              className={`feed-card ${e.severity} ${!seen.includes(e.id) ? 'unread' : ''}`}
              onClick={() => {
                setSelectedId(e.id)
                setSeen((s) => (s.includes(e.id) ? s : [...s, e.id]))
              }}
            >
              <div className="feed-card-top">
                <SeverityBadge severity={e.severity} short />
                <time>{e.time.slice(0, 5)}</time>
              </div>
              <strong>{e.title}</strong>
              <span className="feed-location">
                <MapPin size={11} />
                {e.zone}
                <b>·</b>
                {e.camera}
              </span>
              {e.employee ? (
                <span className="feed-person">
                  <span className="mini-avatar">
                    {e.employee.name
                      .split(' ')
                      .map((n) => n[0])
                      .join('')}
                  </span>
                  {e.employee.name}
                  <span className="skud-tag">СКУД</span>
                </span>
              ) : null}
              {e.type === 'environment' ? <p className="feed-description">{e.description.split('. ')[0]}.</p> : null}
              {e.id === 'TK-1047' ? (
                <span className="feed-access-note">
                  <ShieldX size={12} /> Допуск истёк · Проход заблокирован
                </span>
              ) : null}
              {i === 0 || e.type === 'environment' ? (
                <span className="feed-contact">
                  <Radio size={12} />
                  {e.contact.radio}
                </span>
              ) : null}
              <div className="feed-card-bottom">
                <StatusBadge status={e.status} />
                <ChevronRight size={14} />
              </div>
            </button>
          ))}
          {feedEvents.length === 0 ? (
            <div className="feed-empty">
              <CheckCheck size={26} />
              <strong>Все события прочитаны</strong>
              <p>Снимите фильтр, чтобы увидеть историю.</p>
            </div>
          ) : null}
        </div>
        <div className="rail-bottom">
          <span>
            <i className="small-dot green" /> Подключение активно
          </span>
          <button className="demo-button" onClick={() => setModal('demo')}>
            <Plus size={13} /> Демо
          </button>
        </div>
      </aside>
      <Dialog
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedId(null)
            setPlaying(false)
          }
        }}
      >
        <DialogContent className="event-dialog">
          {selected ? (
            <>
              <DialogHeader>
                <span className="detail-eyebrow">
                  СОБЫТИЕ {selected.id} <b>23 ОКТЯБРЯ · {selected.time}</b>
                </span>
                <DialogTitle className="detail-title">{selected.title}</DialogTitle>
                <DialogDescription>
                  {selected.zone} · Камера {selected.camera}
                </DialogDescription>
              </DialogHeader>
              <div className="detail-tags">
                <SeverityBadge severity={selected.severity} />
                <StatusBadge status={selected.status} />
                <span className="tag-neutral">Уверенность ИИ 98%</span>
              </div>
              <div className="detail-columns">
                <div>
                  <CameraView event={selected} image={selected.image} large showBoxes={showBoxes} />
                  <div className="clip-controls">
                    <button aria-label={playing ? 'Остановить просмотр' : 'Просмотреть демофрагмент'} onClick={() => setPlaying((v) => !v)}>
                      {playing ? <Pause size={15} /> : <Play size={15} />}
                    </button>
                    <span>{playing ? 'Демонстрация фрагмента' : 'Стоп-кадр события'}</span>
                    <div className={`clip-track ${playing ? 'playing' : ''}`}>
                      <i />
                    </div>
                    <span>00:15</span>
                  </div>
                  <div className="detail-description">
                    <h3>Что произошло</h3>
                    <p>{selected.description}</p>
                    <div className="recommended">
                      <TriangleAlert size={17} />
                      <div>
                        <strong>Рекомендуемое действие</strong>
                        <p>{selected.action}</p>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="detail-side">
                  {selected.employee ? (
                    <section className="employee-section">
                      <span className="detail-section-label">
                        <UserRound size={14} /> Данные сотрудника <span className="skud-tag">СКУД</span>
                      </span>
                      <div className="employee-name">
                        <div className="avatar">
                          {selected.employee.name
                            .split(' ')
                            .map((n) => n[0])
                            .join('')}
                        </div>
                        <div>
                          <strong>{selected.employee.name}</strong>
                          <span>{selected.employee.role}</span>
                        </div>
                      </div>
                      <div className="employee-number">
                        Табельный номер <b>{selected.employee.number}</b>
                      </div>
                      <div className={`employee-access ${selected.employee.access.includes('отказано') ? 'denied' : ''}`}>
                        <ShieldCheck size={14} />
                        {selected.employee.access}
                      </div>
                    </section>
                  ) : (
                    <section className="employee-section">
                      <span className="detail-section-label">
                        {selected.type === 'environment' ? <Warehouse size={15} /> : <UserRound size={15} />}{' '}
                        {selected.type === 'environment' ? 'Объект среды' : 'Человек не идентифицирован'}
                      </span>
                      <p>
                        {selected.type === 'environment'
                          ? 'Нарушение не связано с действиями конкретного сотрудника.'
                          : 'Данные сотрудника отсутствуют. Проверка личности доступна охране.'}
                      </p>
                    </section>
                  )}
                  <section className="contact-section">
                    <span className="detail-section-label">Связаться с ответственным</span>
                    <strong>{selected.contact.name}</strong>
                    <span>{selected.contact.role}</span>
                    <div className="contact-line">
                      <Radio size={16} />
                      <div>
                        <small>Рация</small>
                        <b>{selected.contact.radio}</b>
                      </div>
                      <button
                        aria-label="Скопировать канал рации"
                        className="icon-button"
                        onClick={() => {
                          void navigator.clipboard?.writeText(selected.contact.radio)
                          notify('Канал рации скопирован.')
                        }}
                      >
                        <Copy size={13} />
                      </button>
                    </div>
                    <div className="contact-line">
                      <Phone size={16} />
                      <div>
                        <small>Телефон с добавочным</small>
                        <b>{selected.contact.phone}</b>
                      </div>
                    </div>
                    <p className="demo-contact-note">Демонстрационные контакты</p>
                  </section>
                </div>
              </div>
              <div className="detail-footer">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={selected.status === 'dismissed'}
                  onClick={() => updateStatus(selected.id, 'dismissed')}
                >
                  Ложное срабатывание
                </Button>
                <div>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!isOpen(selected) || selected.status === 'working'}
                    onClick={() => updateStatus(selected.id, 'working')}
                  >
                    <Clock3 size={14} />
                    {selected.status === 'working' ? 'В работе' : 'Взять в работу'}
                  </Button>
                  <Button size="sm" disabled={!isOpen(selected)} onClick={() => updateStatus(selected.id, 'resolved')}>
                    <Check size={14} /> Нарушение устранено
                  </Button>
                </div>
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
      <Dialog
        open={modal !== null}
        onOpenChange={(open) => {
          if (!open) setModal(null)
        }}
      >
        <DialogContent className="small-dialog">
          <DialogHeader>
            <DialogTitle>{modal === 'help' ? 'Добро пожаловать в Тук-Тук' : 'Добавить демособытие'}</DialogTitle>
            <DialogDescription>
              {modal === 'help'
                ? 'Безопасность людей и среды — на одном экране.'
                : 'Проверьте, как новое событие появляется в постоянной ленте.'}
            </DialogDescription>
          </DialogHeader>
          {modal === 'help' ? (
            <div className="help-content">
              <p>
                <Video size={20} />
                <span>
                  <strong>Следите за объектом</strong>Выберите зону и откройте камеру, чтобы посмотреть событие.
                </span>
              </p>
              <p>
                <BellRing size={20} />
                <span>
                  <strong>Реагируйте на уведомления</strong>В правой ленте всегда доступны нарушения, данные СКУД и контакты.
                </span>
              </p>
              <p>
                <CheckCheck size={20} />
                <span>
                  <strong>Закройте нарушение</strong>Возьмите событие в работу, затем отметьте его устранение.
                </span>
              </p>
              <div className="info-banner">
                Это интерактивный прототип: видео, сотрудники, контакты и показатели смоделированы. Реальный анализ видео и интеграции не
                подключены.
              </div>
              <Button onClick={() => setModal(null)}>
                Понятно, начать работу <ArrowRight size={15} />
              </Button>
            </div>
          ) : (
            <div className="demo-options">
              {demoOptions.map(({ label, id, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => {
                    const source = initialEvents.find((e) => e.id === id)!
                    const now = new Date().toLocaleTimeString('ru-RU', { timeZone: 'Europe/Moscow', hour12: false })
                    const newEvent = { ...source, id: `TK-DEMO-${Date.now().toString().slice(-6)}`, time: now, status: 'new' as const }
                    setEvents((list) => [newEvent, ...list])
                    setModal(null)
                    setFeedUnread(true)
                    setFeedTab('all')
                    notify('Новое демособытие добавлено в ленту.')
                    if (sound) {
                      try {
                        const audio = new AudioContext()
                        const osc = audio.createOscillator()
                        const gain = audio.createGain()
                        osc.connect(gain)
                        gain.connect(audio.destination)
                        gain.gain.value = 0.06
                        osc.frequency.value = 660
                        osc.start()
                        osc.stop(audio.currentTime + 0.18)
                        osc.onended = () => {
                          void audio.close()
                        }
                      } catch {
                        /* Sound is optional. */
                      }
                    }
                  }}
                >
                  <Icon size={20} />
                  <span>{label}</span>
                  <Plus size={17} />
                </button>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
      {toast ? (
        <div className="toast" role="status">
          <CircleCheck size={17} />
          {toast}
          <button aria-label="Закрыть уведомление" onClick={() => setToast('')}>
            <X size={14} />
          </button>
        </div>
      ) : null}
    </div>
  )
}
