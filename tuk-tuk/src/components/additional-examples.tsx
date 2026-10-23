import { lazy, Suspense, useState } from "react"
import { Toaster } from "sonner"
import {
  AlertCircle,
  CalendarDays,
  ChevronDown,
  CircleCheck,
  Copy,
  Download,
  Mail,
  Search,
  Settings,
  Users,
} from "lucide-react"
import { Section, Specimen } from "@/components/catalog-section"
import SidebarDemo from "@/components/sidebar-demo"
import { useTheme } from "@/components/theme-provider"
import { Button, buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Calendar } from "@/components/ui/calendar"
import { InputOTP, InputOTPGroup, InputOTPSeparator, InputOTPSlot } from "@/components/ui/input-otp"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
  InputGroupText,
} from "@/components/ui/input-group"
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { toastAlert } from "@/components/ui/alert-toast"
import { Switch } from "@/components/ui/switch"
import { Spinner } from "@/components/ui/spinner"
import { Skeleton } from "@/components/ui/skeleton"

const SyntaxCodeBlock = lazy(() =>
  import("@/components/ui/syntax-code-block").then((module) => ({
    default: module.SyntaxCodeBlock,
  })),
)
const people = [
  { name: "Alex Morgan", initials: "AM", role: "Designer", status: "Active" },
  { name: "Jamie Lee", initials: "JL", role: "Engineer", status: "Active" },
  { name: "Sam Taylor", initials: "ST", role: "Recruiter", status: "Invited" },
]
const sampleCode =
  'import { Button } from "@/components/ui/button"\n\nexport function Example() {\n  return <Button variant="outline">Continue</Button>\n}'

