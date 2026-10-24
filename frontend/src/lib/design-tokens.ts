export const FIGMA_SOURCE =
  "https://www.figma.com/design/BhE5DjEG56PsuPqjShao4X/HR-DS?node-id=449-6176"

// HR-DS · 3. Mode / Light + Dark. Used by the catalog and CSS export.
export const colorTokens = [
  {
    name: "accent",
    light: "#0000000a",
    dark: "#404040",
  },
  {
    name: "accent-foreground",
    light: "#1c1c1c",
    dark: "#fafafa",
  },
  {
    name: "background",
    light: "#ffffff",
    dark: "#131314",
  },
  {
    name: "border",
    light: "#e5e5e5",
    dark: "#ffffff17",
  },
  {
    name: "card",
    light: "#f8f8f8",
    dark: "#19191a",
  },
  {
    name: "card-foreground",
    light: "#121212",
    dark: "#e7e7e7",
  },
  {
    name: "destructive",
    light: "#dc2626",
    dark: "#ef4444",
  },
  {
    name: "destructive-foreground",
    light: "#fef2f2",
    dark: "#fef2f2",
  },
  {
    name: "foreground",
    light: "#121212",
    dark: "#f1f1f1",
  },
  {
    name: "input",
    light: "#00000017",
    dark: "#ffffff17",
  },
  {
    name: "muted",
    light: "#f5f5f5",
    dark: "#262626",
  },
  {
    name: "muted-foreground",
    light: "#0000008a",
    dark: "#ffffff8a",
  },
  {
    name: "popover",
    light: "#ffffff",
    dark: "#222222",
  },
  {
    name: "popover-foreground",
    light: "#121212",
    dark: "#f1f1f1",
  },
  {
    name: "primary",
    light: "#2072d0",
    dark: "#2072d0",
  },
  {
    name: "primary-foreground",
    light: "#fafafa",
    dark: "#fafafa",
  },
  {
    name: "ring",
    light: "#a3a3a3",
    dark: "#737373",
  },
  {
    name: "secondary",
    light: "#f5f5f5",
    dark: "#ffffff1a",
  },
  {
    name: "secondary-foreground",
    light: "#1c1c1c",
    dark: "#e7e7e7",
  },
  {
    name: "ring-offset",
    light: "#ffffff",
    dark: "#131314",
  },
  {
    name: "chart-1",
    light: "#ea580c",
    dark: "#1d4ed8",
  },
  {
    name: "chart-2",
    light: "#0d9488",
    dark: "#10b981",
  },
  {
    name: "chart-3",
    light: "#164e63",
    dark: "#f59e0b",
  },
  {
    name: "chart-4",
    light: "#fbbf24",
    dark: "#a855f7",
  },
  {
    name: "chart-5",
    light: "#f59e0b",
    dark: "#f43f5e",
  },
  {
    name: "sidebar-primary-foreground",
    light: "#f1f1f1",
    dark: "#191919",
  },
  {
    name: "sidebar-primary",
    light: "#1c1c1c",
    dark: "#ffffffeb",
  },
  {
    name: "sidebar-foreground",
    light: "#000000b2",
    dark: "#ffffffb8",
  },
  {
    name: "sidebar",
    light: "#fafafa",
    dark: "#0e0e0e",
  },
  {
    name: "sidebar-accent",
    light: "#0000000a",
    dark: "#ffffff0a",
  },
  {
    name: "sidebar-accent-foreground",
    light: "#000000e5",
    dark: "#ffffffe5",
  },
  {
    name: "sidebar-border",
    light: "#00000000",
    dark: "#ffffff00",
  },
  {
    name: "sidebar-ring",
    light: "#a3a3a3",
    dark: "#525252",
  },
  {
    name: "border-subtle",
    light: "#00000008",
    dark: "#ffffff08",
  },
  {
    name: "sidebar-card",
    light: "#ebebeb",
    dark: "#2e2f31",
  },
] as const

export function exportThemeTokens(root: HTMLElement) {
  const styles = getComputedStyle(root)
  const names = [
    ...colorTokens.map((token) => token.name),
    ...[5, 10, 20, 30, 40, 50, 60, 70, 80, 90].map((step) => `alpha-${step}`),
    ...[20, 40, 60, 70, 90].map((step) => `destructive-${step}`),
    "outline",
    "outline-10",
    "bg-overlay",
    "bg-primary-tint",
    "input-surface",
    "input-accent-surface",
    "input-field",
    "calendar-surface",
    "calendar-accent",
    "border-input",
    "ring-input",
    "field-description",
    "blue-accent",
    "success",
    "radius",
    "radius-xs",
    "radius-sm",
    "radius-md",
    "radius-lg",
    "radius-xl",
    "radius-2xl",
    "radius-3xl",
    "radius-4xl",
    "font-sans",
    "font-mono",
  ]
  return `:root {\n${names.map((name) => `  --${name}: ${styles.getPropertyValue(`--${name}`).trim()};`).join("\n")}\n}`
}
