import type { Camera, EventStatus, SafetyEvent, Severity, Site, SiteId } from '../data'
import { cameras as mockCameras, sites as mockSites } from '../data'

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

  async getIncidents(siteId?: string): Promise<SafetyEvent[]> {
    try {
      const url = siteId ? `${API_BASE}/incidents?site_id=${siteId}&size=100` : `${API_BASE}/incidents?size=100`
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: IncidentsResponse | BackendIncident[] = await res.json()
      const items = Array.isArray(data) ? data : data.items || []
      if (Array.isArray(items) && items.length > 0) {
        return items.map(mapBackendIncidentToSafetyEvent)
      }
    } catch {
      // Fallback handled by caller
    }
    return []
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
    onConnectionChange?: (connected: boolean) => void
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
            if (payload.event === 'INCIDENT_CREATED' && payload.data) {
              const incident = mapBackendIncidentToSafetyEvent(payload.data)
              onNewIncident(incident)
            } else if (payload.event === 'INCIDENT_STATUS_UPDATED' && payload.data && payload.data.status) {
              onStatusUpdate(payload.data.id, payload.data.status)
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
}
