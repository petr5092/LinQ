"use client"

import * as React from "react"
import { Checkbox as CheckboxRoot, CheckboxIndicator } from "@radix-ui/react-checkbox"
import { cn } from "@/lib/utils"

type CheckboxControlProps = React.ComponentProps<typeof CheckboxRoot> & {
  state?: "Enabled" | "Disabled" | "Shimmer"
}

function CheckboxControl({
  className,
  state = "Enabled",
  disabled,
  ...props
}: CheckboxControlProps) {
  const isDisabled = disabled || state === "Disabled"
  const isShimmer = state === "Shimmer"
  return (
    <CheckboxRoot
      data-slot="checkbox-control"
      data-control-state={isShimmer ? "Shimmer" : isDisabled ? "Disabled" : "Enabled"}
      disabled={isDisabled || isShimmer}
      aria-busy={isShimmer || undefined}
      className={cn(
        "group/hr-checkbox relative inline-flex size-6 shrink-0 items-center justify-center rounded-xs border-0 bg-transparent p-0 shadow-none outline-none",
        "before:absolute before:inset-[2px] before:rounded-[var(--radius-xs)] before:border-2 before:border-muted-foreground before:content-['']",
        "data-[state=checked]:before:border-transparent data-[state=checked]:before:bg-foreground",
        "data-[state=indeterminate]:before:border-transparent data-[state=indeterminate]:before:bg-foreground",
        "focus-visible:before:shadow-[0_0_0_3px_var(--outline)]",
        "disabled:cursor-not-allowed disabled:before:border-border disabled:data-[state=checked]:before:bg-border disabled:data-[state=indeterminate]:before:bg-border",
        isShimmer && "before:hidden",
        className,
      )}
      {...props}
    >
      <CheckboxIndicator
        data-slot="checkbox-control-indicator"
        className={cn(
          "pointer-events-none relative z-10 flex size-6 items-center justify-center",
          isShimmer && "hidden",
        )}
      >
        <img
          src="/assets/hr-checkbox/check.svg"
          alt=""
          width={24}
          height={24}
          className="group-data-[state=indeterminate]/hr-checkbox:hidden group-disabled/hr-checkbox:hidden dark:hidden"
        />
        <img
          src="/assets/hr-checkbox/check-dark.svg"
          alt=""
          width={24}
          height={24}
          className="hidden dark:block group-data-[state=indeterminate]/hr-checkbox:!hidden group-disabled/hr-checkbox:!hidden"
        />
        <img
          src="/assets/hr-checkbox/minus.svg"
          alt=""
          width={24}
          height={24}
          className="hidden group-data-[state=indeterminate]/hr-checkbox:block group-disabled/hr-checkbox:!hidden dark:!hidden"
        />
        <img
          src="/assets/hr-checkbox/minus-dark.svg"
          alt=""
          width={24}
          height={24}
          className="hidden dark:group-data-[state=indeterminate]/hr-checkbox:block group-disabled/hr-checkbox:!hidden"
        />
        <img
          src="/assets/hr-checkbox/check-disabled.svg"
          alt=""
          width={24}
          height={24}
          className="hidden group-disabled/hr-checkbox:block group-data-[state=indeterminate]/hr-checkbox:!hidden"
        />
        <img
          src="/assets/hr-checkbox/minus-disabled.svg"
          alt=""
          width={24}
          height={24}
          className="hidden group-disabled/hr-checkbox:group-data-[state=indeterminate]/hr-checkbox:block"
        />
      </CheckboxIndicator>
      {isShimmer && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-[2px] rounded-[var(--radius-xs)] bg-gradient-to-r from-white/4 via-transparent to-white/4"
        />
      )}
    </CheckboxRoot>
  )
}

type CheckboxFieldProps = Omit<CheckboxControlProps, "state"> & {
  state?: CheckboxControlProps["state"] | "Default" | "Focus"
  label?: string
  description?: string
  showText?: boolean
}

function CheckboxField({
  label,
  description,
  showText = false,
  state = "Default",
  className,
  ...props
}: CheckboxFieldProps) {
  const id = React.useId()
  const controlId = props.id ?? id
  const labelId = `${id}-label`
  const descriptionId = `${id}-description`
  return (
    <div
      data-slot="checkbox-field"
      data-field-state={state}
      className={cn("flex items-start gap-2", className)}
    >
      <CheckboxControl
        state={state === "Default" || state === "Focus" ? "Enabled" : state}
        className={state === "Focus" ? "before:shadow-[0_0_0_3px_var(--outline)]" : undefined}
        id={controlId}
        aria-label={!showText ? label : undefined}
        aria-labelledby={showText ? labelId : undefined}
        aria-describedby={showText && description ? descriptionId : undefined}
        {...props}
      />
      {showText && (
        <div className="flex min-w-0 flex-col gap-1.5">
          <label id={labelId} htmlFor={controlId} className="text-sm font-medium leading-none">
            {label}
          </label>
          {description && (
            <span
              id={descriptionId}
              className="text-sm font-normal leading-5 text-muted-foreground"
            >
              {description}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

export { CheckboxControl, CheckboxField }
