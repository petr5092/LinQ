import { useEffect, useState } from 'react'

import {

  Activity,
  ArrowDownLeft,

  ArrowDownToLine,

  ArrowRight,

  Bell,

  BookOpen,

  CalendarDays,

  Check,

  ChevronDown,

  ChevronRight,

  ChevronsUpDown,

  CircleCheck,

  ClipboardCheck,

  Clock3,

  DoorOpen,

  Download,

  Eye,

  Factory,

  Fence,

  FileText,

  GraduationCap,

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

  Search,

  Send,

  Settings2,

  ShieldCheck,

  ShieldX,

  SlidersHorizontal,

  Sparkles,

  Thermometer,

  Trash2,

  TriangleAlert,

  UserRound,

  Users,

  Video,

  Volume2,

  VolumeX,

  Warehouse,

  X,

} from 'lucide-react'

import { FacilityMap } from './components/facility-map'
import { BrowserCameraPanel } from './components/browser-camera-panel'

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

  DEFAULT_MODEL_RULES,

  zoneRules,

  zoneWorkshop,

  type Camera,

  type EventStatus,

  type SafetyEvent,

  type SiteId,

} from './data'

import { api, type AnalyticsSummary, type ThermalLatestFrame } from '@/services/api'



const navItems = [

  { key: 'overview', label: 'Обзор', icon: LayoutDashboard },

  { key: 'cameras', label: 'Камеры', icon: Video },

  { key: 'events', label: 'Журнал событий', icon: List },

  { key: 'zones', label: 'Зоны и правила', icon: Map },

  { key: 'analytics', label: 'Аналитика', icon: Activity },

  { key: 'training', label: 'Обучение', icon: GraduationCap },

]

const pageTitles: Record<string, string> = {

  overview: 'Обзор безопасности',

  cameras: 'Видеомониторинг',

  events: 'Журнал событий',

  zones: 'Зоны и правила',

  analytics: 'Аналитика безопасности',

  training: 'Обучение',

  settings: 'Настройки сервиса',

}