function FormsExamples() {
  const [role, setRole] = useState("designer")
  const [date, setDate] = useState<Date | undefined>(new Date(2026, 9, 23))
  const [code, setCode] = useState("")
  const [ascending, setAscending] = useState(true)
  const [search, setSearch] = useState("")
  const [command, setCommand] = useState("No command selected")
  const visiblePeople = people
    .filter((person) => person.name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => (ascending ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name)))
  return (
    <Section id="forms" eyebrow="04 — Forms & data" title="Forms, people & data">
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        <Specimen searchable title="Select" note="Dropdown selection · default and disabled states">
          <div className="space-y-4">
            <label htmlFor="demo-role" className="block text-xs font-medium">
              Team role
            </label>
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger id="demo-role" className="w-full">
                <SelectValue placeholder="Choose a role" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectLabel>Team roles</SelectLabel>
                  <SelectItem value="designer">Designer</SelectItem>
                  <SelectItem value="engineer">Engineer</SelectItem>
                  <SelectItem value="recruiter">Recruiter</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <Select disabled>
              <SelectTrigger aria-label="Disabled role" className="w-full">
                <SelectValue placeholder="Disabled select" />
              </SelectTrigger>
            </Select>
            <span className="block text-xs text-muted-foreground" aria-live="polite">
              Selected: {role}
            </span>
          </div>
        </Specimen>
        <Specimen
          searchable
          title="Input group"
          note="Leading icon, trailing action and text addon"
        >
          <div className="space-y-4">
            <InputGroup>
              <InputGroupAddon>
                <Search />
              </InputGroupAddon>
              <InputGroupInput
                aria-label="Search people"
                placeholder="Search people…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              <InputGroupAddon align="inline-end">
                <InputGroupButton aria-label="Clear people search" onClick={() => setSearch("")}>
                  Clear
                </InputGroupButton>
              </InputGroupAddon>
            </InputGroup>
            <InputGroup>
              <InputGroupAddon>
                <Mail />
              </InputGroupAddon>
              <InputGroupInput aria-label="Work email" placeholder="alex" />
              <InputGroupAddon align="inline-end">
                <InputGroupText>@team.io</InputGroupText>
              </InputGroupAddon>
            </InputGroup>
          </div>
        </Specimen>
        <Specimen searchable title="Input OTP" note="Six-digit code · keyboard and paste support">
          <div className="space-y-4">
            <InputOTP
              aria-label="Verification code"
              maxLength={6}
              pattern="[0-9]*"
              inputMode="numeric"
              value={code}
              onChange={setCode}
              containerClassName="gap-2"
            >
              <InputOTPGroup className="gap-1">
                {[0, 1, 2].map((index) => (
                  <InputOTPSlot
                    key={index}
                    index={index}
                    className="size-7 rounded-sm sm:size-10"
                  />
                ))}
              </InputOTPGroup>
              <InputOTPSeparator />
              <InputOTPGroup className="gap-1">
                {[3, 4, 5].map((index) => (
                  <InputOTPSlot
                    key={index}
                    index={index}
                    className="size-7 rounded-sm sm:size-10"
                  />
                ))}
              </InputOTPGroup>
            </InputOTP>
            <p className="text-xs text-muted-foreground" role="status">
              {code.length === 6 ? "Demo code complete" : `${code.length} of 6 digits entered`}
            </p>
          </div>
        </Specimen>
        <Specimen searchable title="Calendar" note="Single date selection and month navigation">
          <Calendar
            mode="single"
            selected={date}
            onSelect={setDate}
            defaultMonth={new Date(2026, 9)}
            className="mx-auto w-fit max-w-full p-0"
            classNames={{
              weekday: "w-7 text-center text-xs font-normal text-muted-foreground sm:w-9",
              day: "relative size-7 p-0 text-center text-sm sm:size-9",
              day_button: cn(
                buttonVariants({ variant: "ghost", size: "icon-sm" }),
                "size-7 rounded-md p-0 font-normal sm:size-9",
              ),
            }}
          />
          <p className="mt-4 text-xs text-muted-foreground" aria-live="polite">
            {date
              ? `Selected: ${date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`
              : "Choose a date"}
          </p>
        </Specimen>
        <Specimen searchable title="Avatar" note="Initials, sizes and a compact team stack">
          <div className="flex flex-wrap items-end gap-4">
            {[8, 10, 12].map((size, index) => (
              <div key={size} className="flex flex-col items-center gap-2">
                <Avatar style={{ width: size * 4, height: size * 4 }}>
                  <AvatarFallback>{people[index].initials}</AvatarFallback>
                </Avatar>
                <span className="text-xs text-muted-foreground">{size * 4}px</span>
              </div>
            ))}
          </div>
          <div className="mt-6 flex -space-x-2">
            {people.map((person) => (
              <Avatar
                key={person.name}
                aria-label={person.name}
                className="size-8 border-2 border-card"
              >
                <AvatarFallback className="text-xs">{person.initials}</AvatarFallback>
              </Avatar>
            ))}
          </div>
        </Specimen>
        <Specimen searchable title="Command" note="Searchable command list · keyboard selection">
          <Command className="h-auto border border-border">
            <CommandInput aria-label="Search demo commands" placeholder="Type a command…" />
            <CommandList>
              <CommandEmpty>No commands found.</CommandEmpty>
              <CommandGroup heading="Workspace">
                {[
                  { label: "Open people", icon: Users },
                  { label: "Open calendar", icon: CalendarDays },
                  { label: "Open settings", icon: Settings },
                ].map(({ label, icon: Icon }) => (
                  <CommandItem key={label} onSelect={() => setCommand(label)}>
                    <Icon />
                    {label}
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
          <p role="status" className="mt-4 text-xs text-muted-foreground">
            {command}
          </p>
        </Specimen>
        <Specimen
          searchable
          title="Table"
          note="Team members · sortable name column · filtered by Search people"
          className="md:col-span-2 xl:col-span-3"
        >
          <Table>
            <TableCaption>Example team directory</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead aria-sort={ascending ? "ascending" : "descending"}>
                  <button
                    type="button"
                    className="inline-flex items-center gap-2"
                    onClick={() => setAscending((value) => !value)}
                  >
                    Name <span aria-hidden="true">{ascending ? "↑" : "↓"}</span>
                  </button>
                </TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visiblePeople.map((person) => (
                <TableRow key={person.name}>
                  <TableCell>
                    <span className="inline-flex items-center gap-2">
                      <Avatar className="hidden size-7 sm:flex">
                        <AvatarFallback className="text-[10px]">{person.initials}</AvatarFallback>
                      </Avatar>
                      {person.name}
                    </span>
                  </TableCell>
                  <TableCell>{person.role}</TableCell>
                  <TableCell>
                    <Badge variant={person.status === "Active" ? "success-soft" : "secondary"}>
                      {person.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
              {visiblePeople.length === 0 && (
                <TableRow>
                  <TableCell colSpan={3} className="py-8 text-center text-muted-foreground">
                    No people match your search.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Specimen>
      </div>
    </Section>
  )
}

function OverlayExamples() {
  const [teamName, setTeamName] = useState("Design team")
  const [draftName, setDraftName] = useState(teamName)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [notify, setNotify] = useState(true)
  const [message, setMessage] = useState("Choose an action to see the result.")
  const [showCode, setShowCode] = useState(false)
  return (
    <Section id="overlays" eyebrow="05 — Overlays & feedback" title="Menus, dialogs & feedback">
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        <Specimen
          searchable
          title="Dialog"
          note="Editable form · save, cancel and focus restoration"
        >
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground" aria-live="polite">
              Team: {teamName}
            </p>
            <Dialog
              open={dialogOpen}
              onOpenChange={(open) => {
                if (open) setDraftName(teamName)
                setDialogOpen(open)
              }}
            >
              <DialogTrigger asChild>
                <Button variant="outline">Edit demo team</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Edit team</DialogTitle>
                  <DialogDescription>Change the name in this local demo.</DialogDescription>
                </DialogHeader>
                <form
                  onSubmit={(event) => {
                    event.preventDefault()
                    if (draftName.trim()) {
                      setTeamName(draftName.trim())
                      setDialogOpen(false)
                    }
                  }}
                >
                  <label htmlFor="demo-team-name" className="mb-2 block text-sm font-medium">
                    Team name
                  </label>
                  <Input
                    id="demo-team-name"
                    required
                    value={draftName}
                    onChange={(event) => setDraftName(event.target.value)}
                  />
                  <DialogFooter>
                    <DialogClose asChild>
                      <Button variant="outline" type="button">
                        Cancel
                      </Button>
                    </DialogClose>
                    <Button type="submit">Save team</Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          </div>
        </Specimen>
        <Specimen
          searchable
          title="Alert dialog"
          note="Confirmation flow · cancel and destructive action"
        >
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline">Archive demo project</Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Archive this example?</AlertDialogTitle>
                <AlertDialogDescription>
                  This action changes the demo status below.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Keep project</AlertDialogCancel>
                <AlertDialogAction
                  variant="destructive"
                  onClick={() => setMessage("Demo project archived.")}
                >
                  Confirm archive
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </Specimen>
        <Specimen searchable title="Sheet" note="Side panel · right and bottom positions">
          <div className="flex flex-wrap gap-2">
            {(["right", "bottom"] as const).map((side) => (
              <Sheet key={side}>
                <SheetTrigger asChild>
                  <Button variant="outline">Open {side} sheet</Button>
                </SheetTrigger>
                <SheetContent side={side}>
                  <SheetHeader>
                    <SheetTitle>Notification settings</SheetTitle>
                    <SheetDescription>
                      A {side} sheet built with the library component.
                    </SheetDescription>
                  </SheetHeader>
                  <div className="flex items-center justify-between gap-4 px-4">
                    <label htmlFor={`sheet-notify-${side}`} className="text-sm">
                      Email notifications
                    </label>
                    <Switch
                      id={`sheet-notify-${side}`}
                      checked={notify}
                      onCheckedChange={setNotify}
                    />
                  </div>
                  <SheetFooter>
                    <SheetClose asChild>
                      <Button>Done</Button>
                    </SheetClose>
                  </SheetFooter>
                </SheetContent>
              </Sheet>
            ))}
          </div>
        </Specimen>
        <Specimen
          searchable
          title="Dropdown menu"
          note="Action menu · separators and disabled item"
        >
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">
                Project actions
                <ChevronDown className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="p-1">
              <DropdownMenuItem onSelect={() => setMessage("Demo project duplicated.")}>
                <Copy className="size-4" />
                Duplicate project
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => setMessage("Demo export prepared.")}>
                <Download className="size-4" />
                Prepare export
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem disabled>Transfer ownership</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </Specimen>
        <Specimen searchable title="Popover" note="Anchored panel with an interactive preference">
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline">View preferences</Button>
            </PopoverTrigger>
            <PopoverContent align="start" className="max-w-[calc(100vw-2rem)] gap-4 p-4">
              <PopoverHeader>
                <PopoverTitle>Preferences</PopoverTitle>
                <PopoverDescription>
                  Toggle the same preference used in the sheet.
                </PopoverDescription>
              </PopoverHeader>
              <div className="flex items-center justify-between gap-3">
                <label htmlFor="popover-notify">Email notifications</label>
                <Switch id="popover-notify" checked={notify} onCheckedChange={setNotify} />
              </div>
            </PopoverContent>
          </Popover>
        </Specimen>
        <Specimen
          searchable
          title="Toast"
          note="Transient notifications · success and error alerts"
        >
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={() =>
                toastAlert({
                  title: "Changes saved",
                  description: "Your demo preferences are up to date.",
                })
              }
            >
              <CircleCheck className="size-4" />
              Show success toast
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                toastAlert({
                  title: "Something went wrong",
                  description: "This is an example error notification.",
                  variant: "destructive",
                })
              }
            >
              Show error toast
            </Button>
          </div>
        </Specimen>
        <Specimen
          searchable
          title="Alert"
          note="Persistent default and destructive messages"
          className="md:col-span-2"
        >
          <div className="space-y-3">
            <Alert>
              <CircleCheck />
              <AlertTitle>Everything is up to date</AlertTitle>
              <AlertDescription>Your team settings were saved successfully.</AlertDescription>
            </Alert>
            <Alert variant="destructive">
              <AlertCircle />
              <AlertTitle>Review required</AlertTitle>
              <AlertDescription>Check the example information before continuing.</AlertDescription>
            </Alert>
          </div>
        </Specimen>
        <Specimen searchable title="Spinner" note="Loading indicators and a busy button">
          <div className="flex items-center gap-4">
            <Spinner className="size-4" />
            <Spinner className="size-6 text-primary" />
            <Button loading>Saving</Button>
          </div>
        </Specimen>
        <Specimen
          searchable
          title="Code block"
          note="Syntax highlighting · TypeScript example"
          className="md:col-span-2 xl:col-span-3"
        >
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowCode((value) => !value)}
            aria-expanded={showCode}
            aria-controls="demo-code"
          >
            {showCode ? "Hide code example" : "Show code example"}
          </Button>
          {showCode && (
            <div
              id="demo-code"
              className="mt-4 min-w-0 rounded-md border border-border bg-background p-4"
            >
              <Suspense fallback={<Skeleton className="h-24 w-full" />}>
                <SyntaxCodeBlock language="typescript" code={sampleCode} />
              </Suspense>
            </div>
          )}
        </Specimen>
      </div>
      <p role="status" className="mt-5 text-sm text-muted-foreground">
        {message}
      </p>
    </Section>
  )
}

export default function AdditionalExamples() {
  const { mode } = useTheme()
  return (
    <>
      <Toaster theme={mode} closeButton />
      <Section id="sidebar" eyebrow="03 — Layout & navigation" title="Sidebar">
        <Specimen
          searchable
          title="Sidebar"
          note="Expanded and icon states · active pages · search · Cmd/Ctrl+B · mobile drawer"
        >
          <SidebarDemo />
          <p className="mt-4 text-xs text-muted-foreground">
            Use the panel button to collapse the sidebar. On mobile, the same button opens a drawer.
            Select a page to update the example workspace.
          </p>
        </Specimen>
      </Section>
      <FormsExamples />
      <OverlayExamples />
    </>
  )
}
