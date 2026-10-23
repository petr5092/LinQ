import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"
import { Spinner } from "@/components/ui/spinner"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "group/button relative inline-flex shrink-0 items-center justify-center gap-2 overflow-hidden rounded-[var(--radius-md)] border-[0.5px] border-transparent bg-clip-padding text-sm font-medium whitespace-nowrap transition-[background-color,background-image,box-shadow,opacity,color] outline-none select-none focus-visible:shadow-[0_0_0_3px_var(--outline)] active:opacity-60 disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "hr-button-primary text-primary-foreground",
        secondary: "hr-button-secondary text-secondary-foreground",
        outline: "hr-button-outline border-input text-foreground",
        ghost: "hr-button-ghost text-foreground",
        destructive: "hr-button-destructive text-destructive-foreground",
        link: "hr-button-link text-primary",
      },
      size: {
        default: "h-10 px-5 py-2",
        sm: "h-9 px-4 py-2 text-xs",
        lg: "h-11 px-6 py-2",
        icon: "size-10 p-0",
        "icon-sm": "size-9 p-0",
        "icon-lg": "size-11 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  loading = false,
  children,
  disabled,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
    loading?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      aria-busy={loading || undefined}
      disabled={disabled || loading}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    >
      {loading && <Spinner aria-hidden="true" />}
      <Slot.Slottable>{children}</Slot.Slottable>
    </Comp>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export { Button, buttonVariants }
