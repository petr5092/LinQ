import {
  createContext,
  useContext,
  type ComponentProps,
  type CSSProperties,
  type ReactElement,
  type ReactNode,
} from "react"
import { ResponsiveContainer } from "recharts"
import { cn } from "@/lib/utils"

type ChartConfig = Record<string, { label: ReactNode; color: string }>
const ChartContext = createContext<ChartConfig>({})

function ChartContainer({
  config,
  children,
  className,
  style,
  ...props
}: ComponentProps<"div"> & { config: ChartConfig; children: ReactElement }) {
  const colors = Object.fromEntries(
    Object.entries(config).map(([key, value]) => [`--color-${key}`, value.color]),
  )
  return (
    <ChartContext.Provider value={config}>
      <div
        data-slot="chart"
        className={cn(
          "h-[235px] min-w-0 text-xs [&_.recharts-cartesian-axis-tick_text]:fill-muted-foreground [&_.recharts-polar-angle-axis-tick_text]:fill-muted-foreground [&_.recharts-polar-radius-axis-tick_text]:fill-foreground [&_.recharts-surface]:outline-none",
          className,
        )}
        style={{ ...colors, ...style } as CSSProperties}
        {...props}
      >
        <ResponsiveContainer
          width="100%"
          height="100%"
          minWidth={0}
          initialDimension={{ width: 336, height: 235 }}
        >
          {children}
        </ResponsiveContainer>
      </div>
    </ChartContext.Provider>
  )
}

type TooltipEntry = {
  dataKey?: string | number
  name?: string | number
  value?: number | string | (string | number)[]
  color?: string
}
type ChartTooltipContentProps = {
  active?: boolean
  label?: ReactNode
  payload?: readonly TooltipEntry[]
  indicator?: "dot" | "line"
}

function ChartTooltipContent({
  active,
  payload,
  label,
  indicator = "dot",
}: ChartTooltipContentProps) {
  const config = useContext(ChartContext)
  if (!active || !payload?.length) return null
  return (
    <div
      role="tooltip"
      className="grid min-w-[139px] gap-2 rounded-sm border-[0.5px] border-border bg-popover p-2 text-xs leading-3 text-popover-foreground shadow-md"
    >
      {label != null && <span className="font-medium">{label}</span>}
      {payload.map((entry, index) => {
        const item = config[String(entry.dataKey)]
        return (
          <div key={`${entry.dataKey}-${index}`} className="flex items-center gap-2">
            <span
              className={cn(
                "shrink-0 rounded-[2px]",
                indicator === "line" ? "h-3 w-0.5" : "size-2",
              )}
              style={{ backgroundColor: item?.color ?? entry.color }}
            />
            <span className="flex-1 text-muted-foreground">{item?.label ?? entry.name}</span>
            <span className="font-mono font-medium tabular-nums">
              {Array.isArray(entry.value) ? entry.value.join("–") : entry.value}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function ChartLegend({ config, className }: { config: ChartConfig; className?: string }) {
  return (
    <div
      data-slot="chart-legend"
      className={cn(
        "flex flex-wrap items-center justify-center gap-4 text-xs leading-4",
        className,
      )}
    >
      {Object.entries(config).map(([key, item]) => (
        <span key={key} className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-full" style={{ backgroundColor: item.color }} />
          {item.label}
        </span>
      ))}
    </div>
  )
}

function ChartCard({
  title,
  description,
  children,
  footer,
  className,
  docsHref = "https://ui.shadcn.com/charts",
  ...props
}: ComponentProps<"article"> & {
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  docsHref?: string
}) {
  return (
    <article
      data-slot="chart-card"
      className={cn(
        "min-w-0 overflow-hidden rounded-lg border-[0.5px] border-border bg-card text-card-foreground shadow-xs",
        className,
      )}
      {...props}
    >
      <div className="flex h-11 items-center justify-between border-b-[0.5px] border-border px-3 py-2.5">
        <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <img
            src="/assets/hr-chart/bar-chart.svg"
            width={16}
            height={16}
            alt=""
            className="dark:invert"
          />
          Chart
        </span>
        <a
          href={docsHref}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 text-base underline underline-offset-2"
        >
          View docs
          <img
            src="/assets/hr-chart/external-link.svg"
            width={16}
            height={16}
            alt=""
            className="dark:invert"
          />
        </a>
      </div>
      <div className="flex flex-col gap-6 p-6">
        <div className="flex flex-col gap-1.5">
          <span className="text-base font-semibold leading-none tracking-[-0.4px]">{title}</span>
          {description && (
            <span className="text-sm leading-5 text-muted-foreground">{description}</span>
          )}
        </div>
        {children}
        {footer && <div className="text-sm leading-5">{footer}</div>}
      </div>
    </article>
  )
}

export { ChartContainer, ChartTooltipContent, ChartLegend, ChartCard }
export type { ChartConfig }
