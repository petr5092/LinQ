import { useState } from "react"
import {
  Bell,
  BriefcaseBusiness,
  CalendarDays,
  ChevronRight,
  House,
  LayoutGrid,
  Settings,
  Users,
} from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInput,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { useSidebar } from "@/components/ui/use-sidebar"

const items = [
  { label: "Overview", icon: House, count: undefined },
  { label: "People", icon: Users, count: 24 },
  { label: "Vacancies", icon: BriefcaseBusiness, count: 7 },
  { label: "Calendar", icon: CalendarDays, count: undefined },
]

function SidebarDemoContent() {
  const [active, setActive] = useState("Overview")
  const [query, setQuery] = useState("")
  const { state, isMobile, setOpenMobile } = useSidebar()
  function select(label: string) {
    setActive(label)
    if (isMobile) setOpenMobile(false)
  }
  return (
    <>
      <Sidebar
        aria-label="Example workspace navigation"
        collapsible="icon"
        className="absolute h-full"
      >
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                size="lg"
                onClick={() => select("Overview")}
                tooltip="HR Vision workspace"
                aria-label="HR Vision workspace"
              >
                <div className="flex size-8 shrink-0 items-center justify-center rounded-sm bg-primary text-primary-foreground">
                  <LayoutGrid className="size-4" />
                </div>
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">HR Vision</span>
                  <span className="block text-xs text-muted-foreground">Workspace</span>
                </span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
          <div className="group-data-[collapsible=icon]:hidden">
            <SidebarInput
              aria-label="Filter sidebar items"
              placeholder="Search workspace…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <SidebarTrigger aria-label="Close example sidebar" className="md:hidden" />
        </SidebarHeader>
        <SidebarSeparator />
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Workspace</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {items
                  .filter((item) => item.label.toLowerCase().includes(query.toLowerCase()))
                  .map(({ label, icon: Icon, count }) => (
                    <SidebarMenuItem key={label}>
                      <SidebarMenuButton
                        isActive={active === label}
                        aria-current={active === label ? "page" : undefined}
                        tooltip={label}
                        aria-label={label}
                        onClick={() => select(label)}
                      >
                        <Icon />
                        <span>{label}</span>
                      </SidebarMenuButton>
                      {count != null && <SidebarMenuBadge>{count}</SidebarMenuBadge>}
                    </SidebarMenuItem>
                  ))}
              </SidebarMenu>
              {!items.some((item) => item.label.toLowerCase().includes(query.toLowerCase())) && (
                <p role="status" className="px-3 py-2 text-xs text-muted-foreground">
                  No matching pages.
                </p>
              )}
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                isActive={active === "Settings"}
                tooltip="Settings"
                aria-label="Settings"
                onClick={() => select("Settings")}
              >
                <Settings />
                <span>Settings</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton
                tooltip="Alex Morgan"
                aria-label="Alex Morgan"
                onClick={() => select("Profile")}
              >
                <div className="shrink-0">
                  <Avatar className="size-6">
                    <AvatarFallback className="text-[10px]">AM</AvatarFallback>
                  </Avatar>
                </div>
                <span>Alex Morgan</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>
      <div className="flex min-w-0 flex-1 flex-col bg-background">
        <div className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-3">
          <SidebarTrigger aria-label="Toggle example sidebar" />
          <span className="hidden text-xs text-muted-foreground sm:inline">Workspace</span>
          <ChevronRight className="size-3 text-muted-foreground" />
          <span className="truncate text-sm font-medium" aria-live="polite">
            {active}
          </span>
          <Badge variant="secondary" className="ml-auto hidden sm:inline-flex">
            {isMobile ? "Drawer" : state === "expanded" ? "Expanded" : "Icons"}
          </Badge>
        </div>
        <div className="min-w-0 flex-1 overflow-auto p-4 sm:p-6">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <span className="text-lg font-semibold">{active}</span>
            <Button variant="outline" size="sm" onClick={() => select("Notifications")}>
              <Bell className="size-4" /> Notifications
            </Button>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ["Team members", "24"],
              ["Open vacancies", "7"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-md border border-border bg-card p-4">
                <span className="text-xs text-muted-foreground">{label}</span>
                <span className="mt-2 block text-2xl font-semibold">{value}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-md border border-border p-4">
            <span className="text-sm font-medium">Recent activity</span>
            <div className="mt-4 space-y-3">
              <Skeleton className="h-3 w-3/4" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

export default function SidebarDemo() {
  return (
    <SidebarProvider
      className="relative isolate h-[480px] min-h-0 overflow-hidden rounded-lg border border-border"
      data-testid="sidebar-demo"
    >
      <SidebarDemoContent />
    </SidebarProvider>
  )
}
