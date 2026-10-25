import type { Camera, EventStatus, SafetyEvent, Severity, Site, SiteId } from '../data'
import { cameras as mockCameras, sites as mockSites } from '../data'

export interface TelegramLinks {
  group: string | null
  channel: string | null
  private: string | null
}

export interface TelegramChannelInfo {
  configured: boolean
  status: string
  error: string | null
  username: string | null
  links: TelegramLinks
}

export interface NotificationSubscriber {
  id: number
  channel: string
  chat_id: string
  title: string | null
  kind: string | null
  min_severity: string
  active: number
  added_by?: string | null
  added_ts?: number | null
}

export interface DeliveryLogItem {
  id: number
  event_id: string
  channel: string
  chat_id: string
  message_id: string | null
  kind: string | null
  ok: number
  error: string | null
  sent_ts: number | null
  latency_ms: number | null
}

export interface NotificationsStatusResponse {
  telegram: TelegramChannelInfo
  netio: {
    configured: boolean
  }
  subscribers: NotificationSubscriber[]
  stats: Record<string, any>
  deliveries?: DeliveryLogItem[]
}

export interface AnalyticsSummary {
  date: string
  incidents: {
    total: number
    active: number
    new: number
    working: number
    resolved: number
    dismissed: number
  }
  severity: {
    critical: number
    warning: number
    info: number
  }
  cameras: {
    total: number
    online: number
    offline: number
  }
  today: {
    total: number
    hourly: number[]
    by_zone: { name: string; count: number }[]
    by_type: { name: string; count: number }[]
  }
}

export interface BrowserCameraFrameResult {
  camera_id: string
  width: number
  height: number
  detections: {
    class_name: string
    confidence: number
    bbox: [number, number, number, number]
  }[]
  violations: {
    description: string
    class_name: string
    bbox: [number, number, number, number]
  }[]
  new_incidents: string[]
  metrics: {
    backend: string
    inference_ms: number
    fps: number
  }
}

export interface BrowserCameraRegistration {
  id: string
}

const API_BASE = '/api/v1'

interface BackendEmployee {
  name?: string
  role?: string
  number?: string
  access?: string
}

interface BackendContact {
  name?: string
  role?: string
  radio?: string
  phone?: string
}

interface BackendIncident {
  id: string
  site_id?: string
  camera_id: string
  zone: string
  title: string
  time: string
  severity: Severity
  type: 'person' | 'environment' | 'access'
  description?: string
  action?: string
  image_key?: string
  snapshot_url?: string
  video_url?: string
  video?: string
  status: EventStatus
  box?: number[]
  confidence?: number
  employee?: BackendEmployee
  contact?: BackendContact
  employee_name?: string
  employee_role?: string
  employee_number?: string
  employee_access?: string
  contact_name?: string
  contact_role?: string
  contact_radio?: string
  contact_phone?: string
}

interface BackendCamera {
  id: string
  name: string
  zone: string
  workshop?: string
  site_id?: string
  image_placeholder?: string
  rtsp_url?: string
  video?: string
  online?: boolean
  camera_type?: 'visible' | 'thermal'
}

export interface ThermalMeasurement {
  zone_id: string
  zone_name: string
  roi: [number, number, number, number]
  min_temperature_c: number
  mean_temperature_c: number
  max_temperature_c: number
  hot_pixels: number
  threshold_c: number
  alarm: boolean
  severity: Severity
}

export interface ThermalLatestFrame {
  camera_id: string
  captured_at: string
  width: number
  height: number
  minimum_temperature_c: number
  maximum_temperature_c: number
  measurements: ThermalMeasurement[]
  heatmap_jpeg_base64: string
}

export interface ThermalReading {
  zone_id: string
  captured_at: string
  min_temperature_c: number
  mean_temperature_c: number
  max_temperature_c: number
  threshold_c: number
  hot_pixels: number
  alarm: boolean
}

interface BackendZone {
  id?: string
  name: string
}

interface BackendWorkshop {
  name: string
  zones?: (string | BackendZone)[]
}

interface BackendSite {
  id: string
  name: string
  subtitle?: string
  workshops?: BackendWorkshop[]
}

interface IncidentsResponse {
  items?: BackendIncident[]
  total?: number
  page?: number
  size?: number
}

function getWsUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host || 'localhost:3000'
  return `${protocol}//${host}/ws/events`
}

