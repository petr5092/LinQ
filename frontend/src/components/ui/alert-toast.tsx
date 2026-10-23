import type { ReactNode } from "react"
import { toast } from "sonner"
import { AlertCircle, CircleCheck } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { isMobileViewport } from "@/hooks/use-mobile"
import { cn } from "@/lib/utils"

export type ToastAlertOptions = {
  title: string
  description?: string
  icon?: ReactNode
  variant?: "default" | "destructive"
  duration?: number
  clampDescription?: boolean
}

/**
 * The app-wide toast: design-system Alert rendered through sonner.
 * Desktop toasts appear top-right below the header; mobile toasts appear
 * above the bottom nav (position is chosen at fire time).
 */
export function toastAlert({
  title,
  description,
  icon,
  variant = "default",
  duration,
  clampDescription = true,
}: ToastAlertOptions): string | number {
  const isMobile = isMobileViewport()

  const resolvedIcon =
    icon ??
    (variant === "destructive" ? (
      <AlertCircle className="size-4" />
    ) : (
      <CircleCheck className="size-4" />
    ))

  // Mobile keeps non-destructive toasts to a single description line — unless
  // the title is all there is.
  const compactOnMobile = variant !== "destructive" && Boolean(description)

  return toast.custom(
    () => (
      <Alert
        variant={variant}
        className="flex w-full min-w-0 flex-row items-start gap-x-2.5 gap-y-0 shadow-md"
      >
        <div
          className={cn(
            "shrink-0 pt-0.5 text-foreground [&>svg]:size-4",
            compactOnMobile && "max-md:hidden",
          )}
        >
          {resolvedIcon}
        </div>
        <div className="min-w-0 flex-1 space-y-0.5">
          <AlertTitle
            className={cn(
              "min-w-0 wrap-break-word",
              variant === "destructive" ? "max-md:block" : "truncate",
              compactOnMobile && "max-md:hidden",
            )}
          >
            {title}
          </AlertTitle>
          {description ? (
            <AlertDescription
              className={cn(
                "min-w-0 whitespace-pre-wrap wrap-break-word",
                clampDescription && "line-clamp-3",
              )}
            >
              {description}
            </AlertDescription>
          ) : null}
        </div>
      </Alert>
    ),
    {
      duration: duration ?? (variant === "destructive" ? 5000 : 3000),
      position: isMobile ? "bottom-center" : "top-right",
    },
  )
}

export function dismissToastAlert(id: string | number): void {
  toast.dismiss(id)
}
