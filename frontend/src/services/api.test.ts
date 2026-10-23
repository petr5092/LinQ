import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  api,
  mapBackendCameraToCamera,
  mapBackendIncidentToSafetyEvent,
} from "./api"
import { cameras as mockCameras, sites as mockSites } from "../data"

describe("api service & data mappers", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe("mapBackendIncidentToSafetyEvent", () => {
    it("maps a full backend incident with structured employee and contact", () => {
      const backendItem = {
        id: "TK-9999",
        site_id: "north",
        camera_id: "CAM-01",
        zone: "Цех № 1",
        title: "Работа без защитных очков",
        time: "15:00:00",
        severity: "critical" as const,
        type: "person" as const,
        description: "Рабочий в опасной зоне без СИЗ",
        action: "Остановить станок",
        snapshot_url: "/static/snapshots/snap1.jpg",
        status: "new" as const,
        box: [10, 20, 30, 40],
        employee: {
          name: "Алексей Смирнов",
          role: "Токарь",
          number: "12345",
          access: "Разрешён",
        },
        contact: {
          name: "Сергей Кузнецов",
          role: "Старший мастер",
          radio: "Канал 2",
          phone: "+7 (999) 000-11-22",
        },
      }

      const event = mapBackendIncidentToSafetyEvent(backendItem)

      expect(event.id).toBe("TK-9999")
      expect(event.site).toBe("north")
      expect(event.camera).toBe("CAM-01")
      expect(event.zone).toBe("Цех № 1")
      expect(event.title).toBe("Работа без защитных очков")
      expect(event.time).toBe("15:00:00")
      expect(event.severity).toBe("critical")
      expect(event.type).toBe("person")
      expect(event.image).toBe("/static/snapshots/snap1.jpg")
      expect(event.box).toEqual([10, 20, 30, 40])
      expect(event.employee?.name).toBe("Алексей Смирнов")
      expect(event.contact.name).toBe("Сергей Кузнецов")
    })

    it("maps flattened employee and contact fields when nested objects are absent", () => {
      const backendItem = {
        id: "TK-1000",
        camera_id: "CAM-02",
        zone: "Склад",
        title: "Превышение скорости погрузчика",
        time: "15:05:00",
        severity: "warning" as const,
        type: "environment" as const,
        status: "working" as const,
        employee_name: "Дмитрий Воронов",
        employee_role: "Водитель погрузчика",
        employee_number: "67890",
        employee_access: "Допуск А3",
        contact_name: "Иван Мастеров",
        contact_role: "Начальник смены",
        contact_radio: "Канал 5",
        contact_phone: "+7 (495) 111-22-33",
      }

      const event = mapBackendIncidentToSafetyEvent(backendItem)

      expect(event.id).toBe("TK-1000")
      expect(event.site).toBe("north") // default fallback
      expect(event.employee?.name).toBe("Дмитрий Воронов")
      expect(event.employee?.role).toBe("Водитель погрузчика")
      expect(event.contact.name).toBe("Иван Мастеров")
      expect(event.box).toEqual([0, 0, 0, 0]) // default box fallback
    })

    it("handles incidents without employee information (e.g. environment or foreign object)", () => {
      const backendItem = {
        id: "TK-2000",
        site_id: "south",
        camera_id: "CAM-31",
        zone: "Зона разгрузки",
        title: "Посторонний предмет в проходе",
        time: "15:10:00",
        severity: "info" as const,
        type: "environment" as const,
        status: "resolved" as const,
      }

      const event = mapBackendIncidentToSafetyEvent(backendItem)

      expect(event.id).toBe("TK-2000")
      expect(event.employee).toBeUndefined()
      expect(event.contact.name).toBe("Мастер смены") // default fallback
      expect(event.image).toBe("workshop") // default fallback
    })
  })

  describe("mapBackendCameraToCamera", () => {
    it("maps backend camera with online flag and placeholder image", () => {
      const backendCam = {
        id: "CAM-10",
        name: "Склад сырья",
        zone: "Склад",
        workshop: "Корпус Б",
        site_id: "north",
        image_placeholder: "warehouse",
        online: true,
      }

      const cam = mapBackendCameraToCamera(backendCam)

      expect(cam.id).toBe("CAM-10")
      expect(cam.name).toBe("Склад сырья")
      expect(cam.site).toBe("north")
      expect(cam.image).toBe("warehouse")
      expect(cam.online).toBe(true)
    })

    it("defaults offline camera correctly", () => {
      const backendCam = {
        id: "CAM-11",
        name: "Периметр восток",
        zone: "Периметр",
        online: false,
      }

      const cam = mapBackendCameraToCamera(backendCam)
      expect(cam.online).toBe(false)
      expect(cam.site).toBe("north")
      expect(cam.workshop).toBe("")
    })
  })

  describe("api.getSites", () => {
    it("fetches sites successfully from /api/v1/sites", async () => {
      const mockBackendSites = [
        {
          id: "north",
          name: "Завод «Северный»",
          subtitle: "Основная площадка",
          workshops: [{ name: "Корпус А", zones: [{ name: "Цех № 1" }] }],
        },
      ]

      vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBackendSites,
      } as Response)

      const sites = await api.getSites()
      expect(sites.length).toBe(1)
      expect(sites[0].id).toBe("north")
      expect(sites[0].workshops[0].zones).toEqual(["Цех № 1"])
    })

    it("falls back to mockSites on network error", async () => {
      vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("Network failure"))

      const sites = await api.getSites()
      expect(sites).toEqual(mockSites)
    })

    it("falls back to mockSites when server returns 500 error", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
        ok: false,
        status: 500,
      } as Response)

      const sites = await api.getSites()
      expect(sites).toEqual(mockSites)
    })
  })

  describe("api.getCameras", () => {
    it("fetches cameras with optional site_id filter", async () => {
      const mockBackendCameras = [
        {
          id: "CAM-01",
          name: "Линия 1",
          zone: "Цех № 1",
          workshop: "Корпус А",
          site_id: "north",
          image_placeholder: "workshop",
          online: true,
        },
      ]

      const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBackendCameras,
      } as Response)

      const cameras = await api.getCameras("north")
      expect(fetchSpy).toHaveBeenCalledWith("/api/v1/cameras?site_id=north")
      expect(cameras.length).toBe(1)
      expect(cameras[0].id).toBe("CAM-01")
    })

    it("falls back to mockCameras when request fails", async () => {
      vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("API offline"))

      const cameras = await api.getCameras()
      expect(cameras).toEqual(mockCameras)
    })
  })

  describe("api.getIncidents", () => {
    it("parses paginated items response", async () => {
      const mockResponse = {
        items: [
          {
            id: "TK-101",
            site_id: "north",
            camera_id: "CAM-01",
            zone: "Цех № 1",
            title: "Инцидент 1",
            time: "10:00:00",
            severity: "warning",
            type: "person",
            status: "new",
          },
        ],
        total: 1,
      }

      vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      } as Response)

      const incidents = await api.getIncidents("north")
      expect(incidents.length).toBe(1)
      expect(incidents[0].id).toBe("TK-101")
    })

    it("returns empty array on network failure", async () => {
      vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("Connection refused"))

      const incidents = await api.getIncidents()
      expect(incidents).toEqual([])
    })
  })

  describe("api.updateStatus", () => {
    it("sends PATCH request with new status and returns true on 200 OK", async () => {
      const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
        ok: true,
        status: 200,
      } as Response)

      const success = await api.updateStatus("TK-1048", "working")

      expect(success).toBe(true)
      expect(fetchSpy).toHaveBeenCalledWith(
        "/api/v1/incidents/TK-1048/status",
        expect.objectContaining({
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "working" }),
        })
      )
    })

    it("returns false when PATCH request fails", async () => {
      vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("Network timeout"))

      const success = await api.updateStatus("TK-1048", "resolved")
      expect(success).toBe(false)
    })
  })

  describe("api.subscribeToEvents (WebSocket)", () => {
    it("creates WebSocket connection and handles events", () => {
      const mockWsInstances: any[] = []

      class MockWebSocket {
        url: string
        readyState = 1 // OPEN
        onopen: (() => void) | null = null
        onmessage: ((event: { data: string }) => void) | null = null
        onerror: (() => void) | null = null
        onclose: (() => void) | null = null

        constructor(url: string) {
          this.url = url
          mockWsInstances.push(this)
        }

        send = vi.fn()
        close = vi.fn()
      }

      vi.stubGlobal("WebSocket", MockWebSocket)

      const onNewIncident = vi.fn()
      const onStatusUpdate = vi.fn()
      const onConnectionChange = vi.fn()

      const unsubscribe = api.subscribeToEvents(onNewIncident, onStatusUpdate, onConnectionChange)

      expect(mockWsInstances.length).toBe(1)
      const ws = mockWsInstances[0]

      // Simulate connection open
      ws.onopen()
      expect(onConnectionChange).toHaveBeenCalledWith(true)

      // Simulate INCIDENT_CREATED
      ws.onmessage({
        data: JSON.stringify({
          event: "INCIDENT_CREATED",
          data: {
            id: "TK-NEW-1",
            site_id: "north",
            camera_id: "CAM-01",
            zone: "Цех № 1",
            title: "Новое нарушение в реальном времени",
            time: "15:20:00",
            severity: "critical",
            type: "person",
            status: "new",
          },
        }),
      })

      expect(onNewIncident).toHaveBeenCalledTimes(1)
      expect(onNewIncident.mock.calls[0][0].id).toBe("TK-NEW-1")

      // Simulate INCIDENT_STATUS_UPDATED
      ws.onmessage({
        data: JSON.stringify({
          event: "INCIDENT_STATUS_UPDATED",
          data: {
            id: "TK-NEW-1",
            status: "resolved",
          },
        }),
      })

      expect(onStatusUpdate).toHaveBeenCalledWith("TK-NEW-1", "resolved")

      // Unsubscribe closes the socket
      unsubscribe()
      expect(ws.close).toHaveBeenCalled()

      vi.unstubAllGlobals()
    })
  })
})
