import type { ComponentProps, ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type MobileHeaderProps = ComponentProps<"header"> & {
  title: string
  subtitle?: string
  leading?: ReactNode
  trailing?: ReactNode
  onBack?: () => void
  border?: boolean
}

function MobileHeader({
  title,
  subtitle,
  leading,
  trailing,
  onBack,
  border = true,
  className,
  ...props
}: MobileHeaderProps) {
  return (
    <header
      data-slot="mobile-header"
      className={cn(
        "flex h-[50px] w-full max-w-[640px] items-center justify-between bg-background px-2 py-1",
        border && "border-b border-border",
        className,
      )}
      {...props}
    >
      <div className="flex h-[42px] min-w-0 flex-1 items-center pl-1">
        {leading ?? (
          <Button
            variant="ghost"
            size="icon-sm"
            className="rounded-full"
            aria-label="Back"
            onClick={onBack}
          >
            <img
              src="/assets/hr-navigation/chevron-left.svg"
              alt=""
              width={16}
              height={16}
              className="dark:invert"
            />
          </Button>
        )}
      </div>
      <div className="flex h-[42px] min-w-0 flex-1 flex-col items-center justify-center gap-1 text-center">
        <span className="w-full truncate text-base font-semibold leading-none">{title}</span>
        {subtitle && (
          <span className="w-full truncate text-xs leading-4 text-muted-foreground">
            {subtitle}
          </span>
        )}
      </div>
      <div className="flex h-[42px] min-w-0 flex-1 items-center justify-end pr-1">{trailing}</div>
    </header>
  )
}

type MobileNavItem = { value: string; label: string; icon?: ReactNode; disabled?: boolean }
type MobileNavbarProps = ComponentProps<"nav"> & {
  items: MobileNavItem[]
  value: string
  onValueChange: (value: string) => void
}

function MobileNavbar({ items, value, onValueChange, className, ...props }: MobileNavbarProps) {
  return (
    <nav
      data-slot="mobile-navbar"
      aria-label="Mobile navigation"
      className={cn("flex h-16 w-full border-t border-border bg-background", className)}
      {...props}
    >
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          disabled={item.disabled}
          aria-current={value === item.value ? "page" : undefined}
          onClick={() => onValueChange(item.value)}
          className="group/nav-tab flex h-full min-w-0 flex-1 flex-col items-center justify-center gap-1 pb-1 pt-2 text-xs leading-4 text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring disabled:opacity-50 aria-[current=page]:text-foreground"
        >
          <span className="flex h-8 w-12 items-center justify-center rounded-lg group-aria-[current=page]/nav-tab:bg-accent [&_svg]:size-6">
            {item.icon ?? (
              <img
                src="/assets/hr-navigation/tab-hash.svg"
                alt=""
                width={24}
                height={24}
                className="dark:invert"
              />
            )}
          </span>
          <span className="w-full truncate px-1">{item.label}</span>
        </button>
      ))}
    </nav>
  )
}

export { MobileHeader, MobileNavbar }
export type { MobileHeaderProps, MobileNavbarProps, MobileNavItem }
