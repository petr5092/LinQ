import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  RadialBar,
  RadialBarChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import {
  ChartCard,
  ChartContainer,
  ChartLegend,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"

// The bar specimen preserves the sample order and proportions in HR-DS 17085:181830.
const barData = [
  { month: "Apr", desktop: 56 },
  { month: "Mar", desktop: 152 },
  { month: "Jan", desktop: 104 },
  { month: "Feb", desktop: 24 },
  { month: "May", desktop: 56 },
  { month: "Jun", desktop: 120 },
]
const monthlyData = [
  { month: "Jan", desktop: 186 },
  { month: "Feb", desktop: 305 },
  { month: "Mar", desktop: 237 },
  { month: "Apr", desktop: 73 },
  { month: "May", desktop: 209 },
  { month: "Jun", desktop: 214 },
]
const radarData = monthlyData.map((entry, index) => ({
  ...entry,
  fullMonth: ["January", "February", "March", "April", "May", "June"][index],
  comparison: [80, 200, 120, 190, 130, 140][index],
}))
const distribution = [
  { name: "Chrome", value: 337.5, fill: "var(--chart-1)" },
  { name: "Safari", value: 247.5, fill: "var(--chart-2)" },
  { name: "Firefox", value: 225, fill: "var(--chart-3)" },
  { name: "Edge", value: 202.5, fill: "var(--chart-4)" },
  { name: "Other", value: 112.5, fill: "var(--chart-5)" },
]
const radialData = distribution.map((entry, index) => ({
  ...entry,
  value: [100, 27, 40, 58, 83][index],
}))
const config = { desktop: { label: "Item 1", color: "var(--chart-1)" } } satisfies ChartConfig
const axis = {
  tickLine: false,
  axisLine: false,
  tickMargin: 12,
  tick: { fontSize: 12, fill: "var(--muted-foreground)" },
  interval: 0 as const,
  height: 35,
}

function ChartFooter() {
  return (
    <div className="flex flex-col gap-2 leading-none">
      <span className="flex items-center gap-2 font-medium">
        Trending up by 5.2% this month
        <img
          src="/assets/hr-chart/trending-up.svg"
          width={16}
          height={16}
          alt=""
          className="dark:invert"
        />
      </span>
      <span className="text-muted-foreground">Showing total visitors for the last 6 months</span>
    </div>
  )
}

export default function ChartExamples() {
  return (
    <div className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
      <ChartCard
        title="Bar Chart"
        description="January - June 2024"
        docsHref="https://ui.shadcn.com/charts#bar-chart"
        footer={<ChartFooter />}
      >
        <ChartContainer config={config} aria-label="Bar chart of monthly visitors">
          <BarChart
            data={barData}
            margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
            barCategoryGap={6}
          >
            <CartesianGrid vertical={false} stroke="var(--border-subtle)" strokeWidth={0.5} />
            <XAxis dataKey="month" {...axis} />
            <YAxis hide domain={[0, 200]} ticks={[0, 50, 100, 150, 200]} />
            <Tooltip cursor={{ fill: "var(--accent)" }} content={<ChartTooltipContent />} />
            <Bar
              dataKey="desktop"
              fill="var(--color-desktop)"
              radius={8}
              isAnimationActive={false}
            />
          </BarChart>
        </ChartContainer>
      </ChartCard>
      <ChartCard title="Area Chart" description="January - June 2024" footer={<ChartFooter />}>
        <div className="flex flex-col gap-3">
          <ChartContainer config={config} aria-label="Area chart of monthly visitors">
            <AreaChart data={monthlyData} margin={{ top: 0, right: 12, bottom: 0, left: 12 }}>
              <CartesianGrid vertical={false} stroke="var(--border-subtle)" strokeWidth={0.5} />
              <XAxis dataKey="month" {...axis} />
              <YAxis hide domain={[0, 400]} ticks={[0, 100, 200, 300, 400]} />
              <Tooltip content={<ChartTooltipContent indicator="line" />} />
              <Area
                type="natural"
                dataKey="desktop"
                fill="var(--color-desktop)"
                fillOpacity={0.4}
                stroke="var(--color-desktop)"
                strokeWidth={1}
                isAnimationActive={false}
              />
            </AreaChart>
          </ChartContainer>
          <ChartLegend config={config} />
        </div>
      </ChartCard>
      <ChartCard title="Line Chart" description="January - June 2024" footer={<ChartFooter />}>
        <div className="flex flex-col gap-3">
          <ChartContainer config={config} aria-label="Line chart of monthly visitors">
            <LineChart data={monthlyData} margin={{ top: 0, right: 12, bottom: 0, left: 12 }}>
              <CartesianGrid vertical={false} stroke="var(--border-subtle)" strokeWidth={0.5} />
              <XAxis dataKey="month" {...axis} />
              <YAxis hide domain={[0, 400]} ticks={[0, 100, 200, 300, 400]} />
              <Tooltip content={<ChartTooltipContent indicator="line" />} />
              <Line
                type="natural"
                dataKey="desktop"
                dot={false}
                stroke="var(--color-desktop)"
                strokeWidth={2}
                isAnimationActive={false}
              />
            </LineChart>
          </ChartContainer>
          <ChartLegend config={config} />
        </div>
      </ChartCard>
      <ChartCard title="Donut Chart" description="January - June 2024" footer={<ChartFooter />}>
        <div className="relative">
          <ChartContainer config={{}} aria-label="Donut chart of browser visitors">
            <PieChart>
              <Tooltip content={<ChartTooltipContent />} />
              <Pie
                data={distribution}
                dataKey="value"
                nameKey="name"
                innerRadius={60}
                outerRadius={96}
                startAngle={0}
                endAngle={360}
                stroke="var(--card)"
                strokeWidth={0.5}
                isAnimationActive={false}
              />
            </PieChart>
          </ChartContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-3xl font-bold leading-9">1125</span>
            <span className="text-xs leading-4 text-muted-foreground">Visitors</span>
          </div>
        </div>
      </ChartCard>
      <ChartCard title="Radar Chart" description="January - June 2024" footer={<ChartFooter />}>
        <div className="flex flex-col gap-3">
          <ChartContainer
            config={config}
            className="h-[246px]"
            aria-label="Radar chart of monthly visitors"
          >
            <RadarChart data={radarData} outerRadius={96}>
              <PolarGrid stroke="var(--border-subtle)" />
              <PolarAngleAxis
                dataKey="fullMonth"
                tick={({ x, y, payload, textAnchor }) => {
                  const entry = radarData.find((item) => item.fullMonth === payload.value)
                  return (
                    <g transform={`translate(${x},${y})`}>
                      <text
                        textAnchor={textAnchor}
                        fill="var(--card-foreground)"
                        fontSize={12}
                        y={-4}
                      >
                        {entry?.desktop}/{entry?.comparison}
                      </text>
                      <text
                        textAnchor={textAnchor}
                        fill="var(--muted-foreground)"
                        fontSize={12}
                        y={10}
                      >
                        {payload.value}
                      </text>
                    </g>
                  )
                }}
              />
              <PolarRadiusAxis
                angle={60}
                domain={[0, 320]}
                ticks={[0, 80, 160, 240, 320]}
                tick={({ x, y, payload }) => (
                  <text
                    x={x}
                    y={y}
                    textAnchor="middle"
                    transform={`rotate(30 ${x} ${y})`}
                    fill="var(--foreground)"
                    fontSize={12}
                  >
                    {payload.value}
                  </text>
                )}
                axisLine={false}
              />
              <Tooltip content={<ChartTooltipContent />} />
              <Radar
                dataKey="desktop"
                fill="var(--color-desktop)"
                fillOpacity={0.6}
                stroke="none"
                isAnimationActive={false}
              />
            </RadarChart>
          </ChartContainer>
          <ChartLegend config={config} />
        </div>
      </ChartCard>
      <ChartCard title="Radial Chart" description="January - June 2024" footer={<ChartFooter />}>
        <ChartContainer config={{}} aria-label="Radial chart of browser visitors">
          <RadialBarChart
            data={radialData}
            innerRadius={24}
            outerRadius={100}
            startAngle={0}
            endAngle={360}
            barSize={12}
          >
            <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
            <Tooltip content={<ChartTooltipContent />} />
            <RadialBar
              dataKey="value"
              background={{ fill: "var(--muted)" }}
              isAnimationActive={false}
            />
          </RadialBarChart>
        </ChartContainer>
      </ChartCard>
    </div>
  )
}
