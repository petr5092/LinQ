import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import App from "./App"
import { api } from "./services/api"

vi.mock("./services/api", () => ({
  api: {
    getSites: vi.fn().mockResolvedValue([]),
    getCameras: vi.fn().mockResolvedValue([]),
    getIncidents: vi.fn().mockResolvedValue([
      {
        id: "TK-1048",
        site: "north",
        title: "Сотрудник без каски",
        zone: "Цех № 1",
        camera: "CAM-01",
        time: "14:32:08",
        severity: "critical",
        type: "person",
        description: "Сотрудник находится в зоне работы оборудования без защитной каски.",
        action: "Свяжитесь с мастером смены.",
        image: "workshop",
        status: "new",
        box: [63, 43, 9, 32],
        employee: { name: "Иван Петров", role: "Оператор станка", number: "00482", access: "Разрешён" },
        contact: { name: "Дежурный мастер", role: "Мастер смены", radio: "Канал 4", phone: "+7 (495) 123-45-67" },
      },
      {
        id: "TK-1047",
        site: "north",
        title: "Попытка несанкционированного прохода",
        zone: "Проходная",
        camera: "CAM-08",
        time: "14:31:42",
        severity: "critical",
        type: "access",
        description: "Попытка прохода по чужой карте.",
        action: "Блокировать турникет.",
        image: "gate",
        status: "working",
        box: [40, 20, 10, 30],
        employee: { name: "Пётр Сидоров", role: "Слесарь", number: "00123", access: "Заблокирован" },
        contact: { name: "Пост охраны", role: "Охрана", radio: "Канал 1", phone: "+7 (495) 000-00-00" },
      },
    ]),
    updateStatus: vi.fn().mockResolvedValue(true),
    subscribeToEvents: vi.fn().mockImplementation((_onNew, _onUpdate, onConn) => {
      onConn?.(true)
      return () => {}
    }),
  },
}))