const pageDescriptions: Record<string, string> = {

  overview: 'Всё, что происходит на объекте, — в одном месте.',

  cameras: 'Камеры и события на производственной площадке.',

  events: 'История обнаружений и работа с нарушениями.',

  zones: 'Сценарии контроля для каждого участка предприятия.',

  analytics: 'Нарушения, реакция и динамика безопасности.',

  training: 'Обучающие курсы, инструкции и материалы по безопасности для персонала.',

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

function resolveMediaImage(img?: string): string {

  if (!img) return '/images/workshop.png'

  if (img.startsWith('/') || img.startsWith('http')) {

    const placeholders = ['construction', 'workshop', 'warehouse', 'gate', 'perimeter']

    const base = img.split('/').pop()?.replace(/\.(png|jpg|jpeg)$/, '')

    if (base && placeholders.includes(base) && !img.startsWith('/images/')) {

      return `/images/${base}.png`

    }

    return img

  }

  return `/images/${img}.png`

}



function CameraView({

  camera,

  event,

  image,

  video,

  online = true,

  large = false,

  showBoxes = false,

  playing = false,

  mode = 'snapshot',

  useMjpeg = false,

  mjpegUrl,

  latestSnapshotUrl,

  zoom = 1,

  onZoomIn,

  onZoomOut,

  onZoomReset,

}: {

  camera?: Camera

  event?: SafetyEvent

  image: string

  video?: string

  online?: boolean

  large?: boolean

  showBoxes?: boolean

  playing?: boolean

  mode?: 'snapshot' | 'live'

  useMjpeg?: boolean

  mjpegUrl?: string

  latestSnapshotUrl?: string

  zoom?: number

  onZoomIn?: () => void

  onZoomOut?: () => void

  onZoomReset?: () => void

}) {

  const [mjpegFailed, setMjpegFailed] = useState(false)
  const isThermal = camera?.cameraType === 'thermal' || camera?.id?.startsWith('THERMAL')
  const [thermalFrame, setThermalFrame] = useState<ThermalLatestFrame | null>(null)
  const [thermalImgFailed, setThermalImgFailed] = useState(false)

  useEffect(() => {
    setThermalImgFailed(false)
  }, [thermalFrame?.heatmap_jpeg_base64])

  useEffect(() => {
    setMjpegFailed(false)
  }, [mjpegUrl])

  useEffect(() => {
    if (!isThermal || !camera || !online || typeof api.getLatestThermalFrame !== 'function') return
    let active = true
    const poll = async () => {
      try {
        const frame = await api.getLatestThermalFrame(camera.id)
        if (active && frame) setThermalFrame(frame)
      } catch {
        // ignore
      }
    }
    poll()
    const timer = setInterval(poll, 1500)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [isThermal, camera?.id, online])

  const active = event && isOpen(event)

  const fallbackVideo = cameras.find((c) => c.id === event?.camera)?.video

  const videoSrc = video || event?.video || fallbackVideo

  const isLive = mode === 'live' || (large && playing)

  const showVideo = online && Boolean(videoSrc) && isLive

  const bgUrl = resolveMediaImage(image)

  const snapshotImage = latestSnapshotUrl || bgUrl



  return (

    <div

      className={`camera-view ${large ? 'large' : ''} ${online ? '' : 'offline'}`}

      style={{
        backgroundImage: isThermal ? undefined : `url(${snapshotImage})`,
        backgroundColor: isThermal ? '#0f172a' : undefined,
        backgroundSize: large && zoom > 1 ? `${zoom * 100}%` : undefined,
      }}

    >

      {showVideo ? (

        useMjpeg && mjpegUrl && !mjpegFailed ? (

          <img

            className="camera-mjpeg-stream"

            src={mjpegUrl}

            alt="Прямой эфир с разметкой нейросети"

            loading="eager"

            decoding="sync"
            onError={() => setMjpegFailed(true)}

          />

        ) : (

          <video

            className="camera-video-player"

            src={videoSrc}

            autoPlay

            loop

            muted

            playsInline

          />

        )

      ) : null}

      {isThermal && online ? (
        (thermalFrame?.heatmap_jpeg_base64 || thermalFrame) && !thermalImgFailed ? (
          <img
            className="thermal-heatmap"
            src={
              thermalFrame?.heatmap_jpeg_base64
                ? `data:image/jpeg;base64,${thermalFrame.heatmap_jpeg_base64}`
                : `/api/v1/thermal/cameras/${encodeURIComponent(camera?.id || '')}/heatmap.jpg`
            }
            alt="Тепловизионная термограмма"
            onError={() => setThermalImgFailed(true)}
          />
        ) : (
          <div className="thermal-empty">
            <Thermometer size={28} className="animate-pulse" style={{ color: '#f59e0b' }} />
            <strong style={{ fontSize: '13px' }}>Тепловизор · ИК-спектр</strong>
            <span>{thermalImgFailed ? 'Ошибка отображения термограммы' : 'Получение радиометрического кадра...'}</span>
          </div>
        )
      ) : null}

      {isThermal && online && thermalFrame?.measurements ? (
        <div className="thermal-measurements">
          {thermalFrame.measurements.map((m) => (
            <div key={m.zone_id} className={`thermal-reading ${m.alarm ? 'alarm' : ''}`}>
              <strong>{m.zone_name}</strong>
              <span>T_max: {m.max_temperature_c.toFixed(1)}°C {m.alarm ? '⚠️ ПЕРЕГРЕВ' : '✓ норма'}</span>
              <span>Перегрев при: ≥ {m.threshold_c.toFixed(1)}°C (T_mean: {m.mean_temperature_c.toFixed(1)}°C)</span>
            </div>
          ))}
        </div>
      ) : null}

      {isThermal && online ? (
        <div className="thermal-scale">
          <span>20°C</span>
          <i />
          <span>120°C</span>
          <span style={{ marginLeft: '6px', color: '#fef08a', fontWeight: 600 }}>
            Перегрев при: ≥ {thermalFrame?.measurements?.[0]?.threshold_c?.toFixed(1) ?? '21.0'}°C
          </span>
        </div>
      ) : null}

      <div className="camera-tint" />

      <div className="camera-overlay-top">

        <span className={`live-label ${online ? '' : 'stopped'}`}>

          <i />

          {online ? (isThermal ? 'ТЕПЛОВИЗОР · ИК-СПЕКТР' : showVideo ? (useMjpeg ? 'LINQ TPU LIVE' : 'LIVE ПОТОК') : (mode === 'snapshot' ? 'СТОП-КАДР' : 'LIVE')) : 'НЕТ СИГНАЛА'}

        </span>

        <span className="camera-timestamp">23.10.2026 {event?.time ?? '14:32:10'}</span>

      </div>

      {active && online && showBoxes ? (

        <div

          className={`detect-box ${event.severity}`}

          style={{

            left: `${event.box[0]}%`,

            top: `${event.box[1]}%`,

            width: `${event.box[2]}%`,

            height: `${event.box[3]}%`,

          }}

        >

          <span>

            {event.type === 'environment'

              ? 'Объект'

              : event.type === 'access'

                ? 'Контроль доступа'

                : event.title} · 98%

          </span>

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

      <span className="camera-demo">{isThermal ? 'FLIR / MIKRON ИК' : useMjpeg ? 'LINQ TPU ACCELERATED' : 'ДЕМОНСТРАЦИЯ'}</span>

      {online ? (

        <span className="camera-ai">

          <Sparkles size={10} /> LinQ AI

        </span>

      ) : null}

      {large && onZoomIn && onZoomOut && onZoomReset ? (

        <div className="camera-zoom-controls" aria-label="Масштаб изображения">

          <button

            type="button"

            aria-label="Уменьшить изображение"

            title="Уменьшить"

            disabled={zoom <= 1}

            onClick={(e) => {

              e.stopPropagation()

              onZoomOut()

            }}

          >

            −

          </button>

          <button

            type="button"

            className="camera-zoom-value"

            aria-label="Сбросить масштаб"

            title="Сбросить масштаб"

            onClick={(e) => {

              e.stopPropagation()

              onZoomReset()

            }}

          >

            {Math.round(zoom * 100)}%

          </button>

          <button

            type="button"

            aria-label="Увеличить изображение"

            title="Увеличить"

            disabled={zoom >= 2.5}

            onClick={(e) => {

              e.stopPropagation()

              onZoomIn()

            }}

          >

            +

          </button>

        </div>

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

    const saved = JSON.parse(localStorage.getItem('linqsec-events-v1') || localStorage.getItem('tuk-tuk-events-v1') || 'null')

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

  const [isLiveBackend, setIsLiveBackend] = useState(false)

  const [analyticsResult, setAnalyticsResult] = useState<{

    siteId: SiteId

    summary?: AnalyticsSummary

    error: boolean

  } | null>(null)

  const [selectedId, setSelectedId] = useState<string | null>(null)

  const [inspectedCamera, setInspectedCamera] = useState<Camera | null>(null)

  const [zone, setZone] = useState('all')

  const [siteId, setSiteId] = useState<SiteId>('north')

  const [workshop, setWorkshop] = useState('all')

  const [accountId, setAccountId] = useState(accounts[0].id)

  const [search, setSearch] = useState('')

  const [severity, setSeverity] = useState('all')

  const [status, setStatus] = useState('all')

  const [eventTypeFilter, setEventTypeFilter] = useState('all')

  const [eventsReturnPage, setEventsReturnPage] = useState<string | null>(null)

  const [period, setPeriod] = useState('today')

  const [view, setView] = useState('grid')

  const [overviewTab, setOverviewTab] = useState<'traffic_light' | 'cameras' | 'map'>('traffic_light')

  const [selectedTrafficCamera, setSelectedTrafficCamera] = useState<Camera | null>(null)

  const [cameraList, setCameraList] = useState<Camera[]>(cameras)

  useEffect(() => {
    let active = true
    if (typeof api.getCameras === 'function') {
      api.getCameras().then((list) => {
        if (active && Array.isArray(list) && list.length > 0) {
          setCameraList(list)
        }
      })
    }
    return () => {
      active = false
    }
  }, [])

  const [snapshotTimestamp, setSnapshotTimestamp] = useState<number>(() => Date.now())

  const [feedTab, setFeedTab] = useState('all')

  const feedUnread = true

  const [seen, setSeen] = useState<string[]>([])

  const [sound, setSound] = useState(false)

  const [railHidden, setRailHidden] = useState(false)

  const [collapsed, setCollapsed] = useState(false)

  const [modal, setModal] = useState<'help' | 'demo' | null>(null)

  const [toast, setToast] = useState('')

  const showBoxes = false

  const [notifyStatus, setNotifyStatus] = useState<any>(null)

  const [testSending, setTestSending] = useState(false)

  const [playing, setPlaying] = useState(false)

  const [cameraZoom, setCameraZoom] = useState(1)

  const [rulesEnabled, setRulesEnabled] = useState<Record<string, boolean>>({})

  useEffect(() => {
    let isMounted = true
    if (typeof api.getNotificationZoneRules === 'function') {
      api.getNotificationZoneRules().then((rules) => {
        if (isMounted && rules && Object.keys(rules).length > 0) {
          setRulesEnabled((prev) => ({ ...prev, ...rules }))
        }
      })
    }
    return () => {
      isMounted = false
    }
  }, [])

  const [customizerOpen, setCustomizerOpen] = useState(false)

  const [customZones, setCustomZones] = useState<string[]>([])

  const [customRules, setCustomRules] = useState<Record<string, string[]>>({})

  const [customZoneDraft, setCustomZoneDraft] = useState('')

  const [customRuleDraft, setCustomRuleDraft] = useState('')

  const [customRuleZone, setCustomRuleZone] = useState('')

  const [zoneLabels, setZoneLabels] = useState<Record<string, string>>({})

  const [ruleLabels, setRuleLabels] = useState<Record<string, string>>({})

  const [customizerDirty, setCustomizerDirty] = useState(false)

  const [trainingVideoPlaying, setTrainingVideoPlaying] = useState(false)

  const [trainingQuizOpen, setTrainingQuizOpen] = useState(false)

  const [trainingQuizAnswer, setTrainingQuizAnswer] = useState<string | null>(null)

  const [trainingQuizDone, setTrainingQuizDone] = useState(false)

  const [trainingCustomizeOpen, setTrainingCustomizeOpen] = useState(false)

  const [trainingTitle, setTrainingTitle] = useState('Основы безопасности')

  const [trainingTitleDraft, setTrainingTitleDraft] = useState('Основы безопасности')



  const activeSite = sites.find((site) => site.id === siteId) ?? sites[0]

  const activeAccount = accounts.find((account) => account.id === accountId) ?? accounts[0]

  const canCustomizeZones = !['employee', 'video-operator', 'shift-leader'].includes(accountId)

  const canCustomizeTraining = ['safety-specialist', 'safety-inspector'].includes(accountId)

  const siteCameras = cameraList.filter((camera) => camera.site === siteId)

  const siteEvents = events.filter((event) => event.site === siteId)

  const siteZones = activeSite.workshops.flatMap((group) => group.zones)

  const allZones = [...siteZones, ...customZones]

  const workshopZones = activeSite.workshops

    .filter((group) => workshop === 'all' || group.name === workshop)

    .flatMap((group) => group.zones)

  const offlineCount = siteCameras.filter((camera) => !camera.online).length

  const selected = events.find((e) => e.id === selectedId)

  const openEvents = siteEvents.filter(isOpen)

  const criticalCount = openEvents.filter((e) => e.severity === 'critical').length

  const lightCount = openEvents.filter((e) => e.severity === 'info').length

  const notify = (message: string) => setToast(message)



  const openTypeEvents = (type: SafetyEvent['type']) => {

    navigate('events')

    setEventTypeFilter(type)

    setEventsReturnPage('analytics')

  }



  // Periodic polling for frame updates and status

  useEffect(() => {

    const interval = setInterval(() => {

      setSnapshotTimestamp(Date.now())

    }, 4000)

    return () => clearInterval(interval)

  }, [])



  // Load telegram notification status

  useEffect(() => {

    if (page === 'settings') {

      api.getNotificationsStatus().then((res) => {

        if (res) setNotifyStatus(res)

      })

    }

  }, [page])



  const handleSendTest = async (subscriberId?: number) => {

    setTestSending(true)

    const ok = await api.sendTestNotification(subscriberId)

    setTestSending(false)

    if (ok) {

      notify('Тестовое оповещение успешно отправлено в Telegram!')

      api.getNotificationsStatus().then(setNotifyStatus)

    } else {

      notify('Не удалось отправить тестовое сообщение. Проверьте статус бота.')

    }

  }



  const handleUpdateSubscriber = async (subId: number, min_severity: string) => {

    const ok = await api.updateSubscriber(subId, { min_severity })

    if (ok) {

      notify('Настройки подписчика обновлены.')

      api.getNotificationsStatus().then(setNotifyStatus)

    }

  }



  const handleDeleteSubscriber = async (subId: number) => {

    const ok = await api.updateSubscriber(subId, { delete: true })

    if (ok) {

      notify('Подписчик удалён.')

      api.getNotificationsStatus().then(setNotifyStatus)

    }

  }



  useEffect(() => {

    if (!toast) return

    const t = setTimeout(() => setToast(''), 4200)

    return () => clearTimeout(t)

  }, [toast])



  useEffect(() => {

    try {

      localStorage.setItem('linqsec-events-v1', JSON.stringify(events.map(({ id, status }) => ({ id, status }))))

    } catch {

      /* Session state remains usable. */

    }

  }, [events])



  useEffect(() => {

    document.title = `LenQsec · ${pageTitles[page]}`

  }, [page])



  useEffect(() => {

    setCameraZoom(1)

  }, [selectedId])



  useEffect(() => {

    let isMounted = true

    api.getIncidents().then((backendEvents) => {

      if (isMounted && backendEvents !== null) {

        setEvents(backendEvents)

        setIsLiveBackend(true)

      }

    })



    const unsubscribe = api.subscribeToEvents(

      (newIncident) => {

        setEvents((prev) => [newIncident, ...prev.filter((e) => e.id !== newIncident.id)])

        notify(`Новое событие: ${newIncident.title} (${newIncident.zone})`)

      },

      (id, newStatus) => {

        setEvents((prev) => prev.map((e) => (e.id === id ? { ...e, status: newStatus } : e)))

      },

      (connected) => {

        setIsLiveBackend(connected)

      },

      (updatedIncident) => {

        setEvents((prev) =>

          [updatedIncident, ...prev.filter((event) => event.id !== updatedIncident.id)]

        )

      }

    )



    return () => {

      isMounted = false

      unsubscribe()

    }

  }, [])

useEffect(() => {

    let isMounted = true

    api.getAnalyticsSummary(siteId).then((summary) => {

      if (isMounted) setAnalyticsResult({ siteId, summary, error: false })

    }).catch(() => {

      if (isMounted) setAnalyticsResult({ siteId, error: true })

    })

    return () => {

      isMounted = false

    }

  }, [siteId])

  const analytics = analyticsResult?.siteId === siteId ? analyticsResult.summary ?? null : null

  const analyticsError = analyticsResult?.siteId === siteId && analyticsResult.error



  const updateStatus = (id: string, value: EventStatus) => {

    const current = events.find((event) => event.id === id)

    if (!current || (value === 'working' && current.status !== 'new') || (value === 'resolved' && current.status !== 'working')) return

    setEvents((list) => list.map((e) => (e.id === id ? { ...e, status: value } : e)))

    if (value === 'resolved') {

      setSeen((curr) => (curr.includes(id) ? curr : [...curr, id]))

    }

    api.updateStatus(id, value).catch(() => {})

    notify(

      value === 'working'

        ? 'Событие взято в работу. Ответственный назначен.'

        : value === 'resolved'

          ? 'Нарушение отмечено как устранённое.'

          : 'Событие отмечено как ложное срабатывание. LinQ AI учтёт этот пример.'

    )

  }



  const navigate = (key: string) => {

    window.scrollTo({ top: 0, behavior: 'instant' })

    setPage(key)

    setZone('all')

    setSearch('')

    setSeverity('all')

    setStatus('all')

    setEventTypeFilter('all')

    setPeriod('today')

    setWorkshop('all')

    if (key !== 'events') setEventsReturnPage(null)

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

    if (['employee', 'video-operator', 'shift-leader'].includes(id)) setCustomizerOpen(false)

    if (!['safety-specialist', 'safety-inspector'].includes(id)) setTrainingCustomizeOpen(false)

    const next = accounts.find((account) => account.id === id)

    if (next) notify(`Аккаунт: ${next.role} · ${next.name}`)

  }



  const downloadTrainingHandout = () => {

    const content = `LENQSEC · ПАМЯТКА ПО БЕЗОПАСНОСТИ\n\n1. Используйте каску и средства защиты органов дыхания.\n2. Не проходите под подвешенным грузом.\n3. Держите проходы свободными.\n4. Сообщайте оператору видеонаблюдения о нарушениях.`

    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })

    const url = URL.createObjectURL(blob)

    const link = document.createElement('a')

    link.href = url

    link.download = 'lenqsec-pamyatka-po-bezopasnosti.txt'

    link.click()

    URL.revokeObjectURL(url)

    notify('Памятка скачана.')

  }



  const dateMatch = (e: SafetyEvent) => (period === 'last-hour' ? e.time >= '14:00:00' : true)

  const filteredEvents = siteEvents.filter(

    (e) =>

      (zone === 'all' || e.zone === zone) &&

      (severity === 'all' || e.severity === severity) &&

      (status === 'all' || (status === 'open' ? isOpen(e) : e.status === status)) &&

      (eventTypeFilter === 'all' || e.type === eventTypeFilter) &&

      dateMatch(e) &&

      `${e.title} ${e.id} ${e.camera} ${e.employee?.name ?? ''}`.toLowerCase().includes(search.toLowerCase())

  )

  const filteredCameras = siteCameras.filter(

    (c) =>

      (zone === 'all' || c.zone === zone) &&

      (workshop === 'all' || c.workshop === workshop) &&

      `${c.name} ${c.id} ${c.zone} ${c.workshop}`.toLowerCase().includes(search.toLowerCase())

  )

  const prioritizedCameras = [...filteredCameras].sort((a, b) => {

    const aHasViolation = Boolean(a.event && events.some((event) => event.id === a.event && isOpen(event)))

    const bHasViolation = Boolean(b.event && events.some((event) => event.id === b.event && isOpen(event)))

    return Number(bHasViolation) - Number(aHasViolation)

  })

  const visibleCameras = page === 'cameras' ? prioritizedCameras : prioritizedCameras.slice(0, 6)

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

      'ID',

      'Площадка',

      'Зона',

      'Камера',

      'Время',

      'Событие',

      'Важность',

      'Статус',

      'Сотрудник',

      'Табельный номер',

    ]

    const rows = filteredEvents.map((e) => [

      e.id,

      sites.find((s) => s.id === e.site)?.name ?? e.site,

      e.zone,

      e.camera,

      e.time,

      `"${e.title.replace(/"/g, '""')}"`,

      e.severity === 'critical' ? 'Критическое' : e.severity === 'warning' ? 'Внимание' : 'Информация',

      statusLabels[e.status],

      `"${(e.employee?.name ?? '—').replace(/"/g, '""')}"`,

      e.employee?.number ?? '—',

    ])

    const csv = [fields.join(';'), ...rows.map((r) => r.join(';'))].join('\r\n')

    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })

    const url = URL.createObjectURL(blob)

    const a = document.createElement('a')

    a.href = url

    a.download = `safety-events-${siteId}-${new Date().toISOString().slice(0, 10)}.csv`

    a.click()

    URL.revokeObjectURL(url)

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

          <span className="stat-value-tag yellow">{lightCount} лёгких</span>

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

          Устранено всего <ShieldCheck size={15} />

        </span>

        <div className="stat-value">

          {analytics?.incidents.resolved ?? '—'}

        </div>

        <div className="stat-note">По данным базы инцидентов</div>

        <StatSpark color="blue" />

      </button>

      <button className="stat-card" onClick={() => navigate('analytics')}>

        <span className="stat-label">

          Инциденты сегодня <Clock3 size={15} />

        </span>

        <div className="stat-value">

          {analytics?.today.total ?? '—'}

        </div>

        <div className="stat-note">По данным базы инцидентов</div>

      </button>

    </div>

  )

  const zoneFilter = (

    <label className="select-wrap">

      <MapPin size={15} />

      <select aria-label="Фильтр по зоне" value={zone} onChange={(e) => setZone(e.target.value)}>

        <option value="all">Все зоны</option>

        {workshopZones.map((z) => (

          <option value={z} key={z}>

            {zoneLabels[z] ?? z}

          </option>

        ))}

      </select>

      <ChevronDown size={12} />

    </label>

  )

  const workshopFilter = (

    <label className="select-wrap">

      <Factory size={15} />

      <select aria-label="Корпус или участок" value={workshop} onChange={(e) => setWorkshop(e.target.value)}>

        <option value="all">Все корпуса</option>

        {activeSite.workshops.map((w) => (

          <option value={w.name} key={w.name}>

            {w.name}

          </option>

        ))}

      </select>

      <ChevronDown size={12} />

    </label>

  )

  const searchInput = (

    <label className="search-wrap">

      <Search size={15} />

      <input

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

          <button

            className={`snapshot-toggle-btn ${overviewTab === 'traffic_light' ? 'active' : ''}`}

            onClick={() => setOverviewTab(overviewTab === 'traffic_light' ? 'cameras' : 'traffic_light')}

            title="Показать светофор состояния камер"

          >

            <Activity size={14} />

            <span>Светофор</span>

          </button>

          <span className="live-text">

            <i /> Прямой эфир

          </span>

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

                onClick={() => setInspectedCamera(camera)}

              >

                <CameraView

                  camera={camera}

                  event={event}

                  image={camera.image}

                  video={camera.video}

                  online={camera.online}

                  showBoxes={showBoxes}

                  mode="live"

                  latestSnapshotUrl={camera.id === 'CAM-01' ? `/api/v1/cameras/CAM-01/frame.jpg?t=${snapshotTimestamp}` : undefined}

                />

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

            <th>Участок</th>

            <th>Камера</th>

            <th>Время</th>

            <th>Важность</th>

            <th>Сотрудник</th>

            <th>Статус</th>

            <th aria-label="Действие" />

          </tr>

        </thead>

        <tbody>

          {list.map((e) => (

            <tr

              key={e.id}

              className={selectedId === e.id ? 'active' : ''}

              onClick={() => setSelectedId(e.id)}

              style={{ cursor: 'pointer' }}

            >

              <td>

                <div className="event-primary">

                  <EventIcon event={e} />

                  <div>

                    <strong>{e.title}</strong>

                    <span>ID: {e.id}</span>

                  </div>

                </div>

              </td>

              <td>

                <span>{e.zone}</span>

              </td>

              <td>

                <span className="camera-tag">{e.camera}</span>

              </td>

              <td>

                <time>{e.time}</time>

              </td>

              <td>

                <SeverityBadge severity={e.severity} short={compact} />

              </td>

              <td>

                <span className="employee-text">{e.employee?.name ?? '—'}</span>

              </td>

              <td>

                <StatusBadge status={e.status} />

              </td>

              <td onClick={(ev) => ev.stopPropagation()}>

                <button

                  className="icon-button"

                  aria-label={`Открыть событие ${e.id}`}

                  onClick={() => setSelectedId(e.id)}

                >

                  <ArrowRight size={16} />

                </button>

              </td>

            </tr>

          ))}

        </tbody>

      </table>

      {list.length === 0 ? <Empty text="События не найдены" /> : null}

    </div>

  )

  const map = (

    <FacilityMap

      site={activeSite}

      events={siteEvents}

      onEvent={(id: string) => setSelectedId(id)}

      onAttention={(cameraIds: string[]) => {

        navigate('cameras')

        setSearch(cameraIds[0] ?? '')

      }}

      onCameras={(selectedZone: string) => {

        navigate('cameras')

        setZone(selectedZone || 'all')

      }}

      renderCamera={(camera: Camera, event?: SafetyEvent) => (

        <CameraView

          camera={camera}

          event={event}

          image={camera.image}

          video={camera.video}

          online={camera.online}

          showBoxes={showBoxes}

          mode="live"

        />

      )}

    />

  )

  const getCameraTrafficInfo = (cam: Camera) => {
    const camEvents = events.filter((e) => e.camera === cam.id)
    const active = camEvents.filter((e) => e.status === 'new' || e.status === 'working')
    const hasCritical = active.some((e) => e.severity === 'critical')
    const hasWarning = !hasCritical && active.some((e) => e.severity === 'warning')
    const statusColor: 'red' | 'yellow' | 'green' = hasCritical ? 'red' : hasWarning ? 'yellow' : 'green'

    const primaryEvent = active.find((e) => hasCritical ? e.severity === 'critical' : e.severity === 'warning') || active[0] || camEvents[0]

    let statusText = 'В норме · нарушений нет'
    if (cam.cameraType === 'thermal') {
      const threshold = 21.0
      if (statusColor === 'red') {
        statusText = `Критический перегрев (T ≥ ${threshold.toFixed(1)}°C): ${primaryEvent?.title || 'Превышение порога'}`
      } else if (statusColor === 'yellow') {
        statusText = `Внимание: перегрев (порог T ≥ ${threshold.toFixed(1)}°C)`
      } else {
        statusText = `В норме · Перегрев при: T ≥ ${threshold.toFixed(1)}°C`
      }
    } else {
      if (statusColor === 'red') {
        statusText = `Критично: ${primaryEvent?.title || 'Аварийный режим'}`
      } else if (statusColor === 'yellow') {
        statusText = `Внимание: ${primaryEvent?.title || 'Отклонение от регламента'}`
      }
    }

    return {
      statusColor,
      statusText,
      activeCount: active.length,
      primaryEvent,
      hasCritical,
      hasWarning,
      thermalThreshold: cam.cameraType === 'thermal' ? 21.0 : undefined,
    }
  }

  const trafficLightView = (
    <div className="traffic-light-container">
      <div className="traffic-summary-bar">
        <span style={{ fontSize: '13px', fontWeight: 600, color: '#334155', marginRight: '4px' }}>
          Светофор безопасности производственных процессов:
        </span>
        {(() => {
          const infos = siteCameras.map((c) => getCameraTrafficInfo(c))
          const redC = infos.filter((i) => i.statusColor === 'red').length
          const yellowC = infos.filter((i) => i.statusColor === 'yellow').length
          const greenC = infos.filter((i) => i.statusColor === 'green').length
          return (
            <>
              <span className="traffic-summary-pill red">● Критично: {redC}</span>
              <span className="traffic-summary-pill yellow">● Внимание: {yellowC}</span>
              <span className="traffic-summary-pill green">● В норме: {greenC}</span>
              <span style={{ fontSize: '12px', color: '#64748b', marginLeft: 'auto' }}>
                Всего камер под контролем: {siteCameras.length}
              </span>
            </>
          )
        })()}
      </div>

      <div className="traffic-grid">
        {siteCameras.map((cam) => {
          const info = getCameraTrafficInfo(cam)
          return (
            <div
              key={cam.id}
              role="button"
              tabIndex={0}
              className={`traffic-card status-${info.statusColor}`}
              onClick={() => setSelectedTrafficCamera(cam)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  setSelectedTrafficCamera(cam)
                }
              }}
              aria-label={`Светофор камеры ${cam.name} (${cam.id}): состояние ${info.statusColor === 'red' ? 'критично' : info.statusColor === 'yellow' ? 'внимание' : 'в норме'}. Показать скрин нарушения.`}
            >
              <span className={`traffic-status-circle ${info.statusColor}`} aria-hidden="true" />

              <div className="traffic-info">
                <div className="traffic-header">
                  <span className="traffic-title" title={cam.name}>
                    {cam.name}
                  </span>
                  <span className="traffic-workshop">
                    {cam.workshop} · {cam.zone}
                  </span>
                </div>

                <div className={`traffic-status-desc status-${info.statusColor}`}>
                  {info.statusColor === 'red' ? '🔴 ' : info.statusColor === 'yellow' ? '🟡 ' : '🟢 '}
                  {info.statusText}
                </div>

                <div className="traffic-card-footer">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {cam.cameraType === 'thermal' ? (
                      <>
                        <span className="traffic-badge thermal">Тепловизор</span>
                        <span className="traffic-badge thermal" style={{ color: '#b45309' }}>
                          Порог: T ≥ 21.0°C
                        </span>
                      </>
                    ) : (
                      <span className="traffic-badge tpu">LinQ TPU</span>
                    )}
                    <span className="camera-id">{cam.id}</span>
                    {info.activeCount > 0 ? (
                      <span style={{ fontSize: '10px', color: info.statusColor === 'red' ? '#dc2626' : '#d97706', fontWeight: 600 }}>
                        {info.activeCount} акт.
                      </span>
                    ) : null}
                  </div>

                  <span className="traffic-btn-preview">
                    <Eye size={13} /> Скрин нарушения
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )



  return (

    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''} ${railHidden ? 'rail-hidden' : ''}`}>

      <aside className="sidebar">

        <div className="brand-row">

          <div className="brand">



            LenQsec<span className="brand-dot">.</span>

          </div>

          <button

            className="sidebar-toggle"

            aria-label={collapsed ? 'Развернуть меню' : 'Свернуть меню'}

            onClick={() => setCollapsed((v) => !v)}

          >

            <Menu size={18} />

          </button>

        </div>

        <label className="facility-select">

          <span className="facility-symbol">

            <Factory size={18} />

          </span>

          <div>

            <strong>{activeSite.name}</strong>

            <span>{activeSite.subtitle}</span>

          </div>

          <ChevronsUpDown size={15} />

          <select

            aria-label="Выбор площадки"

            value={siteId}

            onChange={(e) => switchSite(e.target.value as SiteId)}

          >

            {sites.map((site) => (

              <option value={site.id} key={site.id}>

                {site.name} — {site.subtitle}

              </option>

            ))}

          </select>

        </label>

        <div className="nav-caption">РАБОЧЕЕ ПРОСТРАНСТВО</div>

        <nav aria-label="Основная навигация">

          {navItems.map(({ key, label, icon: Icon }) => (

            <button

              key={key}

              onClick={() => navigate(key)}

              className={`nav-item ${page === key ? 'active' : ''}`}

              title={label}

            >

              <Icon size={18} />

              <span>{label}</span>

              {key === 'events' ? <b className="events-count">{openEvents.length}</b> : null}

              {key === 'cameras' ? <small>{siteCameras.length}</small> : null}

            </button>

          ))}

        </nav>

        <div className="sidebar-bottom">
          <button

            className={`nav-item ${page === 'settings' ? 'active' : ''}`}

            onClick={() => navigate('settings')}

            title="Настройки сервиса"

          >

            <Settings2 size={18} />

            <span>Настройки</span>

          </button>

          <div className="profile">

            <span className="avatar">{activeAccount.initials}</span>

            <div>

              <strong>{activeAccount.name}</strong>

              <span>{activeAccount.role}</span>

            </div>

            <DropdownMenu>

              <DropdownMenuTrigger asChild>

                <button className="icon-button" aria-label="Сменить пользователя">

                  <UserRound size={16} />

                </button>

              </DropdownMenuTrigger>

              <DropdownMenuContent align="end">

                {accounts.map((account) => (

                  <DropdownMenuItem key={account.id} onClick={() => switchAccount(account.id)}>

                    <div>

                      <strong>{account.role}</strong>

                      <div className="text-muted-foreground" style={{ fontSize: 11 }}>

                        {account.name} · {account.note}

                      </div>

                    </div>

                  </DropdownMenuItem>

                ))}

              </DropdownMenuContent>

            </DropdownMenu>

          </div>

        </div>

      </aside>



      <main className="workspace">

        <header className="breadcrumbs">

          <Factory size={13} />

          <span>{activeSite.subtitle}</span>

          <ChevronRight size={13} />

          <span className="current">{pageTitles[page]}</span>



          {isLiveBackend && (

            <span

              style={{

                marginLeft: 12,

                display: 'inline-flex',

                alignItems: 'center',

                gap: 5,

                background: '#ecfdf5',

                color: '#059669',

                padding: '2px 8px',

                borderRadius: 99,

                fontSize: 10,

                fontWeight: 600,

                border: '1px solid #a7f3d0',

              }}

              title="Подключено к LinQ REST API и WebSocket в реальном времени"

            >

              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }} />

              API LIVE

            </span>

          )}



          <span className="prototype-label">ПРОТОТИП v0.9</span>

        </header>



        <div className="page-heading">

          <div>

            <h1>{pageTitles[page]}</h1>

            <p>{pageDescriptions[page]}</p>

          </div>

          <div className="page-actions">

            <span className="date-select">

              <CalendarDays size={14} />

              <select

                aria-label="Период отображения"

                value={period}

                onChange={(e) => setPeriod(e.target.value)}

              >

                <option value="today">Сегодня, 23 октября</option>

                <option value="last-hour">Последний час</option>

              </select>

            </span>

            <button className="btn-secondary" onClick={exportCSV} title="Скачать события за выбранную смену в CSV">

              <ArrowDownToLine size={15} /> Экспорт

            </button>

            <button className="btn-primary" onClick={() => setModal('demo')}>

              <Sparkles size={15} /> Демонстрация

            </button>

          </div>

        </div>



        <div className="page-content">

          {page === 'overview' ? (

            <>

              {stats}

              <div className="overview-tabs">

                <button

                  className={overviewTab === 'traffic_light' ? 'active' : ''}

                  onClick={() => setOverviewTab('traffic_light')}

                >

                  <Activity size={16} /> Светофор

                </button>

                <button

                  className={overviewTab === 'cameras' ? 'active' : ''}

                  onClick={() => setOverviewTab('cameras')}

                >

                  <Video size={16} /> Камеры

                </button>

                <button

                  className={overviewTab === 'map' ? 'active' : ''}

                  onClick={() => setOverviewTab('map')}

                >

                  <Map size={16} /> Карта объекта

                </button>

                <span>

                  <ShieldCheck size={13} /> Система работает штатно

                </span>

              </div>

              {overviewTab === 'map' ? (

                map

              ) : overviewTab === 'traffic_light' ? (

                <>

                  {trafficLightView}

                  {cameraGrid}

                </>

              ) : (

                cameraGrid

              )}

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

          {page === 'cameras' ? (
            <>
              <BrowserCameraPanel cameras={siteCameras} siteId={siteId} />
              {cameraGrid}
            </>
          ) : null}

          {page === 'events' ? (

            <>

              {eventsReturnPage === 'analytics' ? (

                <button className="journal-back" onClick={() => navigate('analytics')}>

                  <ArrowDownLeft size={14} /> Вернуться к аналитике

                </button>

              ) : null}

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

                    <option value="info">Лёгкие</option>

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

                  <p>Управляйте отправкой уведомлений по участкам. Выключение сценария блокирует рассылку алертов (Telegram / NetIO) для выбранной зоны.</p>

                </div>

                {canCustomizeZones ? (

                  <button

                    className="customize-action"

                    onClick={() => {

                      if (customizerOpen && customizerDirty) {

                        setCustomizerDirty(false)

                        setCustomizerOpen(false)

                        notify('Изменения предприятия сохранены.')

                      } else {

                        setCustomizerOpen((value) => !value)

                      }

                    }}

                  >

                    {customizerOpen ? (customizerDirty ? 'Сохранить изменения' : 'Скрыть настройку') : 'Настроить предприятие'}

                  </button>

                ) : null}

              </div>

              {customizerOpen ? (

                <div className="zone-customizer">

                  <div>

                    <strong>Адаптация под предприятие</strong>

                    <p>Добавляйте собственные места и сценарии контроля.</p>

                  </div>

                  <div className="customizer-fields">

                    <label>

                      <span>Новое место</span>

                      <input

                        value={customZoneDraft}

                        onChange={(e) => setCustomZoneDraft(e.target.value)}

                        placeholder="Например, Серверная"

                      />

                    </label>

                    <button

                      onClick={() => {

                        const value = customZoneDraft.trim()

                        if (!value || allZones.includes(value)) return

                        setCustomZones((zones) => [...zones, value])

                        setCustomizerDirty(true)

                        setCustomRuleZone(value)

                        setCustomZoneDraft('')

                      }}

                    >

                      Добавить место

                    </button>

                    <label>

                      <span>Новое нарушение</span>

                      <input

                        value={customRuleDraft}

                        onChange={(e) => setCustomRuleDraft(e.target.value)}

                        placeholder="Например, Открытая дверь"

                      />

                    </label>

                    <select

                      aria-label="Место для нового нарушения"

                      value={customRuleZone || allZones[0] || ''}

                      onChange={(e) => setCustomRuleZone(e.target.value)}

                    >

                      {allZones.map((item) => (

                        <option key={item} value={item}>

                          {item}

                        </option>

                      ))}

                    </select>

                    <button

                      onClick={() => {

                        const value = customRuleDraft.trim()

                        const target = customRuleZone || allZones[0]

                        if (!value || !target) return

                        setCustomRules((rules) => ({ ...rules, [target]: [...(rules[target] ?? []), value] }))

                        setCustomizerDirty(true)

                        setCustomRuleDraft('')

                      }}

                    >

                      Добавить нарушение

                    </button>

                  </div>

                </div>

              ) : null}

              <div className="zones-grid">

                {allZones.map((z, i) => {

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

                          <h2>

                            {zoneLabels[z] ?? z}

                            {customizerOpen ? (

                              <button

                                className="inline-edit"

                                title="Изменить название места"

                                onClick={() => {

                                  const value = window.prompt('Название места', zoneLabels[z] ?? z)?.trim()

                                  if (value && value !== z) {

                                    setZoneLabels((labels) => ({ ...labels, [z]: value }))

                                    setCustomizerDirty(true)

                                  }

                                }}

                              >

                                изменить

                              </button>

                            ) : null}

                          </h2>

                          <p>

                            {zoneWorkshop[z] ?? 'Пользовательская зона'} · {cameraCount} {pluralRu(cameraCount, 'камера', 'камеры', 'камер')} · {zoneEventCount}{' '}

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

                      {[...(zoneRules[z] ?? DEFAULT_MODEL_RULES), ...(customRules[z] ?? [])].map((rule) => (

                        <div className="rule-row" key={rule}>

                          <span>

                            {ruleLabels[`${z}:${rule}`] ?? rule}

                            {customizerOpen ? (

                              <button

                                className="inline-edit"

                                title="Изменить нарушение"

                                onClick={() => {

                                  const value = window.prompt('Название нарушения', ruleLabels[`${z}:${rule}`] ?? rule)?.trim()

                                  if (value && value !== rule) {

                                    setRuleLabels((labels) => ({ ...labels, [`${z}:${rule}`]: value }))

                                    setCustomizerDirty(true)

                                  }

                                }}

                              >

                                изменить

                              </button>

                            ) : null}

                          </span>

                          <Switch

                            aria-label={`${zoneLabels[z] ?? z}: ${ruleLabels[`${z}:${rule}`] ?? rule}`}

                            checked={rulesEnabled[z + rule] ?? true}

                            onCheckedChange={(v) => {

                              setRulesEnabled((p) => ({ ...p, [z + rule]: v }))

                              if (customizerOpen) setCustomizerDirty(true)

                              api.setNotificationZoneRule(z, rule, v)

                            }}

                          />

                        </div>

                      ))}

                    </section>

                  )

                })}

              </div>

            </>

          ) : null}

          {page === 'analytics' ? (

            <>

              {analyticsError ? (

                <div className="analytics-card" role="alert">

                  Не удалось загрузить аналитику из базы данных. Проверьте доступность сервера.

                </div>

              ) : analytics === null ? (

                <div className="analytics-card" role="status">Загрузка аналитики…</div>

              ) : (

                <>

                  <div className="stats-grid">

                    {[

                      ['Инциденты за всё время', analytics.incidents.total],

                      ['Открытые', analytics.incidents.active],

                      ['Критические', analytics.severity.critical],

                      ['Устранённые', analytics.incidents.resolved],

                    ].map(([label, value]) => (

                      <div className="stat-card" key={label}>

                        <span className="stat-label">{label}</span>

                        <div className="stat-value">{value}</div>

                      </div>

                    ))}

                  </div>

                  <div className="analytics-card">

                    <div className="section-heading">

                      <div>

                        <h2>Инциденты за сутки</h2>

                        <p>

                          {new Intl.DateTimeFormat('ru-RU', {

                            day: 'numeric',

                            month: 'long',

                            year: 'numeric',

                            timeZone: 'UTC',

                          }).format(new Date(`${analytics.date}T00:00:00Z`))}

                        </p>

                      </div>

                      <span className="chart-legend">

                        <i /> Из базы данных · всего {analytics.today.total}

                      </span>

                    </div>

                    {analytics.today.total === 0 ? (

                      <p>За эти сутки зарегистрированных инцидентов нет.</p>

                    ) : null}

                    <div style={{ overflowX: 'auto' }}>

                      <div className="bar-chart" style={{ minWidth: 900 }}>

                        {analytics.today.hourly.map((count, hour) => (

                          <div className="chart-col" key={hour}>

                            <span style={{ height: `${Math.max(4, (count / Math.max(...analytics.today.hourly, 1)) * 108)}px` }}>

                              <b>{count}</b>

                            </span>

                            <small>{String(hour).padStart(2, '0')}:00</small>

                          </div>

                        ))}

                      </div>

                    </div>

                  </div>

                  <div className="analytics-bottom">

                    <section>

                      <h2>По зонам · за сутки</h2>

                      {analytics.today.by_zone.length > 0 ? analytics.today.by_zone.map(({ name, count }) => (

                        <div className="zone-chart-row" key={name}>

                          <span>{name}</span>

                          <div>

                            <i

                              style={{

                                width: `${(count / analytics.today.total) * 100}%`,

                              }}

                            />

                          </div>

                          <b>{count}</b>

                        </div>

                      )) : <p>Нет данных за выбранные сутки.</p>}

                    </section>

                    <section>

                      <h2>Типы событий · за сутки</h2>

                      {analytics.today.by_type.length > 0 ? analytics.today.by_type.map(({ name, count }) => {

                        const typeKey = (name === 'person' || name === 'access' || name === 'environment') ? (name as 'person' | 'access' | 'environment') : 'person'

                        const label = name === 'person'

                          ? 'Действия сотрудников'

                          : name === 'access'

                            ? 'Контроль доступа'

                            : name === 'environment'

                              ? 'Состояние среды'

                              : name

                        return (

                          <button

                            className="type-stat"

                            key={name}

                            onClick={() => openTypeEvents(typeKey)}

                            title={`Показать события: ${label}`}

                          >

                            <span>{label}</span>

                            <strong>{count}</strong>

                          </button>

                        )

                      }) : <p>Нет данных за выбранные сутки.</p>}

                      <div className="analytics-note">

                        <ShieldCheck size={18} /> Подсчёт ведётся по зарегистрированным инцидентам выбранной площадки.

                      </div>

                    </section>

                  </div>

                </>

              )}

            </>

          ) : null}

          {page === 'training' ? (

            <>

              <section className="training-hero">

                <div className="training-hero-icon">

                  <GraduationCap size={24} />

                </div>

                <div>

                  <h2>Безопасность начинается с знаний</h2>

                  <p>Изучайте правила предприятия, проходите короткие тесты и возвращайтесь к материалам в любое время.</p>

                </div>

                <div className="training-progress">

                  <strong>2 из 6</strong>

                  <span>уроков пройдено</span>

                  <div className="training-progress-counts">

                    <b>2 <small>пройдено</small></b>

                    <b>4 <small>осталось</small></b>

                  </div>

                  <i><b style={{ width: '33%' }} /></i>

                </div>

                {canCustomizeTraining ? (

                  <button

                    className="training-customize"

                    onClick={() => {

                      setTrainingTitleDraft(trainingTitle)

                      setTrainingCustomizeOpen((value) => !value)

                    }}

                    title="Настроить программу обучения"

                  >

                    <Settings2 size={14} /> {trainingCustomizeOpen ? 'Скрыть настройку' : 'Настроить обучение'}

                  </button>

                ) : null}

              </section>

              {trainingCustomizeOpen && canCustomizeTraining ? (

                <div className="training-customizer">

                  <div>

                    <strong>Настройка программы</strong>

                    <p>Изменения видны сотрудникам предприятия.</p>

                  </div>

                  <label>

                    <span>Название вводного урока</span>

                    <input

                      value={trainingTitleDraft}

                      onChange={(e) => setTrainingTitleDraft(e.target.value)}

                    />

                  </label>

                  <button

                    className="training-save"

                    onClick={() => {

                      setTrainingTitle(trainingTitleDraft.trim() || 'Основы безопасности')

                      setTrainingCustomizeOpen(false)

                      notify('Программа обучения сохранена.')

                    }}

                  >

                    Сохранить

                  </button>

                </div>

              ) : null}

              <div className="training-layout">

                <section className="training-video-card">

                  <div className="section-heading">

                    <div>

                      <h2>Видеоурок · {trainingTitle}</h2>

                      <p>04:32 · обязательный вводный инструктаж</p>

                    </div>

                    <span className="tag-neutral">Для всех сотрудников</span>

                  </div>

                  <button

                    className={`training-video ${trainingVideoPlaying ? 'playing' : ''}`}

                    onClick={() => setTrainingVideoPlaying((value) => !value)}

                    aria-label={trainingVideoPlaying ? 'Поставить видео на паузу' : 'Запустить видео'}

                  >

                    <span className="training-video-bg" />

                    <span className="training-video-overlay" />

                    <span className="training-video-label">

                      <Video size={14} /> Вводный инструктаж · Цех № 1

                    </span>

                    <span className="training-play">

                      {trainingVideoPlaying ? <Pause size={24} /> : <Play size={24} fill="currentColor" />}

                    </span>

                    <span className="training-video-caption">

                      {trainingVideoPlaying ? 'Воспроизведение · 00:18 / 04:32' : 'Нажмите, чтобы начать просмотр'}

                    </span>

                  </button>

                  <div className="training-card-footer">

                    <span>

                      <Check size={14} /> После просмотра урок будет отмечен как пройденный

                    </span>

                    <button

                      className="training-link"

                      onClick={() => notify('Видеоурок открыт в демонстрационном режиме.')}

                    >

                      Открыть в новом окне <ArrowRight size={13} />

                    </button>

                  </div>

                </section>

                <section className="training-quiz-card">

                  <div className="training-card-icon">

                    <ClipboardCheck size={19} />

                  </div>

                  <h2>Проверьте знания</h2>

                  <p>Короткий тест после инструктажа поможет закрепить правила.</p>

                  {!trainingQuizOpen ? (

                    <button

                      className="training-primary"

                      onClick={() => {

                        setTrainingQuizOpen(true)

                        setTrainingQuizDone(false)

                        setTrainingQuizAnswer(null)

                      }}

                    >

                      Начать тест <ArrowRight size={14} />

                    </button>

                  ) : (

                    <div className="training-question">

                      <strong>Что нужно сделать перед входом в производственную зону?</strong>

                      {['Проверить каску и необходимые СИЗ', 'Взять телефон с собой', 'Пройти под подвешенным грузом'].map(

                        (answer) => (

                          <button

                            key={answer}

                            className={trainingQuizAnswer === answer ? 'selected' : ''}

                            onClick={() => setTrainingQuizAnswer(answer)}

                          >

                            {answer}

                          </button>

                        )

                      )}

                      {trainingQuizDone ? (

                        <p className={trainingQuizAnswer === 'Проверить каску и необходимые СИЗ' ? 'quiz-success' : 'quiz-error'}>

                          {trainingQuizAnswer === 'Проверить каску и необходимые СИЗ'

                            ? 'Верно! Правило усвоено.'

                            : 'Попробуйте ещё раз и выберите безопасное действие.'}

                        </p>

                      ) : (

                        <button

                          className="training-submit"

                          disabled={!trainingQuizAnswer}

                          onClick={() => setTrainingQuizDone(true)}

                        >

                          Проверить ответ

                        </button>

                      )}

                    </div>

                  )}

                </section>

              </div>

              <section className="training-materials">

                <div className="section-heading">

                  <div>

                    <h2>Материалы для изучения</h2>

                    <p>Читайте в удобном формате и скачивайте памятки для работы</p>

                  </div>

                  <span className="tag-neutral">6 материалов</span>

                </div>

                <div className="training-material-grid">

                  <article className="training-material">

                    <span className="training-material-icon blue">

                      <BookOpen size={19} />

                    </span>

                    <div>

                      <strong>Правила безопасной работы</strong>

                      <p>Статья · 7 минут чтения</p>

                    </div>

                    <button

                      className="training-icon-action"

                      title="Открыть статью"

                      onClick={() => notify('Статья открыта в режиме чтения.')}

                    >

                      <ArrowRight size={15} />

                    </button>

                  </article>

                  <article className="training-material">

                    <span className="training-material-icon orange">

                      <FileText size={19} />

                    </span>

                    <div>

                      <strong>Руководство по СИЗ</strong>

                      <p>PDF · 12 страниц</p>

                    </div>

                    <button

                      className="training-icon-action"

                      title="Открыть руководство"

                      onClick={() => notify('Руководство открыто в режиме чтения.')}

                    >

                      <ArrowRight size={15} />

                    </button>

                  </article>

                  <article className="training-material">

                    <span className="training-material-icon green">

                      <Download size={19} />

                    </span>

                    <div>

                      <strong>Памятка для смены</strong>

                      <p>Раздаточный материал · TXT</p>

                    </div>

                    <button

                      className="training-icon-action"

                      title="Скачать памятку"

                      onClick={downloadTrainingHandout}

                    >

                      <Download size={15} />

                    </button>

                  </article>

                </div>

              </section>

            </>

          ) : null}

          {page === 'settings' ? (

            <>

              <section className="settings-card">

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>

                  <div>

                    <h2>Telegram-бот оперативных оповещений</h2>

                    <p style={{ color: 'var(--subtle)', fontSize: 12 }}>

                      Мгновенная доставка стоп-кадров нарушений в личные и групповые чаты дежурных смен

                    </p>

                  </div>

                  {notifyStatus?.telegram?.status === 'online' ? (

                    <span className="connected" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>

                      <Check size={14} color="#16a34a" /> @{notifyStatus.telegram.username || 'linq_safety_bot'} в сети

                    </span>

                  ) : (

                    <span style={{ color: 'var(--subtle)', fontSize: 11 }}>

                      {notifyStatus?.telegram?.status === 'starting' ? 'Запуск long polling...' : (notifyStatus?.telegram?.status || 'Проверка связи...')}

                    </span>

                  )}

                </div>



                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20 }}>

                  {notifyStatus?.telegram?.links?.private && (

                    <a

                      href={notifyStatus.telegram.links.private}

                      target="_blank"

                      rel="noreferrer"

                      style={{

                        display: 'inline-flex',

                        alignItems: 'center',

                        gap: 6,

                        padding: '7px 12px',

                        background: '#e9f1fc',

                        color: '#2072d0',

                        borderRadius: 6,

                        fontSize: 12,

                        fontWeight: 500,

                        textDecoration: 'none',

                      }}

                    >

                      <Send size={13} /> Подключить личные сообщения

                    </a>

                  )}

                  {notifyStatus?.telegram?.links?.group && (

                    <a

                      href={notifyStatus.telegram.links.group}

                      target="_blank"

                      rel="noreferrer"

                      style={{

                        display: 'inline-flex',

                        alignItems: 'center',

                        gap: 6,

                        padding: '7px 12px',

                        background: '#f0f1f3',

                        color: '#374151',

                        borderRadius: 6,

                        fontSize: 12,

                        fontWeight: 500,

                        textDecoration: 'none',

                      }}

                    >

                      <Users size={13} /> Добавить в группу смены

                    </a>

                  )}

                  <Button

                    variant="outline"

                    size="sm"

                    disabled={testSending}

                    onClick={() => handleSendTest()}

                    style={{ fontSize: 12 }}

                  >

                    {testSending ? 'Отправка...' : 'Отправить тест всем'}

                  </Button>

                </div>



                <div style={{ marginTop: 15 }}>

                  <h3 style={{ fontSize: 13, marginBottom: 8, color: '#334155' }}>

                    Зарегистрированные подписчики ({notifyStatus?.subscribers?.length || 0})

                  </h3>

                  {notifyStatus?.subscribers?.length > 0 ? (

                    <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden' }}>

                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>

                        <thead>

                          <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', textAlign: 'left' }}>

                            <th style={{ padding: '8px 12px' }}>Получатель</th>

                            <th style={{ padding: '8px 12px' }}>Тип</th>

                            <th style={{ padding: '8px 12px' }}>Фильтр важности</th>

                            <th style={{ padding: '8px 12px', textAlign: 'right' }}>Действия</th>

                          </tr>

                        </thead>

                        <tbody>

                          {notifyStatus.subscribers.map((sub: any) => (

                            <tr key={sub.id} style={{ borderBottom: '1px solid #f1f5f9' }}>

                              <td style={{ padding: '8px 12px' }}>

                                <strong>{sub.title}</strong>

                                {sub.username && <span style={{ color: '#64748b', marginLeft: 6 }}>@{sub.username}</span>}

                              </td>

                              <td style={{ padding: '8px 12px' }}>

                                <span style={{

                                  background: sub.chat_type === 'private' ? '#e0f2fe' : '#fef3c7',

                                  color: sub.chat_type === 'private' ? '#0369a1' : '#b45309',

                                  padding: '2px 6px',

                                  borderRadius: 4,

                                  fontSize: 10,

                                  fontWeight: 600,

                                }}>

                                  {sub.chat_type === 'private' ? 'Личный' : 'Группа'}

                                </span>

                              </td>

                              <td style={{ padding: '8px 12px' }}>

                                <select

                                  value={sub.min_severity}

                                  onChange={(e) => handleUpdateSubscriber(sub.id, e.target.value)}

                                  style={{ padding: '3px 8px', borderRadius: 4, border: '1px solid #cbd5e1', fontSize: 11 }}

                                >

                                  <option value="info">Все (Инфо + Внимание + Критич.)</option>

                                  <option value="warning">Только Внимание и Критические</option>

                                  <option value="critical">Только Критические</option>

                                </select>

                              </td>

                              <td style={{ padding: '8px 12px', textAlign: 'right' }}>

                                <Button

                                  variant="ghost"

                                  size="sm"

                                  onClick={() => handleSendTest(sub.id)}

                                  style={{ height: 26, padding: '0 8px', fontSize: 11, marginRight: 6 }}

                                  title="Отправить тестовое сообщение"

                                >

                                  <Send size={12} />

                                </Button>

                                <Button

                                  variant="ghost"

                                  size="sm"

                                  onClick={() => handleDeleteSubscriber(sub.id)}

                                  style={{ height: 26, padding: '0 8px', color: '#ef4444' }}

                                  title="Удалить подписчика"

                                >

                                  <Trash2 size={12} />

                                </Button>

                              </td>

                            </tr>

                          ))}

                        </tbody>

                      </table>

                    </div>

                  ) : (

                    <div style={{ padding: '16px', background: '#f8fafc', borderRadius: 8, border: '1px dashed #cbd5e1', textAlign: 'center', color: '#64748b', fontSize: 12 }}>

                      Нет активных подписчиков. Нажмите кнопку выше и отправьте <code>/start</code> боту в Telegram.

                    </div>

                  )}

                </div>

              </section>



              <section className="settings-card">

                <h2>Уведомления системы</h2>

                <div className="setting-row">

                  <div>

                    <strong>Звуковые оповещения</strong>

                    <p>Сигнал при появлении критического события</p>

                  </div>

                  <Switch checked={sound} onCheckedChange={setSound} />

                </div>

              </section>



              <section className="settings-card">

                <h2>Демонстрация системы</h2>

                <div className="setting-row">

                  <div>

                    <strong>Сброс демонстрационных данных</strong>

                    <p>Возвращает исходные статусы всех нарушений</p>

                  </div>

                  <Button

                    variant="outline"

                    size="sm"

                    onClick={() => {

                      localStorage.removeItem('linqsec-events-v1')

                      localStorage.removeItem('tuk-tuk-events-v1')

                      setEvents(initialEvents)

                      notify('Демоданные сброшены к начальному состоянию.')

                    }}

                  >

                    Сбросить

                  </Button>

                </div>

                <div className="setting-row">

                  <div>

                    <strong>Экспорт настроек предприятия</strong>

                    <p>Выгрузить конфигурацию правил и зон в JSON</p>

                  </div>

                  <Button

                    variant="outline"

                    size="sm"

                    onClick={() => {

                      const data = { siteId, zoneRules, customZones, customRules, rulesEnabled }

                      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })

                      const url = URL.createObjectURL(blob)

                      const a = document.createElement('a')

                      a.href = url

                      a.download = `lenqsec-settings-${siteId}.json`

                      a.click()

                      URL.revokeObjectURL(url)

                      notify('Настройки экспортированы.')

                    }}

                  >

                    Выгрузить JSON

                  </Button>

                </div>

              </section>

            </>

          ) : null}

        </div>

      </main>



      <aside className="notification-rail">

        <div className="rail-header">

          <div>

            <strong>События смены</strong>

            <span>{openEvents.length} активных</span>

          </div>

          <div className="rail-header-actions">

            <button

              className={`icon-button ${sound ? 'selected' : ''}`}

              title={sound ? 'Звук включён' : 'Звук выключен'}

              aria-label={sound ? 'Отключить звук' : 'Включить звук'}

              data-tooltip={sound ? 'Звук включён' : 'Звук выключен'}

              onClick={() => {

                setSound((v) => !v)

                notify(!sound ? 'Звуковые оповещения включены' : 'Звук отключён')

              }}

            >

              {sound ? <Volume2 size={16} /> : <VolumeX size={16} />}

            </button>

            <button

              className="icon-button"

              aria-label="Скрыть ленту событий"

              title="Скрыть ленту событий"

              onClick={() => setRailHidden(true)}

            >

              <ChevronRight size={16} />

            </button>

          </div>

        </div>

        <div className="rail-tabs">

          <button

            className={feedTab === 'all' ? 'active' : ''}

            onClick={() => setFeedTab('all')}

          >

            Все <b>{siteEvents.length}</b>

          </button>

          <button

            className={feedTab === 'critical' ? 'active' : ''}

            onClick={() => setFeedTab('critical')}

          >

            Критические <b>{criticalCount}</b>

          </button>

        </div>

        <div className="rail-feed">

          {feedEvents.map((e) => (

            <article

              key={e.id}

              className={`feed-card ${e.severity} ${seen.includes(e.id) ? 'read' : ''} ${selectedId === e.id ? 'active' : ''}`}

              role="button"

              tabIndex={0}

              aria-label={`Открыть событие ${e.id}: ${e.title}`}

              onClick={() => setSelectedId(e.id)}

            >

              <div className="feed-card-header">

                <span className="feed-time">{e.time}</span>

                <span className="feed-camera">{e.camera}</span>

                <SeverityBadge severity={e.severity} short />

              </div>

              <strong>{e.title}</strong>

              <p>{e.zone}</p>

              <div className="feed-card-footer">

                <StatusBadge status={e.status} />

                <label

                  className="feed-read-toggle"

                  onClick={(ev) => ev.stopPropagation()}

                  title={seen.includes(e.id) ? 'Отмечено как прочитанное' : 'Отметить прочитанным'}

                >

                  <input

                    type="checkbox"

                    checked={seen.includes(e.id)}

                    onChange={() => {

                      setSeen((curr) => (curr.includes(e.id) ? curr.filter((x) => x !== e.id) : [...curr, e.id]))

                    }}

                  />

                  <span>Прочитано</span>

                </label>

              </div>

            </article>

          ))}

          {feedEvents.length === 0 ? (

            <div className="empty-rail">

              <CircleCheck size={28} />

              <span>Нет новых уведомлений</span>

            </div>

          ) : null}

        </div>

      </aside>



      {railHidden ? (

        <button

          className="rail-restore"

          aria-label="Показать ленту событий"

          title="Показать ленту событий"

          onClick={() => setRailHidden(false)}

        >

          <Bell size={16} />

        </button>

      ) : null}

      {/* Светофор безопасности: модальное окно последнего скрина нарушения */}
      {selectedTrafficCamera ? (() => {
        const cam = selectedTrafficCamera
        const info = getCameraTrafficInfo(cam)
        const ev = info.primaryEvent
        const snapshotUrl = ev?.image
          ? resolveMediaImage(ev.image)
          : cam.cameraType === 'thermal'
            ? `/api/v1/thermal/cameras/${encodeURIComponent(cam.id)}/heatmap.jpg`
            : `/api/v1/cameras/${encodeURIComponent(cam.id)}/snapshot.jpg?t=${snapshotTimestamp}`

        return (
          <Dialog open={true} onOpenChange={(open) => { if (!open) setSelectedTrafficCamera(null) }}>
            <DialogContent className="traffic-dialog-content">
              <DialogHeader>
                <DialogTitle style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span>Светофор безопасности · Стоп-кадр нарушения</span>
                  <span className={`traffic-summary-pill ${info.statusColor}`} style={{ fontSize: '11px', padding: '3px 10px' }}>
                    {info.statusColor === 'red' ? '🔴 КРИТИЧНО' : info.statusColor === 'yellow' ? '🟡 ВНИМАНИЕ' : '🟢 В НОРМЕ'}
                  </span>
                </DialogTitle>
                <DialogDescription>
                  Камера: <strong>{cam.name} ({cam.id})</strong> · Участок: <strong>{cam.workshop} · {cam.zone}</strong>
                </DialogDescription>
              </DialogHeader>

              <div className="traffic-snapshot-preview">
                <img
                  src={snapshotUrl}
                  alt={`Стоп-кадр нарушения камеры ${cam.id}`}
                  onError={(e) => {
                    if (cam.cameraType === 'thermal') return
                    const fallback = resolveMediaImage(cam.image)
                    if ((e.target as HTMLImageElement).src !== fallback) {
                      (e.target as HTMLImageElement).src = fallback
                    }
                  }}
                />
              </div>

              <div className="traffic-event-details">
                {cam.cameraType === 'thermal' ? (
                  <div style={{ padding: '9px 12px', background: '#fef3c7', border: '1px solid #fde68a', borderRadius: '6px', fontSize: '12px', color: '#92400e', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <strong>Критерий перегрева тепловизора:</strong>
                      <span style={{ fontWeight: 700, color: '#b45309' }}>Порог: T ≥ 21.0°C</span>
                    </div>
                    <span>
                      Аварийный перегрев фиксируется при превышении температуры поверхности 21.0°C в контрольной зоне OSF. Сброс тревоги происходит при охлаждении до 20.0°C.
                    </span>
                  </div>
                ) : null}

                {ev ? (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong style={{ fontSize: '14px', color: '#0f172a' }}>
                        {ev.title}
                      </strong>
                      <span style={{ fontSize: '12px', color: '#64748b' }}>
                        Время: 23.10.2026 {ev.time}
                      </span>
                    </div>
                    <p style={{ margin: 0, fontSize: '13px', color: '#334155' }}>
                      {ev.description}
                    </p>
                    {ev.action ? (
                      <div style={{ padding: '8px 12px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '6px', fontSize: '12px', color: '#1e40af' }}>
                        <strong>Рекомендуемое действие:</strong> {ev.action}
                      </div>
                    ) : null}
                  </>
                ) : (
                  <div style={{ padding: '12px', color: '#047857', fontSize: '13px' }}>
                    ✓ На данной камере в текущую смену нарушений не зафиксировано. Процесс протекает штатно.
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '8px' }}>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedTrafficCamera(null)}
                >
                  Закрыть
                </Button>
                <Button
                  size="sm"
                  onClick={() => {
                    setInspectedCamera(cam)
                    setSelectedTrafficCamera(null)
                  }}
                >
                  <Play size={14} style={{ fill: 'currentColor', marginRight: 6 }} />
                  Перейти к прямому эфиру камеры
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        )
      })() : null}

      {/* Real-time Camera Inspection Dialog with MJPEG / Neural telemetry */}

      <Dialog open={!!inspectedCamera} onOpenChange={(open) => !open && setInspectedCamera(null)}>

        <DialogContent className="max-w-4xl p-0 overflow-hidden bg-slate-950 text-white border-slate-800">

          <DialogTitle className="sr-only">

            {inspectedCamera?.name ?? 'Камера'}

          </DialogTitle>

          <DialogDescription className="sr-only">

            Прямой видеоэфир и нейросетевая аналитика LinQ TPU

          </DialogDescription>

          {inspectedCamera ? (

            <div>

              <div className="flex items-center justify-between px-5 py-3 pr-12 border-b border-slate-800 bg-slate-900/80">

                <div className="flex items-center gap-3">

                  <span className="small-dot green" />

                  <strong className="text-sm font-semibold">{inspectedCamera.id} · {inspectedCamera.name}</strong>

                  {isLiveBackend && inspectedCamera.id === 'CAM-01' && (

                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">

                      LinQ TPU (ONLINE)

                    </span>

                  )}

                  {inspectedCamera.cameraType === 'thermal' && (

                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">

                      ТЕПЛОВИЗОР · Перегрев: T ≥ 21.0°C

                    </span>

                  )}

                </div>

                <div className="flex items-center gap-2">

                  <span className="text-xs text-slate-400">{inspectedCamera.workshop} · {inspectedCamera.zone}</span>

                </div>

              </div>



              <div className="relative aspect-video bg-black flex items-center justify-center overflow-hidden">

                <CameraView

                  camera={inspectedCamera}

                  event={events.find((e) => e.id === inspectedCamera.event)}

                  image={inspectedCamera.image}

                  video={inspectedCamera.video}

                  online={inspectedCamera.online}

                  large

                  showBoxes={showBoxes}

                  playing={true}

                  mode="live"

                  useMjpeg={isLiveBackend && inspectedCamera.id === 'CAM-01'}

                  mjpegUrl="/api/v1/cameras/CAM-01/stream.mjpg"

                  zoom={cameraZoom}

                  onZoomIn={() => setCameraZoom((z) => Math.min(2.5, Number((z + 0.25).toFixed(2))))}

                  onZoomOut={() => setCameraZoom((z) => Math.max(1, Number((z - 0.25).toFixed(2))))}

                  onZoomReset={() => setCameraZoom(1)}

                />

              </div>



              <div className="p-4 bg-slate-900">

                <div className="flex items-center justify-between mb-3">

                  <div>

                    <h3 className="text-sm font-semibold text-slate-200">Видеоаналитика в реальном времени</h3>

                    <p className="text-xs text-slate-400">Нейросетевой модуль детекции СИЗ и нарушений безопасности</p>

                  </div>

                  <div className="flex items-center gap-2">

                    <span className="text-xs text-slate-400">Движок:</span>

                    <strong className="text-xs text-blue-400">LinQ Neural Guard</strong>

                  </div>

                </div>



                <div className="camera-telemetry-panel">

                  <div className="telemetry-card">

                    <span>Скорость инференса</span>

                    <strong>{isLiveBackend && inspectedCamera.id === 'CAM-01' ? '25.0 FPS' : '30.0 FPS'}</strong>

                  </div>

                  <div className="telemetry-card">

                    <span>Задержка (Latency)</span>

                    <strong>{isLiveBackend && inspectedCamera.id === 'CAM-01' ? '18.4 мс' : '14.8 мс'}</strong>

                  </div>

                  <div className="telemetry-card">

                    <span>Аппаратный ускоритель</span>

                    <strong style={{ color: '#2563eb' }}>{isLiveBackend && inspectedCamera.id === 'CAM-01' ? 'LinQ TPU (H1M)' : 'Local ONNX'}</strong>

                  </div>

                  <div className="telemetry-card">

                    <span>Обнаружено объектов</span>

                    <strong>{events.filter((e) => e.camera === inspectedCamera.id && isOpen(e)).length} чел.</strong>

                  </div>

                </div>

              </div>

            </div>

          ) : null}

        </DialogContent>

      </Dialog>



      {/* Event Details Dialog */}

      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelectedId(null)}>

        <DialogContent className="event-dialog max-w-3xl">

          <DialogTitle className="sr-only">

            {selected?.title ?? 'Детали события'}

          </DialogTitle>

          <DialogDescription className="sr-only">

            Карточка инцидента безопасности с видеоподтверждением и контактами ответственных

          </DialogDescription>

          {selected ? (

            <div>

              <div className="detail-eyebrow">

                <span>{selected.id}</span>

                <span>·</span>

                <span>{selected.zone}</span>

                <span>·</span>

                <span>{selected.camera}</span>

                <span>·</span>

                <span>{selected.time}</span>

                <b className="ml-auto">

                  <SeverityBadge severity={selected.severity} />

                </b>

              </div>

              <h2 className="detail-title">{selected.title}</h2>

              <div className="detail-layout">

                <div className="detail-media">

                  <CameraView

                    event={selected}

                    image={selected.image}

                    video={selected.video}

                    online={true}

                    large

                    showBoxes={showBoxes}

                    playing={playing}

                    zoom={cameraZoom}

                    onZoomIn={() => setCameraZoom((z) => Math.min(2.5, Number((z + 0.25).toFixed(2))))}

                    onZoomOut={() => setCameraZoom((z) => Math.max(1, Number((z - 0.25).toFixed(2))))}

                    onZoomReset={() => setCameraZoom(1)}

                  />

                  <div className="clip-controls">

                    <button

                      aria-label={playing ? 'Остановить просмотр' : 'Просмотреть демофрагмент'}

                      onClick={() => setPlaying((v) => !v)}

                    >

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

                    <section className="employee-card">

                      <h3>Сотрудник</h3>

                      <strong>{selected.employee.name}</strong>

                      <span>{selected.employee.role}</span>

                      <small>Табельный: {selected.employee.number} · {selected.employee.access}</small>

                    </section>

                  ) : null}

                  <section className="contact-card">

                    <h3>Связаться</h3>

                    <strong>{selected.contact.name}</strong>

                    <span>{selected.contact.role}</span>

                    <div>

                      <span>Рация: {selected.contact.radio}</span>

                      <a href={`tel:${selected.contact.phone}`}>

                        <Phone size={12} /> {selected.contact.phone}

                      </a>

                    </div>

                  </section>

                </div>

              </div>

              <div className="detail-footer">

                <Button

                  variant="ghost"

                  size="sm"

                  className="feedback-button"

                  title="Обучить ИИ распознавать это как ложное срабатывание"

                  disabled={selected.status === 'dismissed'}

                  onClick={() => updateStatus(selected.id, 'dismissed')}

                >

                  <Sparkles size={14} /> Обучить ИИ: ложное срабатывание

                </Button>

                <div>

                  {selected.status === 'new' ? (

                    <Button

                      variant="outline"

                      size="sm"

                      className="work-button"

                      title="Взять нарушение в работу"

                      onClick={() => updateStatus(selected.id, 'working')}

                    >

                      <Clock3 size={14} /> Взять в работу

                    </Button>

                  ) : null}

                  {selected.status === 'working' ? (

                    <Button

                      variant="outline"

                      size="sm"

                      className="resolve-button"

                      title="Отметить нарушение как устранённое"

                      onClick={() => updateStatus(selected.id, 'resolved')}

                    >

                      <Check size={14} /> Нарушение устранено

                    </Button>

                  ) : null}

                </div>

              </div>

            </div>

          ) : null}

        </DialogContent>

      </Dialog>



      {/* Demo Modal */}

      <Dialog open={modal === 'demo'} onOpenChange={(open) => !open && setModal(null)}>

        <DialogContent className="max-w-md">

          <DialogHeader>

            <DialogTitle>Демонстрационные сценарии</DialogTitle>

            <DialogDescription>

              Выберите типовой инцидент для мгновенного просмотра в интерфейсе:

            </DialogDescription>

          </DialogHeader>

          <div className="demo-options">

            {demoOptions.map(({ label, id, icon: Icon }) => (

              <button

                key={id}

                className="demo-option-item"

                onClick={() => {

                  setModal(null)

                  setSelectedId(id)

                }}

              >

                <span className="demo-option-icon">

                  <Icon size={18} />

                </span>

                <span>{label}</span>

                <ChevronRight size={16} />

              </button>

            ))}

          </div>

        </DialogContent>

      </Dialog>



      {toast ? (

        <div className="toast" role="status" aria-live="polite">

          <Sparkles size={15} />

          <span>{toast}</span>

        </div>

      ) : null}

    </div>

  )

}