export function mapBackendIncidentToSafetyEvent(item: BackendIncident): SafetyEvent {
  return {
    id: item.id,
    site: (item.site_id || 'north') as SiteId,
    title: item.title,
    zone: item.zone,
    camera: item.camera_id,
    time: item.time,
    severity: item.severity,
    type: item.type,
    description: item.description || '',
    action: item.action || '',
    image: item.snapshot_url || item.image_key || 'workshop',
    video: item.video_url || item.video || (item.camera_id === 'CAM-01' ? '/videos/construction_safety.mp4' : undefined),
    employee: item.employee?.name
      ? {
          name: item.employee.name,
          role: item.employee.role || '',
          number: item.employee.number || '',
          access: item.employee.access || '',
        }
      : item.employee_name
        ? {
            name: item.employee_name,
            role: item.employee_role || '',
            number: item.employee_number || '',
            access: item.employee_access || '',
          }
        : undefined,
    contact: {
      name: item.contact?.name || item.contact_name || 'Мастер смены',
      role: item.contact?.role || item.contact_role || 'Дежурный мастер',
      radio: item.contact?.radio || item.contact_radio || 'Канал 4',
      phone: item.contact?.phone || item.contact_phone || '+7 (495) 123-45-67',
    },
    status: item.status,
    box: Array.isArray(item.box) && item.box.length === 4 ? (item.box as [number, number, number, number]) : [0, 0, 0, 0],
    confidence: typeof item.confidence === 'number' ? item.confidence : undefined,
  }
}

export function mapBackendCameraToCamera(item: BackendCamera): Camera {
  return {
    id: item.id,
    name: item.name,
    zone: item.zone,
    workshop: item.workshop || '',
    site: (item.site_id || 'north') as SiteId,
    image: item.image_placeholder || 'workshop',
    video: item.rtsp_url || item.video || (item.id === 'CAM-01' ? '/videos/construction_safety.mp4' : undefined),
    event: item.id === 'CAM-01' ? 'TK-1048' : undefined,
    online: item.online ?? true,
    cameraType: item.camera_type ?? 'visible',
  }
}