describe("<App /> Component Integration", () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it("renders main brand and navigation bar items", async () => {
    await act(async () => {
      render(<App />)
    })

    const nav = screen.getByRole("navigation", { name: "Основная навигация" })
    expect(within(nav).getByRole("button", { name: "Обзор" })).toBeInTheDocument()
    expect(within(nav).getByRole("button", { name: /Камеры/ })).toBeInTheDocument()
    expect(within(nav).getByRole("button", { name: /Журнал событий/ })).toBeInTheDocument()
    expect(within(nav).getByRole("button", { name: "Зоны и правила" })).toBeInTheDocument()
    expect(within(nav).getByRole("button", { name: "Контроль доступа" })).toBeInTheDocument()
    expect(within(nav).getByRole("button", { name: "Аналитика" })).toBeInTheDocument()
  })

  it("shows API Live indicator when WebSocket connects", async () => {
    await act(async () => {
      render(<App />)
    })

    await waitFor(() => {
      expect(screen.getByTitle(/Подключено к LinQ REST API и WebSocket/i)).toBeInTheDocument()
    })
  })

  it("navigates across pages when navigation items are clicked", async () => {
    await act(async () => {
      render(<App />)
    })

    const nav = screen.getByRole("navigation", { name: "Основная навигация" })

    // Navigate to Камеры
    await act(async () => {
      fireEvent.click(within(nav).getByRole("button", { name: /Камеры/ }))
    })
    expect(screen.getByRole("heading", { level: 1, name: "Видеомониторинг" })).toBeInTheDocument()

    // Navigate to Журнал событий
    await act(async () => {
      fireEvent.click(within(nav).getByRole("button", { name: /Журнал событий/ }))
    })
    expect(screen.getByRole("heading", { level: 1, name: "Журнал событий" })).toBeInTheDocument()

    // Navigate to Аналитика
    await act(async () => {
      fireEvent.click(within(nav).getByRole("button", { name: "Аналитика" }))
    })
    expect(screen.getByRole("heading", { level: 1, name: "Аналитика безопасности" })).toBeInTheDocument()
  })

  it("switches industrial facility (site) correctly", async () => {
    await act(async () => {
      render(<App />)
    })

    const facilitySelect = screen.getByLabelText("Выбор площадки")
    expect(facilitySelect).toHaveValue("north")

    // Switch to south
    await act(async () => {
      fireEvent.change(facilitySelect, { target: { value: "south" } })
    })

    expect(facilitySelect).toHaveValue("south")
    expect(screen.getByText("Южная площадка")).toBeInTheDocument()
  })

  it("filters events by search query in event journal", async () => {
    await act(async () => {
      render(<App />)
    })

    const nav = screen.getByRole("navigation", { name: "Основная навигация" })
    await act(async () => {
      fireEvent.click(within(nav).getByRole("button", { name: /Журнал событий/ }))
    })

    const searchInput = screen.getByPlaceholderText(/Событие, сотрудник или ID/i)
    await act(async () => {
      fireEvent.change(searchInput, { target: { value: "без каски" } })
    })

    const matches = screen.getAllByText("Сотрудник без каски")
    expect(matches.length).toBeGreaterThan(0)
  })

  it("updates incident status and dispatches API update", async () => {
    await act(async () => {
      render(<App />)
    })

    const nav = screen.getByRole("navigation", { name: "Основная навигация" })
    await act(async () => {
      fireEvent.click(within(nav).getByRole("button", { name: /Журнал событий/ }))
    })

    // Click first incident from the list
    const incidentTitles = screen.getAllByText("Сотрудник без каски")
    await act(async () => {
      fireEvent.click(incidentTitles[0])
    })

    // Click "Взять в работу"
    const inWorkButton = screen.getByRole("button", { name: /Взять в работу/i })
    await act(async () => {
      fireEvent.click(inWorkButton)
    })

    expect(api.updateStatus).toHaveBeenCalledWith("TK-1048", "working")
    await waitFor(() => {
      expect(screen.getByText(/Событие взято в работу/i)).toBeInTheDocument()
    })
  })

  it("triggers CSV export without crashing", async () => {
    await act(async () => {
      render(<App />)
    })

    const exportBtn = screen.getByRole("button", { name: /Экспорт/i })
    await act(async () => {
      fireEvent.click(exportBtn)
    })

    await waitFor(() => {
      expect(screen.getByText(/Журнал событий выгружен в CSV/i)).toBeInTheDocument()
    })
  })

  it("displays latest screenshot on overview and opens real-time neural camera view on click", async () => {
    await act(async () => {
      render(<App />)
    })

    // 1. Verify latest screenshot section and badges on the main screen
    expect(screen.getByText(/Последний скриншот системы безопасности/i)).toBeInTheDocument()
    const snapshotBadges = screen.getAllByText(/ПОСЛЕДНИЙ СКРИН/i)
    expect(snapshotBadges.length).toBeGreaterThan(0)

    // 2. Click on camera to enter real-time neural network video view
    const cameraClickButton = screen.getByRole("button", { name: /Открыть камеру CAM-01/i })
    await act(async () => {
      fireEvent.click(cameraClickButton)
    })

    // 3. Verify real-time video modal opens with neural network analytics
    await waitFor(() => {
      expect(screen.getByText(/Видеоаналитика в реальном времени/i)).toBeInTheDocument()
      expect(screen.getByText(/LinQ Neural Guard/i)).toBeInTheDocument()
    })
  })
  it("navigates to Training section and checks safety training materials", async () => {
    await act(async () => {
      render(<App />)
    })

    const nav = screen.getByRole("navigation", { name: "Основная навигация" })
    await act(async () => {
      fireEvent.click(within(nav).getByRole("button", { name: "Обучение" }))
    })

    expect(screen.getByRole("heading", { level: 1, name: "Обучение" })).toBeInTheDocument()
    expect(screen.getByText(/Безопасность начинается с знаний/i)).toBeInTheDocument()
    expect(screen.getByText(/2 из 6/i)).toBeInTheDocument()
    expect(screen.getByText(/Видеоурок/i)).toBeInTheDocument()
    expect(screen.getByText(/Материалы для изучения/i)).toBeInTheDocument()
  })

  it("filters events by type from analytics and shows return button", async () => {
    await act(async () => {
      render(<App />)
    })

    const nav = screen.getByRole("navigation", { name: "Основная навигация" })
    await act(async () => {
      fireEvent.click(within(nav).getByRole("button", { name: "Аналитика" }))
    })

    // Click on type stat button
    const typeBtn = screen.getByRole("button", { name: /Действия сотрудников/i })
    await act(async () => {
      fireEvent.click(typeBtn)
    })

    expect(screen.getByRole("heading", { level: 1, name: "Журнал событий" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Вернуться к аналитике/i })).toBeInTheDocument()

    // Click back to analytics
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Вернуться к аналитике/i }))
    })

    expect(screen.getByRole("heading", { level: 1, name: "Аналитика безопасности" })).toBeInTheDocument()
  })
})
