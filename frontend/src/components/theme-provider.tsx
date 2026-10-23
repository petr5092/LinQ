import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

export const THEME_OPTIONS = [
  { id: "current-dark", family: "hr-vision", mode: "dark", label: "HR Vision" },
  { id: "current-light", family: "hr-vision", mode: "light", label: "HR Vision" },
] as const

export type Theme = (typeof THEME_OPTIONS)[number]["id"]
export type ThemeMode = (typeof THEME_OPTIONS)[number]["mode"]

type ThemeProviderProps = {
  children: React.ReactNode
  defaultTheme?: Theme
  storageKey?: string
}

type ThemeProviderState = {
  theme: Theme
  mode: ThemeMode
  setTheme: (theme: Theme) => void
}

const initialState: ThemeProviderState = {
  theme: "current-dark",
  mode: "dark",
  setTheme: () => null,
}

const ThemeProviderContext = createContext<ThemeProviderState>(initialState)

function resolveStoredTheme(value: string | null, fallback: Theme): Theme {
  if (THEME_OPTIONS.some((option) => option.id === value)) return value as Theme
  if (value === "light") return "current-light"
  if (value === "dark") return "current-dark"
  if (value === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "current-dark"
      : "current-light"
  }
  return fallback
}

export function ThemeProvider({
  children,
  defaultTheme = "current-dark",
  storageKey = "hr-vision-theme",
  ...props
}: ThemeProviderProps) {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === "undefined") return defaultTheme
    return resolveStoredTheme(window.localStorage.getItem(storageKey), defaultTheme)
  })
  const selectedTheme = THEME_OPTIONS.find((option) => option.id === theme) ?? THEME_OPTIONS[0]

  useEffect(() => {
    const root = window.document.documentElement

    root.classList.remove("light", "dark")
    root.dataset.theme = selectedTheme.family
    root.classList.add(selectedTheme.mode)
    root.style.colorScheme = selectedTheme.mode
    window.localStorage.setItem(storageKey, selectedTheme.id)
  }, [selectedTheme, storageKey])

  const updateTheme = useCallback((nextTheme: Theme) => {
    setTheme(nextTheme)
  }, [])

  const value = useMemo(
    () => ({
      theme,
      mode: selectedTheme.mode,
      setTheme: updateTheme,
    }),
    [selectedTheme.mode, theme, updateTheme],
  )

  return (
    <ThemeProviderContext.Provider {...props} value={value}>
      {children}
    </ThemeProviderContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const useTheme = () => {
  const context = useContext(ThemeProviderContext)

  if (context === undefined) throw new Error("useTheme must be used within a ThemeProvider")

  return context
}