export const api = {
  async getSites(): Promise<Site[]> {
    try {
      const res = await fetch(`${API_BASE}/sites`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: BackendSite[] = await res.json()
      if (Array.isArray(data) && data.length > 0) {
        return data.map((s) => ({
          id: s.id as SiteId,
          name: s.name,
          subtitle: s.subtitle || '',
          workshops: (s.workshops || []).map((w) => ({
            name: w.name,
            zones: (w.zones || []).map((z) => (typeof z === 'string' ? z : z.name)),
          })),
        }))
      }
    } catch {
      // Graceful fallback to mock data
    }
    return mockSites
  },

  async getCameras(siteId?: string): Promise<Camera[]> {
    try {
      const url = siteId ? `${API_BASE}/cameras?site_id=${siteId}` : `${API_BASE}/cameras`
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: BackendCamera[] = await res.json()
      if (Array.isArray(data) && data.length > 0) {
        return data.map(mapBackendCameraToCamera)
      }
    } catch {
      // Graceful fallback to mock cameras
    }
    return mockCameras
  },

  async getIncidents(siteId?: string): Promise<SafetyEvent[] | null> {
    try {
      const url = siteId ? `${API_BASE}/incidents?site_id=${siteId}&size=100` : `${API_BASE}/incidents?size=100`
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: IncidentsResponse | BackendIncident[] = await res.json()
      const items = Array.isArray(data) ? data : data.items || []
      return items.map(mapBackendIncidentToSafetyEvent)
    } catch {
      return null
    }
  },

  async getAnalyticsSummary(siteId: string): Promise<AnalyticsSummary> {
    const res = await fetch(`${API_BASE}/analytics/summary?site_id=${encodeURIComponent(siteId)}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  },

  async getLatestThermalFrame(cameraId: string): Promise<ThermalLatestFrame> {
    const res = await fetch(`${API_BASE}/thermal/cameras/${encodeURIComponent(cameraId)}/latest`, { cache: 'no-store' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  },

  async getThermalReadings(cameraId: string, zoneId?: string): Promise<ThermalReading[]> {
    const params = new URLSearchParams({ limit: '120' })
    if (zoneId) params.set('zone_id', zoneId)
    const res = await fetch(`${API_BASE}/thermal/cameras/${encodeURIComponent(cameraId)}/readings?${params}`, { cache: 'no-store' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  },

  async processBrowserCameraFrame(cameraId: string, frame: Blob): Promise<BrowserCameraFrameResult> {
    const res = await fetch(`${API_BASE}/worker/browser-frame/${encodeURIComponent(cameraId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'image/jpeg' },
      body: frame,
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      throw new Error(typeof data.detail === 'string' ? data.detail : `Ошибка обработки камеры: HTTP ${res.status}`)
    }
    return data as BrowserCameraFrameResult
  },

  async registerBrowserCamera(
    siteId: string,
    name: string,
    zone: string,
    workshop: string,
  ): Promise<BrowserCameraRegistration> {
    const id = `BROWSER-${crypto.randomUUID()}`
    const res = await fetch(`${API_BASE}/cameras`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id,
        name,
        zone,
        workshop,
        site_id: siteId,
        image_placeholder: 'workshop',
        online: false,
        fps: 2,
      }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      throw new Error(typeof data.detail === 'string' ? data.detail : `Не удалось зарегистрировать камеру: HTTP ${res.status}`)
    }
    return { id: data.id as string }
  },

  async setBrowserCameraOnline(cameraId: string, online: boolean): Promise<void> {
    const res = await fetch(`${API_BASE}/cameras/${encodeURIComponent(cameraId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ online }),
    })
    if (!res.ok) throw new Error(`Не удалось обновить статус камеры: HTTP ${res.status}`)
  },

  async updateStatus(id: string, status: EventStatus): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE}/incidents/${id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      return res.ok
    } catch {
      return false
    }
  },

  subscribeToEvents(
    onNewIncident: (incident: SafetyEvent) => void,
    onStatusUpdate: (id: string, status: EventStatus) => void,
    onConnectionChange?: (connected: boolean) => void,
    onIncidentUpdated?: (incident: SafetyEvent) => void
  ): () => void {
    let ws: WebSocket | null = null
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null
    let pingInterval: ReturnType<typeof setInterval> | null = null
    let isClosed = false

    function connect() {
      if (isClosed) return
      try {
        ws = new WebSocket(getWsUrl())

        ws.onopen = () => {
          onConnectionChange?.(true)
          pingInterval = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send('ping')
            }
          }, 25000)
        }

        ws.onmessage = (event) => {
          if (event.data === 'pong') return
          try {
            const payload = JSON.parse(event.data) as {
              event?: string
              data?: BackendIncident & { status?: EventStatus }
            }
            if ((payload.event === 'INCIDENT_CREATED' || payload.event === 'INCIDENT_NEW') && payload.data) {
              const incident = mapBackendIncidentToSafetyEvent(payload.data)
              onNewIncident(incident)
            } else if (payload.event === 'INCIDENT_UPDATED' && payload.data) {
              const incident = mapBackendIncidentToSafetyEvent(payload.data)
              if (onIncidentUpdated) onIncidentUpdated(incident)
              else onNewIncident(incident)
            } else if ((payload.event === 'INCIDENT_STATUS_UPDATED' || payload.event === 'INCIDENT_STATUS_CHANGED') && payload.data && payload.data.status) {
              onStatusUpdate(payload.data.id, payload.data.status)
              if (payload.data.title && onIncidentUpdated) {
                onIncidentUpdated(mapBackendIncidentToSafetyEvent(payload.data))
              }
            }
          } catch {
            // Ignore non-json
          }
        }

        ws.onerror = () => {
          onConnectionChange?.(false)
        }

        ws.onclose = () => {
          onConnectionChange?.(false)
          if (pingInterval) clearInterval(pingInterval)
          if (!isClosed) {
            reconnectTimeout = setTimeout(connect, 5000)
          }
        }
      } catch {
        onConnectionChange?.(false)
        if (!isClosed) {
          reconnectTimeout = setTimeout(connect, 5000)
        }
      }
    }

    connect()

    return () => {
      isClosed = true
      if (pingInterval) clearInterval(pingInterval)
      if (reconnectTimeout) clearTimeout(reconnectTimeout)
      if (ws) ws.close()
    }
  },

  async getNotificationsStatus(): Promise<NotificationsStatusResponse | null> {
    try {
      const res = await fetch(`${API_BASE}/notifications/status`)
      if (!res.ok) return null
      return (await res.json()) as NotificationsStatusResponse
    } catch {
      return null
    }
  },

  async sendTestNotification(subscriberId?: number): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE}/notifications/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subscriber_id: subscriberId }),
      })
      return res.ok
    } catch {
      return false
    }
  },

  async updateSubscriber(subscriberId: number, data: { min_severity?: string; active?: boolean; delete?: boolean }): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE}/notifications/subscribers/${subscriberId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      return res.ok
    } catch {
      return false
    }
  },

  async syncTelegramAlerts(): Promise<{ ok: boolean; synced_count: number }> {
    try {
      const res = await fetch(`${API_BASE}/notifications/sync`, { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return (await res.json()) as { ok: boolean; synced_count: number }
    } catch {
      return { ok: false, synced_count: 0 }
    }
  },

  async getNotificationZoneRules(): Promise<Record<string, boolean>> {
    try {
      const res = await fetch(`${API_BASE}/notifications/rules`)
      if (!res.ok) return {}
      const data = await res.json()
      return data?.rules ?? {}
    } catch {
      return {}
    }
  },

  async setNotificationZoneRule(zone: string, rule: string, enabled: boolean): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE}/notifications/rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ zone, rule, enabled }),
      })
      return res.ok
    } catch {
      return false
    }
  },

  async getDeliveries(limit = 50, failedOnly = false): Promise<DeliveryLogItem[]> {
    try {
      const res = await fetch(`${API_BASE}/notifications/deliveries?limit=${limit}&failed_only=${failedOnly}`)
      if (!res.ok) return []
      return (await res.json()) as DeliveryLogItem[]
    } catch {
      return []
    }
  },

}
