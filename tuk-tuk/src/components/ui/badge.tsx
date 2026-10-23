import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex h-5 shrink-0 items-center justify-center gap-1 whitespace-nowrap rounded-md border-[0.5px] border-border-subtle px-2 py-0.5 text-xs font-semibold leading-4 transition-colors [&_svg]:size-3",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive: "bg-destructive-60 text-white hover:bg-destructive-90",
        "destructive-soft":
          "border-transparent bg-destructive/15 text-destructive hover:bg-destructive/25",
        verified: "bg-primary text-primary-foreground hover:bg-primary/90",
        success: "bg-success text-white hover:bg-success/90",
        "success-soft": "border-transparent bg-success/15 text-success hover:bg-success/25",
        outline: "border-border bg-transparent text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof badgeVariants>) {
  return <div data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />
}

// eslint-disable-next-line react-refresh/only-export-components
export { Badge, badgeVariants }
